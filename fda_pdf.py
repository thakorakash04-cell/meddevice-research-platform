"""Bounded, read-only extraction of public FDA summaries and session-private uploads."""
import hashlib,io,re
from urllib.parse import urljoin,urlsplit
import requests
import streamlit as st
from pypdf import PdfReader,filters
from research_engine import get_fda_pdf_link

MAX_BYTES=10_000_000
MAX_TEXT=60_000
MAX_READ_PAGES=60
# Bound decompression before inspecting page content streams.
filters.ZLIB_MAX_OUTPUT_LENGTH=min(filters.ZLIB_MAX_OUTPUT_LENGTH,8_000_000)

def extract_pdf(raw,source_name='Uploaded summary',url=None,k_number=None):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError('Choose a PDF under 10 MB.')
    if not raw.lstrip().startswith(b'%PDF-'):raise ValueError('This file is not a readable PDF; the server may have returned an HTML page.')
    try:
        reader=PdfReader(io.BytesIO(raw),strict=False)
        if reader.is_encrypted:raise ValueError('Password-protected PDFs are not supported. Upload an unlocked summary.')
        total=len(reader.pages)
        if total>200:raise ValueError('This PDF exceeds 200 pages. Upload the summary section separately.')
        pages=[];warnings=[];characters=0;content_bytes=0
        for index in range(min(total,MAX_READ_PAGES)):
            page=reader.pages[index]
            contents=page.get_contents()
            if contents:
                length=len(contents.get_data());content_bytes+=length
                if length>5_000_000 or content_bytes>25_000_000:
                    warnings.append('Extraction stopped at page '+str(index+1)+' because the PDF content stream exceeded the processing limit.');break
            text=page.extract_text() or ''
            text=text.replace('\x00','').strip()
            remaining=MAX_TEXT-characters
            if not remaining:
                warnings.append('Text limited to 60,000 characters; later pages were not read.');break
            if len(text)>remaining:
                text=text[:remaining];warnings.append('Text limited to 60,000 characters; the final extracted page is partial.')
            pages.append({'page':index+1,'text':text});characters+=len(text)
        if total>MAX_READ_PAGES:warnings.append('Only the first 60 pages were read.')
        empty=[p['page'] for p in pages if len(p['text'])<30]
        if empty:warnings.append('Pages with little or no extractable text: '+', '.join(map(str,empty))+'. Scans and image-only tables need OCR; figures were not interpreted.')
        if sum(len(p['text']) for p in pages)<80:raise ValueError('This PDF has little or no readable text. It may be scanned; upload an OCR/text-searchable copy. No image OCR is performed.')
        return {'name':source_name,'k_number':k_number,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'total_pages':total,'read_pages':len(pages),'pages':pages,'warnings':warnings,'status':'read'}
    except ValueError:raise
    except Exception:raise ValueError('The PDF could not be parsed safely. Try another text-searchable summary PDF.') from None

def valid_fda_pdf_url(url):
    parsed=urlsplit(url)
    return parsed.scheme=='https' and parsed.netloc=='www.accessdata.fda.gov' and not parsed.query and not parsed.fragment and bool(re.fullmatch(r'/cdrh_docs/pdf\d{1,2}/K\d{6}\.pdf',parsed.path))

@st.cache_data(ttl=3600,max_entries=20,show_spinner=False)
def fetch_fda_summary(k_number):
    if not isinstance(k_number,str) or not re.fullmatch(r'K\d{6}',k_number):raise ValueError('Use a valid 510(k) number such as K240001.')
    url=get_fda_pdf_link(k_number)
    try:
        for attempt in range(3):
            if not valid_fda_pdf_url(url):raise ValueError('The summary URL is outside the permitted FDA PDF location.')
            with requests.get(url,stream=True,timeout=(10,20),allow_redirects=False,headers={'User-Agent':'MedDevice-Research/1.0','Accept':'application/pdf'}) as response:
                if response.status_code in (301,302,303,307,308):
                    url=urljoin(url,response.headers.get('Location',''))
                    if not valid_fda_pdf_url(url):raise ValueError('FDA redirected the request outside the permitted PDF location.')
                    continue
                if response.status_code==404:raise ValueError('No summary PDF was found at the standard FDA link. Upload a text-searchable copy if available.')
                if response.status_code in (403,429):raise ValueError('FDA blocked or rate-limited the download. Open the source link and upload a text-searchable copy instead.')
                if response.status_code!=200:raise ValueError('FDA summary download failed (HTTP '+str(response.status_code)+'). Retry or upload a copy.')
                length=response.headers.get('Content-Length','')
                if length.isdigit() and int(length)>MAX_BYTES:raise ValueError('The FDA PDF exceeds the 10 MB limit.')
                body=bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    body.extend(chunk)
                    if len(body)>MAX_BYTES:raise ValueError('The FDA PDF exceeds the 10 MB limit.')
                return extract_pdf(bytes(body),k_number+' FDA summary',url,k_number)
        raise ValueError('The FDA summary redirected too many times. Upload a copy instead.')
    except requests.RequestException:raise ValueError('Cannot reach the FDA summary PDF. Retry or upload a text-searchable copy.') from None

def loaded_k_numbers(tables):
    found={}
    for table in tables:
        if table['name']!='FDA 510(k)' or '510(k) Number' not in table['headers']:continue
        col=table['headers'].index('510(k) Number')
        for row in table['rows']:
            k=str(row[col]).upper()
            if re.fullmatch(r'K\d{6}',k):found[k]=True
    return set(found)

def collect_pdf_evidence(tables,evidence,question,store,actor,uploaded=None):
    """Only server-owned loaded FDA IDs can trigger downloads; never follow model URLs."""
    store.require_permission(actor,'use_tools')
    allowed=loaded_k_numbers(tables)
    explicit=list(dict.fromkeys(re.findall(r'\bK\d{6}\b',question.upper())))
    requested=[k for k in explicit if k in allowed]
    if not explicit:
        for item in evidence:
            if item.get('table')!='FDA 510(k)':continue
            for record in item.get('records',[]):
                k=str(record.get('510(k) Number','')).upper()
                if k in allowed and k not in requested:requested.append(k)
    documents=[]
    if uploaded:documents.append(uploaded)
    for k in explicit:
        if k not in allowed:documents.append({'name':k,'k_number':k,'status':'unavailable','pages':[],'warnings':['This 510(k) number is not in the current FDA results. Run a matching search first.']})
    limit=3-(1 if uploaded else 0)
    for k in requested[:limit]:
        store.require_permission(actor,'use_tools')
        try:documents.append(fetch_fda_summary(k))
        except ValueError as exc:documents.append({'name':k+' FDA summary','k_number':k,'url':get_fda_pdf_link(k),'status':'unavailable','pages':[],'warnings':[str(exc)]})
    if len(requested)>limit:documents.append({'name':'Document limit','status':'notice','pages':[],'warnings':['Only the first '+str(limit)+' selected FDA summaries were attempted. Narrow the question for other devices.']})
    if not documents:documents=[{'name':'PDF selection','status':'notice','pages':[],'warnings':['No specific loaded FDA records were selected. Ask about a loaded K-number, or upload a summary and request PDF analysis.']}]
    store.require_permission(actor,'use_tools')
    return documents
