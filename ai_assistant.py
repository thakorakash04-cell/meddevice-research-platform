import requests
import json
import re
import pandas as pd
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

def call_gemini_api(
    prompt: str,
    system_instruction: str = "",
    api_key: str = "",
    model: str = "gemini-2.0-flash"
) -> Dict[str, Any]:
    """
    Calls Google Gemini REST API using standard requests.
    Supports fallback models if the primary model is unavailable.
    """
    if not api_key or not api_key.strip():
        return {
            "success": False,
            "error": "Gemini API key is required. Please enter your API key in the configuration bar above."
        }

    clean_key = api_key.strip()
    models_to_try = [model, "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash"]
    # Deduplicate while preserving order
    seen = set()
    models_to_try = [m for m in models_to_try if not (m in seen or seen.add(m))]

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.95,
            "maxOutputTokens": 2048,
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [
                {"text": system_instruction}
            ]
        }

    last_err = ""
    for mod in models_to_try:
        url = f"{GEMINI_API_BASE}/{mod}:generateContent?key={clean_key}"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text_response = parts[0].get("text", "")
                        return {
                            "success": True,
                            "text": text_response,
                            "model_used": mod,
                            "error": None
                        }
                return {
                    "success": False,
                    "error": "Gemini returned an empty response. Please try rephrasing."
                }
            else:
                err_data = {}
                try:
                    err_data = resp.json()
                except Exception:
                    pass
                msg = err_data.get("error", {}).get("message", f"HTTP {resp.status_code}: {resp.text[:200]}")
                last_err = f"Model {mod} Error: {msg}"
                # If invalid API key, don't try other models
                if resp.status_code in [400, 403] and ("API_KEY_INVALID" in msg or "API key not valid" in msg):
                    return {
                        "success": False,
                        "error": "Invalid Gemini API Key. Please verify your Google AI Studio API key."
                    }
        except requests.exceptions.Timeout:
            last_err = f"Request timed out connecting to Gemini ({mod})."
        except Exception as e:
            last_err = str(e)

    return {
        "success": False,
        "error": f"Failed to communicate with Gemini API. Details: {last_err}"
    }


def retrieve_context_from_dataframes(
    query: str,
    df_risk: pd.DataFrame,
    df_app: pd.DataFrame,
    max_risk: int = 15,
    max_app: int = 25
) -> str:
    """
    Performs fast token-based & substring search across in-memory CDSCO DataFrames
    to extract grounded context for Gemini LLM.
    """
    if not query or not query.strip():
        return ""

    tokens = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 2]
    # Remove common conversational stop words
    stop_words = {"what", "which", "show", "tell", "give", "list", "find", "devices", "device", "india", "cdsco", "details", "info", "information", "about", "with", "from", "does", "have", "many"}
    search_tokens = [t for t in tokens if t not in stop_words] or tokens

    risk_matches = pd.DataFrame()
    app_matches = pd.DataFrame()

    # 1. Search Risk DB
    if df_risk is not None and not df_risk.empty:
        risk_cols = [c for c in ["medical_device_name", "devicename", "device_name", "intended_use", "str_intended_use", "grouping_name", "device_category", "risk_classification_under_mdr_2017"] if c in df_risk.columns]
        if risk_cols:
            mask = pd.Series(False, index=df_risk.index)
            # Try exact query substring first
            for col in risk_cols:
                mask |= df_risk[col].astype(str).str.contains(query, case=False, na=False)
            # Then token matches
            for t in search_tokens[:3]:
                for col in ["medical_device_name", "devicename", "intended_use", "device_category"]:
                    if col in df_risk.columns:
                        mask |= df_risk[col].astype(str).str.contains(t, case=False, na=False)
            risk_matches = df_risk[mask].head(max_risk)

    # 2. Search Approved Registrations DB
    if df_app is not None and not df_app.empty:
        app_cols = [c for c in ["devicename", "brandname", "modelname", "address", "premises_add", "str_intended_use", "str_licence_no", "instname", "classname"] if c in df_app.columns]
        if app_cols:
            mask = pd.Series(False, index=df_app.index)
            for col in app_cols:
                mask |= df_app[col].astype(str).str.contains(query, case=False, na=False)
            for t in search_tokens[:3]:
                for col in ["devicename", "brandname", "address"]:
                    if col in df_app.columns:
                        mask |= df_app[col].astype(str).str.contains(t, case=False, na=False)
            app_matches = df_app[mask].head(max_app)

    # Build markdown context
    context_sections = []

    if not risk_matches.empty:
        context_sections.append("### OFFICIAL CDSCO RISK CLASSIFICATION RECORDS (Step 1 Database):")
        for idx, row in risk_matches.iterrows():
            dname = row.get("medical_device_name") or row.get("devicename") or row.get("device_name", "N/A")
            cname = row.get("risk_classification_under_mdr_2017") or row.get("class_name") or row.get("classname", "N/A")
            cat = row.get("device_category") or row.get("grouping_name", "N/A")
            use = str(row.get("intended_use") or row.get("str_intended_use") or "")[:200]
            context_sections.append(f"- **Device:** {dname} | **Class:** {cname} | **Category:** {cat} | **Intended Use:** {use}")

    if not app_matches.empty:
        context_sections.append("\n### OFFICIAL CDSCO APPROVED REGISTRATIONS (Step 2 Database - Manufacturers & Importers):")
        for idx, row in app_matches.iterrows():
            dname = row.get("devicename", "N/A")
            role = row.get("role", "N/A")
            addr = str(row.get("address", "N/A")).replace("\n", ", ")[:120]
            lic = row.get("str_licence_no", "N/A")
            cls = row.get("classname", "N/A")
            brand = row.get("brandname", "N/A")
            auth = row.get("instname", "N/A")
            context_sections.append(f"- **Device:** {dname} | **Role:** {role} | **Company/Address:** {addr} | **License:** {lic} | **Class:** {cls} | **Brand:** {brand} | **Authority:** {auth}")

    if not context_sections:
        return "No direct keyword matches found in local CDSCO records for this specific query."

    return "\n".join(context_sections)


def extract_company_data(
    company_query: str,
    df_app: pd.DataFrame
) -> Dict[str, Any]:
    """
    Extracts all records, licenses, roles, classes, and facilities for a company
    from the 105,000+ CDSCO approved registrations dataset.
    """
    if df_app is None or df_app.empty or not company_query or not company_query.strip():
        return {
            "found": False,
            "company_name": company_query,
            "total_records": 0,
            "records": pd.DataFrame()
        }

    q = company_query.strip()
    mask = pd.Series(False, index=df_app.index)
    if "address" in df_app.columns:
        mask |= df_app["address"].astype(str).str.contains(q, case=False, na=False)
    if "premises_add" in df_app.columns:
        mask |= df_app["premises_add"].astype(str).str.contains(q, case=False, na=False)
    if "brandname" in df_app.columns:
        mask |= df_app["brandname"].astype(str).str.contains(q, case=False, na=False)

    matching_df = df_app[mask].copy()

    if matching_df.empty:
        return {
            "found": False,
            "company_name": q,
            "total_records": 0,
            "records": pd.DataFrame()
        }

    # Extract Key Statistics
    total_records = len(matching_df)
    role_counts = matching_df["role"].value_counts().to_dict() if "role" in matching_df.columns else {}
    mfg_count = role_counts.get("Manufacturer", 0)
    imp_count = role_counts.get("Importer", 0)

    unique_licenses = sorted(list(set(matching_df["str_licence_no"].dropna().astype(str).unique()))) if "str_licence_no" in matching_df.columns else []
    unique_classes = sorted(list(set(matching_df["classname"].dropna().astype(str).unique()))) if "classname" in matching_df.columns else []
    unique_authorities = sorted(list(set(matching_df["instname"].dropna().astype(str).unique()))) if "instname" in matching_df.columns else []
    unique_brands = sorted(list(set(matching_df["brandname"].dropna().astype(str).unique()))) if "brandname" in matching_df.columns else []

    # Extract distinct company titles
    addresses = matching_df["address"].dropna().astype(str).tolist()
    primary_name = q
    if addresses:
        first_addr = addresses[0]
        primary_name = first_addr.split("\n")[0] if "\n" in first_addr else first_addr[:60]

    # Sample top devices
    sample_cols = [c for c in ["devicename", "role", "str_licence_no", "classname", "brandname", "modelname", "instname", "address"] if c in matching_df.columns]
    sample_records = matching_df[sample_cols].head(30).to_dict(orient="records")

    return {
        "found": True,
        "company_name": primary_name,
        "search_query": q,
        "total_records": total_records,
        "mfg_count": mfg_count,
        "imp_count": imp_count,
        "unique_licenses": unique_licenses,
        "unique_classes": unique_classes,
        "unique_authorities": unique_authorities,
        "unique_brands": [b for b in unique_brands if b and b.strip() != "-" and b.strip() != "null"][:20],
        "sample_records": sample_records,
        "records_df": matching_df
    }


def generate_company_ai_dossier(
    company_data: Dict[str, Any],
    api_key: str
) -> Dict[str, Any]:
    """
    Uses Google Gemini to generate an in-depth regulatory intelligence profile
    and market positioning dossier for a company.
    """
    if not company_data.get("found"):
        return {
            "success": False,
            "error": f"No official CDSCO records found for '{company_data.get('company_name', 'company')}'. Try another name."
        }

    c_name = company_data["company_name"]
    total = company_data["total_records"]
    mfg = company_data["mfg_count"]
    imp = company_data["imp_count"]
    lics = ", ".join(company_data["unique_licenses"][:8])
    classes = ", ".join(company_data["unique_classes"])
    auths = ", ".join(company_data["unique_authorities"][:5])
    brands = ", ".join(company_data["unique_brands"][:15])

    sample_devices_txt = ""
    for r in company_data["sample_records"][:15]:
        sample_devices_txt += f"- **{r.get('devicename')}** | Role: {r.get('role')} | Class: {r.get('classname')} | Brand: {r.get('brandname')} | License: {r.get('str_licence_no')}\n"

    system_instruction = (
        "You are an expert Medical Device Regulatory Affairs & Market Intelligence Consultant specializing in CDSCO (India) "
        "and US FDA medical device regulations. Provide authoritative, concise, data-driven executive reports grounded strictly "
        "in official government filing records."
    )

    prompt = f"""
Generate an Executive Regulatory & Market Intelligence Dossier for **{c_name}** based on the following verified CDSCO government registration data:

### VERIFIED CDSCO FILINGS OVERVIEW:
- **Company Name / Entity:** {c_name}
- **Total Registered Filings:** {total:,}
- **Domestic Manufacturing Filings (Form MD-3/5/7/8/28):** {mfg:,}
- **Importer Registrations (Form MD-14/15):** {imp:,}
- **Device Risk Classification Range:** {classes or 'Not Specified'}
- **Official License Numbers:** {lics or 'N/A'}
- **Key Issuing State / Central Authorities:** {auths or 'N/A'}
- **Registered Brands / Trademarks:** {brands or 'N/A'}

### SAMPLE REGISTERED DEVICES CATALOG:
{sample_devices_txt}

---
Please produce a structured regulatory intelligence report covering:
1. **🏢 Executive Profile & Indian Market Footprint**: Summarize whether this entity operates primarily as a domestic manufacturer, an importer, or a hybrid player.
2. **⚖️ Regulatory Risk Spectrum & Compliance**: Analyze their device class distribution (Class A, B, C, D) and regulatory complexity.
3. **📦 Core Product Portfolio & Clinical Focus**: Highlight their primary medical specialty segments and notable brands/devices.
4. **🏛️ Licensing & Governance Footprint**: Discuss issuing authorities (State Licensing Authority vs Central CDSCO) and active license scope.
5. **💡 Strategic Regulatory Insights**: Key takeaways for procurement officers, regulatory consultants, and industry competitors.

Format clearly with professional markdown, headers, bullet points, and highlight metrics.
"""

    return call_gemini_api(prompt, system_instruction=system_instruction, api_key=api_key)


def answer_ai_chat_query(
    user_query: str,
    df_risk: pd.DataFrame,
    df_app: pd.DataFrame,
    fda_results: Optional[List[Dict[str, Any]]] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    api_key: str = ""
) -> Dict[str, Any]:
    """
    Answers user regulatory questions grounded in loaded CDSCO and FDA data.
    """
    context = retrieve_context_from_dataframes(user_query, df_risk, df_app)

    fda_context = ""
    if fda_results:
        fda_context = "\n### US FDA 510(k) CLEARANCE RECORDS (Live openFDA Query):\n"
        for r in fda_results[:10]:
            fda_context += f"- **Device:** {r.get('device_name')} | **Applicant:** {r.get('applicant')} | **510(k) #:** {r.get('k_number')} | **Decision Date:** {r.get('decision_date')}\n"

    system_instruction = (
        "You are 'MedDevice AI', an expert regulatory assistant specializing in Indian CDSCO (Medical Device Rules 2017) "
        "and US FDA 510(k) regulations. Answer user questions authoritatively and concisely. "
        "Ground your response strictly in the provided verified government datasets (CDSCO Risk Classification, CDSCO Approved Registrations, and US FDA 510k). "
        "Always cite specific device classes (Class A, B, C, D), license numbers, applicant/manufacturer names, or source portals when available in the context."
    )

    # Build prompt with conversation history context if available
    history_txt = ""
    if chat_history:
        recent_turns = chat_history[-4:]
        history_txt = "### RECENT CONVERSATION CONTEXT:\n"
        for msg in recent_turns:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_txt += f"{role}: {msg.get('content', '')}\n"
        history_txt += "\n"

    prompt = f"""
{history_txt}### GROUND TRUTH GOVERNMENT DATA CONTEXT:
{context}
{fda_context}

### USER QUESTION:
{user_query}

Answer the question accurately using the data above. If specific registrations, companies, classes, or licenses are found in the data, list and explain them clearly. If the data does not contain the answer, state that clearly and provide standard CDSCO / US FDA regulatory guidance.
"""

    return call_gemini_api(prompt, system_instruction=system_instruction, api_key=api_key)
