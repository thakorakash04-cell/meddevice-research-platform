import io
from unittest.mock import Mock,patch
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from fda_pdf import extract_pdf,fetch_fda_summary,collect_pdf_evidence,valid_fda_pdf_url
from grounded_ai import ask

TEXT='Device: Example Laser. Intended use: soft tissue cutting. Predicate: K230001. Bench testing: output power was tested. Clinical data were not provided in this summary.'
TABLES=[{'id':'T1','name':'FDA 510(k)','headers':['510(k) Number','Device Name'],'rows':[['K240001','Example Laser'],['K240002','Other Laser']]}]

def pdf_bytes(text=TEXT,encrypted=False):
    writer=PdfWriter();page=writer.add_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();escaped=text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    stream.set_data(('BT /F1 12 Tf 72 720 Td ('+escaped+') Tj ET').encode())
    page[NameObject('/Contents')]=writer._add_object(stream)
    if encrypted:writer.encrypt('password')
    output=io.BytesIO();writer.write(output);return output.getvalue()

def response(status=200,raw=None,headers=None):
    result=Mock(status_code=status,headers=headers or {});result.__enter__=Mock(return_value=result);result.__exit__=Mock(return_value=False)
    result.iter_content.return_value=[raw if raw is not None else pdf_bytes()];return result

def test_extracts_real_pdf_text_with_page_positions():
    document=extract_pdf(pdf_bytes())
    assert document['pages'][0]['page']==1 and 'Intended use' in document['pages'][0]['text']
    assert document['total_pages']==1 and document['status']=='read'

@pytest.mark.parametrize('raw,match',[(b'<!doctype html>','not a readable PDF'),(b'%PDF-invalid','parsed safely')])
def test_html_and_corrupt_pdf_are_rejected(raw,match):
    with pytest.raises(ValueError,match=match):extract_pdf(raw)

def test_encrypted_scanned_and_large_inputs_are_rejected():
    with pytest.raises(ValueError,match='Password'):extract_pdf(pdf_bytes(encrypted=True))
    with pytest.raises(ValueError,match='OCR'):extract_pdf(pdf_bytes(''))
    with patch('fda_pdf.MAX_BYTES',10):
        with pytest.raises(ValueError,match='10 MB'):extract_pdf(pdf_bytes())

def test_truncation_is_explicit():
    with patch('fda_pdf.MAX_TEXT',100):
        document=extract_pdf(pdf_bytes())
    assert len(document['pages'][0]['text'])==100 and any('partial' in w for w in document['warnings'])

def test_fetch_uses_only_fixed_fda_pdf_location_and_blocks_redirects():
    fetch_fda_summary.clear()
    with patch('fda_pdf.requests.get',return_value=response()) as get:
        document=fetch_fda_summary('K240001')
        assert document['url']=='https://www.accessdata.fda.gov/cdrh_docs/pdf24/K240001.pdf'
        assert get.call_args.kwargs['allow_redirects'] is False
    fetch_fda_summary.clear()
    with patch('fda_pdf.requests.get',return_value=response(302,headers={'Location':'http://127.0.0.1/private'})) as get:
        with pytest.raises(ValueError,match='outside'):fetch_fda_summary('K240001')
        assert get.call_count==1
    with patch('fda_pdf.requests.get') as get:
        with pytest.raises(ValueError):fetch_fda_summary('../../secret')
        get.assert_not_called()
    assert not valid_fda_pdf_url('https://www.accessdata.fda.gov.evil.test/cdrh_docs/pdf24/K240001.pdf')

@pytest.mark.parametrize('status,match',[(403,'blocked'),(404,'No summary'),(500,'HTTP 500')])
def test_download_failures_are_actionable(status,match):
    fetch_fda_summary.clear()
    with patch('fda_pdf.requests.get',return_value=response(status)):
        with pytest.raises(ValueError,match=match):fetch_fda_summary('K240001')

def test_loaded_record_allowlist_and_permissions_guard_download():
    store=Mock();actor=Mock()
    with patch('fda_pdf.fetch_fda_summary') as fetch:
        docs=collect_pdf_evidence(TABLES,[],'Read K999999 PDF',store,actor)
        fetch.assert_not_called();assert docs[0]['status']=='unavailable'
        store.require_permission.side_effect=PermissionError('revoked')
        with pytest.raises(PermissionError):collect_pdf_evidence(TABLES,[],'Read K240001 PDF',store,actor)
        fetch.assert_not_called()

def test_requested_pdf_evidence_reaches_answer_call_only_when_requested():
    document=extract_pdf(pdf_bytes(),k_number='K240001')
    plan={'queries':[{'table':'T1','filters':[{'column':'510(k) Number','op':'eq','value':'K240001'}]}],'read_fda_pdfs':True,'clarification':''}
    loader=Mock(return_value=[document])
    with patch('grounded_ai.settings',return_value=('secret','model')),patch('grounded_ai.generate',side_effect=[plan,'The summary describes soft tissue cutting.']) as generate:
        result=ask(TABLES,'Extract intended use from the K240001 PDF.',pdf_loader=loader)
        assert loader.call_count==1 and result['pdf_documents'][0]['total_pages']==1
        assert generate.call_args.args[3]['pdf_documents'][0]['pages'][0]['text']==TEXT
        assert 'untrusted' in generate.call_args.args[2]
    loader.reset_mock()
    with patch('grounded_ai.settings',return_value=('secret','model')),patch('grounded_ai.generate',side_effect=[{'queries':[{'table':'T1','metrics':[{'column':'*','op':'count'}]}],'clarification':''},'Two records.']):
        ask(TABLES,'How many records?',pdf_loader=loader)
        loader.assert_not_called()

def test_failed_pdf_does_not_produce_invented_document_answer():
    with patch('grounded_ai.settings',return_value=('secret','model')),patch('grounded_ai.generate',return_value={'queries':[],'read_fda_pdfs':True}) as generate:
        result=ask(TABLES,'Read the PDF',pdf_loader=lambda *_:[{'status':'unavailable','pages':[],'warnings':['not found']}])
        assert 'could not read' in result['answer'] and generate.call_count==1
