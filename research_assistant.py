"""Session-private chat over the current research results, isolated from search reruns."""
import hashlib
import pandas as pd
import streamlit as st
from grounded_ai import ask,settings,clean_answer
from fda_pdf import extract_pdf,collect_pdf_evidence

def queue_research_question():
    # Form callbacks run before widget rendering, allowing a successful answer
    # to reset only the question without clearing consent or triggering reruns.
    st.session_state['_research_ai_pending']={
        'question':st.session_state.get('research_ai_question',''),
        'consent':st.session_state.get('research_ai_consent',False),
    }

@st.fragment
def render_research_chat(tables,version,store,actor):
    try:store.require_permission(actor,'use_tools')
    except PermissionError:st.warning('Your research-tool access is no longer active. Sign in again or contact the administrator.');return
    pending=st.session_state.pop('_research_ai_pending',None)
    st.subheader('Ask AI')
    st.caption('Ask questions about the results loaded in the three research tabs. Answers use this search snapshot, not a complete registry. Requested FDA PDF summaries can be read; no general web search is performed. Verify AI explanations against the source results.')
    if st.session_state.get('_research_ai_version')!=version:
        st.session_state['_research_ai_version']=version;st.session_state['_research_ai_messages']=[]
    key,model=settings()
    st.caption(('Gemini key loaded · ' if key else 'Gemini key missing · ')+model)
    if not key:
        st.info('Add GEMINI_API_KEY to Streamlit Secrets. Optional: ASK_AI_MODEL = "gemini-3.5-flash-lite". Save and reboot.');return
    if not tables:st.info('Run a regulatory search first to load records for Ask AI.');return
    st.caption('Available: '+' · '.join(t['name']+' ('+str(len(t['rows']))+' records)' for t in tables))
    st.caption('For document research, ask “Extract intended use, predicates and performance testing from the summary PDF for Kxxxxxx.” Up to three summaries are read per question. Name a loaded K-number to target a document.')
    with st.expander('Optional: upload a 510(k) summary PDF'):
        st.caption('Use this if the FDA link is unavailable. Upload a text-searchable PDF under 10 MB, then select Read uploaded PDF. Only extracted text is sent to Gemini when your question requests document research.')
        upload=st.file_uploader('Summary PDF',type=['pdf'],key='research_pdf_file')
        saved=st.session_state.get('_research_pdf_upload')
        digest=hashlib.sha256(upload.getvalue()).hexdigest() if upload else None
        if not saved or saved[0]!=digest:
            st.session_state.pop('_research_pdf_upload',None);saved=None
        if upload and st.button('Read uploaded PDF',key='research_pdf_read'):
            try:
                store.require_permission(actor,'use_tools')
                with st.spinner('Extracting PDF page text…'):document=extract_pdf(upload.getvalue())
                st.session_state['_research_pdf_upload']=(digest,document);saved=(digest,document)
                store.log_event(actor,'tool_use','Read uploaded FDA summary')
            except ValueError as exc:st.error(str(exc))
        if saved:
            st.success('PDF ready · '+str(saved[1]['read_pages'])+' of '+str(saved[1]['total_pages'])+' pages extracted.')
            for warning in saved[1]['warnings']:st.caption(warning)
    uploaded=saved[1] if saved else None
    messages=st.session_state.setdefault('_research_ai_messages',[])
    if st.button('Clear chat',key='research_ai_clear'):
        messages.clear()
    transcript=st.container()
    if pending and not pending['consent']:st.error('Tick the sharing checkbox before selecting Ask AI.')
    elif pending and not pending['question'].strip():st.info('Enter a question, then select Ask AI.')
    if pending and pending['consent'] and pending['question'].strip():
        question=pending['question']
        try:
            store.require_permission(actor,'use_tools')
            with st.spinner('Checking loaded records…'):
                result=ask(tables,question,messages,scope='Regulatory Research: current search results only. FDA clearances and CDSCO risk classifications/registration listings are distinct sources. No completeness or legal/clinical conclusions. Requested FDA summary PDF text may supplement the loaded metadata.',pdf_loader=lambda evidence,q:collect_pdf_evidence(tables,evidence,q,store,actor,uploaded),attached_pdf={'name':uploaded['name'],'total_pages':uploaded['total_pages']} if uploaded else None)
            store.require_permission(actor,'use_tools')
            store.log_event(actor,'tool_use','Ask AI')
            messages.extend([{'role':'user','text':question},{'role':'assistant','text':clean_answer(result['answer']),'evidence':result['evidence'],'pdf_documents':result.get('pdf_documents',[])}])
            messages[:]=messages[-12:]
            st.session_state['research_ai_question']=''
        except ValueError as exc:st.error(str(exc))
        except PermissionError:st.error('Your research-tool access changed. Sign in again before asking another question.');return
    # Submit consent and question together. A checkbox change must not depend
    # on a fragment rerun to enable a second widget with a new identity.
    with st.form('research_ai_composer',clear_on_submit=False):
        question=st.text_area('Your question',placeholder='Ask about devices, applicants, classifications or loaded results…',max_chars=2000,key='research_ai_question',height=100)
        consent=st.checkbox('Allow sending my questions and relevant loaded records to Google Gemini',key='research_ai_consent',help='This includes table headings, a small sample, query results, recent chat, and extracted PDF text when you request document research. Account credentials and API keys are not included in prompts.')
        st.form_submit_button('Ask AI',type='primary',on_click=queue_research_question)
    with transcript:
        for message_index,message in enumerate(messages):
            with st.chat_message(message['role']):
                st.markdown(clean_answer(message['text']) if message['role']=='assistant' else message['text'])
                for item in message.get('evidence',[]):
                    with st.expander('['+item['citation']+'] '+item['table']+' · '+str(item['matched_records'])+' matching records'):
                        st.caption('Showing '+str(item['shown_rows'])+' of '+str(item['result_rows'])+' result rows. Calculations use all matching records. Row references are positions within this loaded snapshot.')
                        st.json(item['query'],expanded=False)
                        st.dataframe(pd.DataFrame(item['records']),hide_index=True,width='stretch')
                for index,document in enumerate(message.get('pdf_documents',[])):
                    with st.expander('PDF source: '+document['name']+' · '+document['status']):
                        if document.get('url'):st.link_button('Open FDA summary PDF',document['url'])
                        for warning in document.get('warnings',[]):st.warning(warning)
                        pages=document.get('pages',[])
                        if pages:
                            st.caption(str(document['read_pages'])+' of '+str(document['total_pages'])+' pages extracted. Page numbers are PDF page positions; figures and image-only tables are not read. Check the original layout before relying on technical comparisons.')
                            page_number=st.selectbox('Review extracted page',[p['page'] for p in pages],key='pdf_page_'+str(message_index)+'_'+str(index)+'_'+document['sha256'][:10])
                            st.text(next(p['text'] for p in pages if p['page']==page_number) or 'No readable text on this page.')
