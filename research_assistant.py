"""Session-private chat over the current research results, isolated from search reruns."""
import pandas as pd
import streamlit as st
from grounded_ai import ask,settings

@st.fragment
def render_research_chat(tables,version,store,actor):
    store.require_permission(actor,'use_tools')
    st.subheader('Ask AI')
    st.caption('Ask questions about the results loaded in the three research tabs. Answers use this search snapshot, not a complete registry or a fresh web search. Verify AI explanations against the source results.')
    if st.session_state.get('_research_ai_version')!=version:
        st.session_state['_research_ai_version']=version;st.session_state['_research_ai_messages']=[]
    key,model=settings()
    st.caption(('Gemini key loaded · ' if key else 'Gemini key missing · ')+model)
    if not key:
        st.info('Add GEMINI_API_KEY to Streamlit Secrets. Optional: ASK_AI_MODEL = "gemini-3.5-flash-lite". Save and reboot.');return
    if not tables:st.info('Run a regulatory search first to load records for Ask AI.');return
    st.caption('Available: '+' · '.join(t['name']+' ('+str(len(t['rows']))+' records)' for t in tables))
    messages=st.session_state.setdefault('_research_ai_messages',[])
    consent=st.checkbox('Allow sending my questions and relevant loaded records to Google Gemini',key='research_ai_consent',help='This includes table headings, a small sample, selected query results and recent chat. Account credentials and API keys are not included in prompts.')
    if st.button('Clear chat',key='research_ai_clear'):
        messages.clear()
    transcript=st.container()
    question=st.chat_input('Ask about devices, applicants, classifications or loaded results…',max_chars=2000,disabled=not consent,key='research_ai_question')
    if question:
        if not consent:st.error('Enable sharing with Google Gemini before asking.');return
        try:
            store.require_permission(actor,'use_tools')
            with st.spinner('Checking loaded records…'):
                result=ask(tables,question,messages,scope='Regulatory Research: current search results only. FDA clearances and CDSCO risk classifications/registration listings are distinct sources. No completeness or legal/clinical conclusions.')
            store.require_permission(actor,'use_tools')
            store.log_event(actor,'tool_use','Ask AI')
            messages.extend([{'role':'user','text':question},{'role':'assistant','text':result['answer'],'evidence':result['evidence']}])
            messages[:]=messages[-12:]
        except ValueError as exc:st.error(str(exc))
    with transcript:
        for message in messages:
            with st.chat_message(message['role']):
                st.markdown(message['text'])
                for item in message.get('evidence',[]):
                    with st.expander('['+item['citation']+'] '+item['table']+' · '+str(item['matched_records'])+' matching records'):
                        st.caption('Showing '+str(item['shown_rows'])+' of '+str(item['result_rows'])+' result rows. Calculations use all matching records. Row references are positions within this loaded snapshot.')
                        st.json(item['query'],expanded=False)
                        st.dataframe(pd.DataFrame(item['records']),hide_index=True,width='stretch')
