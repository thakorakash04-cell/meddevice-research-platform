import streamlit as st
import pandas as pd
import ai_assistant

def render_ai_chatbot(df_risk, df_app):
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.markdown("<div class='card card-blue'><h3 style='color:#0f172a;margin:0'>🤖 AI Regulatory Assistant & Company Explorer</h3></div>", unsafe_allow_html=True)

    # API Key Config
    api_key = st.secrets.get("GEMINI_API_KEY", "") if "GEMINI_API_KEY" in st.secrets else ""
    if not api_key:
        api_key = st.session_state.get("gemini_user_key", "")

    with st.expander("⚙️ AI Configuration & Tools", expanded=False):
        st.markdown("**Google Gemini API Key Config**")
        if api_key:
            st.success("✅ **Gemini API Key Confirmed.** Systems are ready.")
        else:
            in_key = st.text_input("Enter your Gemini API Key to enable AI features:", type="password", key="gemini_user_key")
            if in_key:
                st.rerun()

    tab1, tab2 = st.tabs(["💬 Regulatory Chatbot", "🏢 Company Deep-Dive Explorer"])

    with tab1:
        st.markdown("Ask anything about medical device regulations, device classifications, or specific manufacturers in India.")

        # Display chat messages
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Sample prompt chips
        if not st.session_state.messages:
            c1, c2, c3 = st.columns(3)
            if c1.button("📌 Class C Ablation guidelines"):
                st.session_state.chat_query = "What are the CDSCO requirements and risk classifications for Class C Ablation devices?"
            if c2.button("🏭 Compare Stent Importers"):
                st.session_state.chat_query = "List me the top importers vs manufacturers of Cardiac Stents in India."
            if c3.button("🦷 Orthodontic / Dental Regs"):
                st.session_state.chat_query = "Show me the classification and approved manufacturers for dental implants in India."

        prompt = st.chat_input("Type your regulatory query here...", key="chat_input")
        fallback_prompt = st.session_state.pop("chat_query", None)

        active_prompt = prompt or fallback_prompt

        if active_prompt:
            st.session_state.messages.append({"role": "user", "content": active_prompt})
            with st.chat_message("user"):
                st.markdown(active_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing CDSCO & FDA Databases..."):
                    res = ai_assistant.answer_ai_chat_query(
                        active_prompt,
                        df_risk,
                        df_app,
                        fda_results=None,
                        chat_history=st.session_state.messages[:-1],
                        api_key=api_key
                    )

                if res.get("success"):
                    st.markdown(res["text"])
                    st.session_state.messages.append({"role": "assistant", "content": res["text"]})
                else:
                    st.error(res.get("error", "Error connecting to AI."))

    with tab2:
        st.markdown("### 🏢 Market Intelligence: Company Deep-Dive")
        st.markdown("Search for any medical device company (e.g., *Meril*, *Abbott*, *Wuhan Dimed*, *Medtronic*) to view their complete registered Indian portfolio and generate an expert AI overview.")

        cq = st.text_input("Target Manufacturer / Importer Name:", placeholder="e.g. Meril Life Sciences")
        if cq:
            with st.spinner("Extracting company filings..."):
                c_data = ai_assistant.extract_company_data(cq, df_app)

            if not c_data.get("found"):
                st.warning(f"No registrations found containing '{cq}'.")
            else:
                st.success(f"Verified CDSCO Filings for **{c_data['company_name']}**")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total CDSCO Filings", c_data["total_records"])
                m2.metric("Manufacturing Licenses", c_data["mfg_count"])
                m3.metric("Import Licenses", c_data["imp_count"])
                m4.metric("Unique Licenses", len(c_data["unique_licenses"]))

                if st.button("🤖 Generate AI Executive Company Profile", type="primary"):
                    with st.spinner("Generating Market Intelligence Report..."):
                        dossier = ai_assistant.generate_company_ai_dossier(c_data, api_key=api_key)
                        if dossier.get("success"):
                            st.markdown("---")
                            st.markdown("### 📊 Market Intelligence Report")
                            st.markdown(dossier["text"])
                            st.markdown("---")
                        else:
                            st.error(dossier.get("error", "Failed to generate report."))

                with st.expander(f"📋 View All {c_data['total_records']} Filings Data"):
                    st.dataframe(c_data["records_df"], use_container_width=True)
