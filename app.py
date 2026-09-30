import streamlit as st
import requests
import hashlib
from datetime import datetime, timedelta, timezone
import pandas as pd
from urllib.parse import quote
from collections import defaultdict
import urllib3
import json
import os
import re
import io

urllib3.disable_warnings()

st.set_page_config(
    page_title="MedDevice Research Platform",
    layout="wide",
    page_icon="⚕️",
    initial_sidebar_state="expanded"
)

# ─── BASE DIRECTORY FOR PARQUET FILES ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── SESSION STATE INITIALIZATION ─────────────────────────────────────────────
if 'filter_applied' not in st.session_state:
    st.session_state.filter_applied = {}
if 'search_executed' not in st.session_state:
    st.session_state.search_executed = False

# ─── ENHANCED GLOBAL STYLES ───────────────────────────────────────────────────
st.markdown("""
<style>
/* App Main View */
[data-testid="stAppViewContainer"] { background: #f8fafc; }

/* ─── SIDEBAR STYLING ─── */
[data-testid="stSidebar"] {
    background-color: #f1f5f9;
    padding-top: 1rem;
}

/* Sidebar Headings */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {
    color: #0f172a !important;
    font-weight: 700;
}

/* Sidebar Input Labels */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stWidgetLabel p {
    color: #0f172a !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.3px;
    margin-bottom: 4px;
}

/* Search Text Input Boxes */
[data-testid="stSidebar"] input[type="text"] {
    background-color: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] input[type="text"]::placeholder {
    color: #64748b !important;
}
[data-testid="stSidebar"] input[type="text"]:focus {
    border-color: #0284c7 !important;
    box-shadow: 0 0 0 1px #0284c7 !important;
    color: #0f172a !important;
}

/* Selectbox & Multiselect Field Containers */
[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] * {
    color: #0f172a !important;
}

/* Multiselect Device Category Selected Chips */
[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    padding: 3px 8px !important;
}
[data-testid="stSidebar"] span[data-baseweb="tag"] span {
    color: #ffffff !important;
}

/* Dropdown Menu Popup */
div[data-baseweb="popover"],
div[data-baseweb="menu"] {
    background-color: #ffffff !important;
    border-radius: 8px !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: 0 10px 25px rgba(0,0,0,0.15) !important;
}
div[data-baseweb="popover"] div[role="option"],
div[data-baseweb="menu"] div[role="option"] {
    color: #0f172a !important;
    font-weight: 500 !important;
    background-color: #ffffff !important;
    padding: 8px 12px !important;
}
div[data-baseweb="popover"] div[role="option"]:hover,
div[data-baseweb="menu"] div[role="option"]:hover {
    background-color: #e0f2fe !important;
    color: #0369a1 !important;
}

/* Primary Action Button */
[data-testid="stSidebar"] button[kind="primary"] {
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 700 !important;
    padding: 10px !important;
    margin-top: 8px;
}
[data-testid="stSidebar"] button[kind="primary"]:hover {
    background-color: #0369a1 !important;
}

/* ─── CARD STYLES ─── */
.card {
    background: #ffffff;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.card-blue { border-left: 4px solid #0284c7; }
.card-green { border-left: 4px solid #10b981; }

.audit-trace {
    background: #0f172a;
    color: #38bdf8;
    border-radius: 6px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 11px;
    margin-top: 6px;
}

/* ─── EXCEL-STYLE FILTER PANEL ─── */
.filter-panel {
    background: #f0f4f8;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 14px;
    margin-bottom: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
}

.filter-title {
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 12px;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.filter-success {
    background: #f0fdf4;
    color: #16a34a;
    border: 1px solid #86efac;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
    margin-top: 8px;
}

</style>
""", unsafe_allow_html=True)

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def to_excel_bytes(df, sheet_name="Results"):
    output = io.BytesIO()
    export_df = df.head(10000)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()

def get_fda_pmn_link(k): 
    return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={k}" if k else None

def get_fda_pdf_link(k):
    if not k or not k.startswith("K"): 
        return None
    yr = k[1:3]
    folder = "pdf" + (yr[1] if yr.startswith("0") else yr)
    return f"https://www.accessdata.fda.gov/cdrh_docs/{folder}/{k}.pdf"

# ─── REGULATORY SYNONYMS DICTIONARY ───────────────────────────────────────────
SYNONYMS = {
    'stent': ['stent', 'scaffold', 'endoprosthesis', 'graft'],
    'bandage': ['bandage', 'dressing', 'gauze', 'tape', 'plaster', 'crepe', 'cohesive'],
    'ablation': ['ablation', 'radiofrequency', 'cryoablation', 'microwave', 'electrosurgical', 'electrode', 'laser ablation'],
    'catheter': ['catheter', 'cannula', 'sheath', 'balloon', 'dilatation', 'guiding'],
    'pacemaker': ['pacemaker', 'pulse generator', 'icd', 'cardiac resynchronization', 'pacing'],
    'implant': ['implant', 'prosthesis', 'fixation', 'screw', 'plate', 'nail', 'joint'],
    'mri': ['mri', 'magnetic resonance', 'scanner'],
    'glove': ['glove', 'examination', 'surgical glove', 'latex', 'nitrile'],
    'syringe': ['syringe', 'needle', 'hypodermic', 'auto-disable', 'injector'],
    'mask': ['mask', 'respirator', 'surgical mask', 'n95', 'face mask'],
    'valve': ['valve', 'heart valve', 'tavr', 'aortic valve', 'mitral'],
    'laser': ['laser', 'diode laser', 'holmium', 'nd:yag', 'argon laser', 'excimer', 'laser system', 'photocoagulator', 'laser fiber']
}

def expand_terms(query_str, enable_synonyms=True):
    if not query_str.strip():
        return []
    q = query_str.lower().strip()
    terms = [q]
    if enable_synonyms:
        words = re.findall(r'\w+', q)
        for w in words:
            for k, syn_list in SYNONYMS.items():
                if k in w or w in k:
                    terms.extend(syn_list)
    return list(set(terms))

def robust_dataframe_search(df, query, target_columns, ai_mode=True, match_mode='all_words'):
    if df.empty or not query.strip():
        return df

    q = query.lower().strip()
    words = [w for w in re.findall(r'\w+', q) if len(w) > 0]
    if not words:
        return df

    corpus = df[target_columns[0]].astype(str).fillna('')
    for col in target_columns[1:]:
        if col in df.columns:
            corpus = corpus + ' ' + df[col].astype(str).fillna('')
    corpus = corpus.str.lower()

    if not ai_mode:
        if match_mode == 'exact':
            mask = corpus.str.contains(q, regex=False, na=False)
        elif match_mode == 'any_words':
            masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
            mask = pd.concat(masks, axis=1).any(axis=1) if masks else pd.Series(True, index=df.index)
        else:
            masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
            mask = pd.concat(masks, axis=1).all(axis=1) if masks else pd.Series(True, index=df.index)
        return df[mask]
    else:
        exact_masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
        exact_match_mask = pd.concat(exact_masks, axis=1).all(axis=1) if exact_masks else pd.Series(False, index=df.index)

        synonym_terms = set()
        for w in words:
            for k, syn_list in SYNONYMS.items():
                if k in w or w in k:
                    synonym_terms.update(syn_list)

        syn_masks = [corpus.str.contains(t, regex=False, na=False) for t in synonym_terms]
        syn_match_mask = pd.concat(syn_masks, axis=1).any(axis=1) if syn_masks else pd.Series(False, index=df.index)

        combined_mask = exact_match_mask | syn_match_mask
        matched_df = df[combined_mask].copy()

        if not matched_df.empty:
            is_exact = exact_match_mask.loc[matched_df.index]
            matched_df['_rank'] = is_exact.map({True: 0, False: 1})
            matched_df = matched_df.sort_values(by='_rank').drop(columns=['_rank'])

        return matched_df

# ─── FIXED EXCEL-STYLE COLUMN FILTER FUNCTION ────────────────────────────────
def excel_style_filter(df, filter_key_prefix=""):
    """Excel-style column filters that actually work"""
    if df.empty:
        return df
    
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown('<div class="filter-title">🔍 Column-Level Filters (Excel-Style)</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
    
    with col1:
        filter_column = st.selectbox(
            "Select Column", 
            options=list(df.columns),
            key=f"fcol_{filter_key_prefix}"
        )
    
    with col2:
        filter_mode = st.selectbox(
            "Filter Type", 
            options=["Text Contains", "Exact Match", "From Dropdown"],
            key=f"fmode_{filter_key_prefix}"
        )
    
    filtered_df = df.copy()
    filter_applied = False
    
    try:
        # TEXT CONTAINS
        if filter_mode == "Text Contains":
            with col3:
                filter_text = st.text_input(
                    "Enter text", 
                    placeholder="e.g., Laser",
                    key=f"ftext_{filter_key_prefix}"
                )
            
            with col4:
                if st.button("🔎", key=f"fbtn_{filter_key_prefix}", help="Apply filter"):
                    if filter_text.strip():
                        filtered_df = filtered_df[
                            filtered_df[filter_column].astype(str).str.lower().str.contains(
                                filter_text.lower(), regex=False, na=False
                            )
                        ]
                        filter_applied = True
                        st.session_state.filter_applied[filter_key_prefix] = f"Text contains '{filter_text}'"
            
            with col5:
                if st.button("✕", key=f"fclear_{filter_key_prefix}", help="Clear filter"):
                    st.session_state.filter_applied.pop(filter_key_prefix, None)
                    st.rerun()
        
        # EXACT MATCH
        elif filter_mode == "Exact Match":
            with col3:
                filter_value = st.text_input(
                    "Exact value", 
                    placeholder="Type exactly",
                    key=f"fexact_{filter_key_prefix}"
                )
            
            with col4:
                if st.button("🔎", key=f"fexactbtn_{filter_key_prefix}", help="Apply filter"):
                    if filter_value.strip():
                        filtered_df = filtered_df[
                            filtered_df[filter_column].astype(str).str.strip() == filter_value.strip()
                        ]
                        filter_applied = True
                        st.session_state.filter_applied[filter_key_prefix] = f"Exact match '{filter_value}'"
            
            with col5:
                if st.button("✕", key=f"fclearexa_{filter_key_prefix}", help="Clear filter"):
                    st.session_state.filter_applied.pop(filter_key_prefix, None)
                    st.rerun()
        
        # DROPDOWN
        else:  # From Dropdown
            unique_vals = sorted(df[filter_column].dropna().astype(str).unique().tolist())[:50]
            
            with col3:
                selected_values = st.multiselect(
                    "Select values", 
                    options=unique_vals,
                    key=f"fdrop_{filter_key_prefix}"
                )
            
            with col4:
                if st.button("🔎", key=f"fdropbtn_{filter_key_prefix}", help="Apply filter"):
                    if selected_values:
                        filtered_df = filtered_df[
                            filtered_df[filter_column].astype(str).isin(selected_values)
                        ]
                        filter_applied = True
                        st.session_state.filter_applied[filter_key_prefix] = f"Selected {len(selected_values)} values"
            
            with col5:
                if st.button("✕", key=f"fcleardrop_{filter_key_prefix}", help="Clear filter"):
                    st.session_state.filter_applied.pop(filter_key_prefix, None)
                    st.rerun()
        
        # Show filter status
        if filter_key_prefix in st.session_state.filter_applied:
            st.markdown(f"<div class='filter-success'>✅ Filter applied: {st.session_state.filter_applied[filter_key_prefix]}</div>", 
                       unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Filter error: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    return filtered_df

# ─── DATA LOADERS ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_cdsco_combined_risk():
    p_path = os.path.join(BASE_DIR, "cdsco_combined_risk.parquet")
    if os.path.exists(p_path):
        df = pd.read_parquet(p_path)
        with open(p_path, "rb") as f:
            h = sha256(f.read())
        return {"data": df, "total": len(df), "hash": h, "timestamp": datetime.now().isoformat()}
    return {"data": pd.DataFrame(), "total": 0, "hash": "", "timestamp": datetime.now().isoformat()}

@st.cache_data(ttl=3600, show_spinner=False)
def load_cdsco_approved_devices():
    p_path = os.path.join(BASE_DIR, "cdsco_approved_devices.parquet")
    if os.path.exists(p_path):
        df = pd.read_parquet(p_path)
        with open(p_path, "rb") as f:
            h = sha256(f.read())
        return {"data": df, "total": len(df), "hash": h, "timestamp": datetime.now().isoformat()}
    return {"data": pd.DataFrame(), "total": 0, "hash": "", "timestamp": datetime.now().isoformat()}

risk_payload = load_cdsco_combined_risk()
approved_payload = load_cdsco_approved_devices()

UTC = timezone.utc

def get_cdsco_sync_metadata():
    IST = timezone(timedelta(hours=5, minutes=30))
    sync_info = {
        "last_updated": "Loading...",
        "status": "Active (Daily Auto-Sync)",
        "schedule": "Every Day at 02:00 AM UTC (07:30 AM IST)",
        "risk_records": len(risk_payload["data"]) if not risk_payload["data"].empty else 0,
        "approved_records": len(approved_payload["data"]) if not approved_payload["data"].empty else 0,
        "risk_delta": 0,
        "approved_delta": 0
    }
    meta_path = os.path.join(BASE_DIR, "cdsco_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
                dt = datetime.fromisoformat(meta.get("last_updated"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                dt_ist = dt.astimezone(IST)
                sync_info["last_updated"] = dt_ist.strftime("%d-%b-%Y %H:%M:%S IST")
                sync_info["risk_delta"] = int(meta.get("risk_delta", 0) or 0)
                sync_info["approved_delta"] = int(meta.get("approved_delta", 0) or 0)
        except Exception:
            pass
    return sync_info

sync_meta = get_cdsco_sync_metadata()

def search_us_fda(device_query: str, applicant: str, limit=20, ai_mode=True):
    search_parts = []
    if device_query.strip():
        dev_clean = device_query.strip()
        words = re.findall(r'\w+', dev_clean)
        if ai_mode:
            terms = expand_terms(dev_clean, enable_synonyms=True)
            term_str = " OR ".join([f'"{t}"' for t in terms[:6]])
            search_parts.append(f"device_name:({term_str})")
        else:
            if len(words) > 1:
                dev_subparts = [f'device_name:"{w}"' for w in words]
                search_parts.append(f"({' AND '.join(dev_subparts)})")
            else:
                search_parts.append(f'device_name:"{dev_clean}"')

    if applicant.strip():
        app_clean = applicant.strip()
        app_words = re.findall(r'\w+', app_clean)
        if len(app_words) > 1:
            app_subparts = [f'applicant:"{w}"' for w in app_words]
            search_parts.append(f"({' AND '.join(app_subparts)})")
        else:
            search_parts.append(f'applicant:"{app_clean}"')

    raw_query = " AND ".join(search_parts)
    url = f"https://api.fda.gov/device/510k.json?search={quote(raw_query)}&limit={limit}"
    try:
        resp = requests.get(url, timeout=15)
        h = sha256(resp.content)
        if resp.status_code == 200:
            data = resp.json()
            return {"status":"success","hash":h,"url":url,"query":raw_query,"timestamp":datetime.now().isoformat(),
                    "total":data.get("meta",{}).get("results",{}).get("total",0),"results":data.get("results",[])}
        return {"status":"error","message":f"HTTP {resp.status_code}","hash":h,"url":url,"timestamp":datetime.now().isoformat()}
    except Exception as e:
        return {"status":"error","message":str(e)}

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚕️ Regulatory Intelligence")

    st.markdown(f"""
    <div style="background:#1e293b; border-radius:8px; padding:12px; border:1px solid #334155; margin-bottom:12px;">
        <div style="color:#10b981; font-weight:700; font-size:12px; display:flex; align-items:center; gap:6px;">
            <span>🟢</span> CDSCO DAILY AUTO-SYNC ACTIVE
        </div>
        <div style="color:#f8fafc; font-size:12px; margin-top:6px;"><b>Last Data Fetched:</b><br><span style="color:#38bdf8;">{sync_meta['last_updated']}</span></div>
        <div style="color:#94a3b8; font-size:11px; margin-top:4px;"><b>Schedule:</b> {sync_meta['schedule']}</div>
        <div style="color:#94a3b8; font-size:11px; margin-top:2px;"><b>Verified Scope:</b> {sync_meta['risk_records']:,} Risk Classes | {sync_meta['approved_records']:,} Registrations</div>
        <div style="color:#10b981; font-size:11px; margin-top:2px;"><b>New This Run:</b> +{sync_meta['risk_delta']:,} Risk Classes | +{sync_meta['approved_delta']:,} Registrations</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    jurisdiction = st.selectbox("Regulatory Target", ["Dual (US FDA + CDSCO)", "CDSCO India Only", "US FDA Only"])
    st.markdown("---")
    device_name = st.text_input("Product / Device Name", value="Laser", placeholder="e.g. Laser, Diode, Stent")
    applicant_name = st.text_input("Manufacturer / Importer", value="", placeholder="e.g. Meril, Abbott")

    st.markdown("---")
    st.markdown("**🤖 AI Search & Engine Controls**")

    ai_search_toggle = st.toggle(
        "🤖 AI-Assisted Smart Search",
        value=True,
        help="ON: AI semantic synonyms | OFF: Exact keyword matching"
    )

    if not ai_search_toggle:
        match_mode = st.selectbox(
            "Strict Keyword Matching Mode",
            ["Match All Words (AND)", "Exact Phrase Match", "Match Any Word (OR)"],
            index=0
        )
        mode_map = {
            "Match All Words (AND)": "all_words",
            "Exact Phrase Match": "exact",
            "Match Any Word (OR)": "any_words"
        }
        selected_mode = mode_map[match_mode]
    else:
        selected_mode = "all_words"
        st.caption("✨ AI Search Active: Expanding synonyms with relevance ranking")

    search_scope = st.selectbox(
        "Search Field Scope",
        ["All Fields (Product, Brand, Models, Intended Use, License)", "Product Name Only", "Company Name Only"],
        index=0
    )

    if not risk_payload["data"].empty and "device_category" in risk_payload["data"].columns:
        all_categories = sorted(list(set(risk_payload["data"]["device_category"].dropna().astype(str).str.strip())))
    else:
        all_categories = ["Cardiovascular", "Orthopedic", "General Hospital", "Electromechanical", "IVD"]

    st.markdown("---")
    st.markdown("**CDSCO Filters**")
    cdsco_role = st.selectbox("Applicant Role Filter", ["Both (Manufacturer + Importer)", "Manufacturer Only", "Importer Only"])
    selected_categories = st.multiselect("Device Categories Filter", all_categories, default=all_categories)

    search_btn = st.button("▶️ Run Verified Search", type="primary", use_container_width=True)
    
    if search_btn:
        st.session_state.search_executed = True

    st.markdown("---")
    st.markdown("**📥 Download Full Databases**")
    if os.path.exists(os.path.join(BASE_DIR, "cdsco_combined_risk.xlsx")):
        with open(os.path.join(BASE_DIR, "cdsco_combined_risk.xlsx"), "rb") as f:
            st.download_button("📊 CDSCO Risk List (.xlsx)", data=f, file_name="cdsco_combined_risk.xlsx", 
                             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─── MAIN UI EXECUTION ────────────────────────────────────────────────────────
if st.session_state.search_executed and (device_name.strip() or applicant_name.strip()):
    
    # US FDA SECTION
    if jurisdiction in ["Dual (US FDA + CDSCO)", "US FDA Only"]:
        st.markdown("<div class='card card-blue'><h3 style='color:#0284c7;margin:0'>🇺🇸 US FDA — 510(k) Premarket Clearances</h3></div>", unsafe_allow_html=True)
        fda_res = search_us_fda(device_name, applicant_name, limit=20, ai_mode=ai_search_toggle)

        if fda_res.get("status") == "success" and fda_res["results"]:
            st.markdown(f"""
            <div class='audit-trace'>
                🔐 openFDA Hash: <code>{fda_res['hash'][:16]}...</code><br>
                📡 Query: <a href='{fda_res['url']}' style='color:#38bdf8;' target='_blank'>View Query</a>
            </div>
            """, unsafe_allow_html=True)
            st.write("")

            df_fda_export = pd.DataFrame([{
                "510(k) Number": r.get("k_number", ""),
                "Device Name": r.get("device_name", ""),
                "Applicant": r.get("applicant", ""),
                "Clearance Date": r.get("decision_date", ""),
                "Device Class": r.get("openfda", {}).get("device_class", ""),
            } for r in fda_res["results"]])

            # Apply filters
            df_fda_filtered = excel_style_filter(df_fda_export, filter_key_prefix="fda")
            
            st.download_button(
                label="📥 Download FDA 510(k) Results (.xlsx)",
                data=to_excel_bytes(df_fda_filtered, sheet_name="FDA_510k"),
                file_name=f"FDA_510k_{device_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_fda"
            )

            st.dataframe(df_fda_filtered, use_container_width=True)
        else:
            st.warning("No FDA 510(k) records matched.")

        st.write("")

    # CDSCO SECTION
    if jurisdiction in ["Dual (US FDA + CDSCO)", "CDSCO India Only"]:
        st.markdown("<div class='card card-green'><h3 style='color:#059669;margin:0'>🇮🇳 CDSCO India — Regulatory Intelligence</h3></div>", unsafe_allow_html=True)

        term = device_name.strip()
        app_term = applicant_name.strip()

        # STEP 1: Risk Classification
        st.markdown("#### Step 1: Risk Classification Lookup")
        st.caption("Covers: ListOfApprovedRiskDevice + ListOfApprovedRiskNSSMDevice")

        df_risk = risk_payload["data"]
        if not df_risk.empty:
            if search_scope == "Product Name Only":
                risk_cols = ["medical_device_name"]
            elif search_scope == "Company Name Only":
                risk_cols = ["device_category"]
            else:
                risk_cols = ["medical_device_name", "intended_use", "device_category"]

            if term:
                risk_matches = robust_dataframe_search(
                    df_risk, term, risk_cols, ai_mode=ai_search_toggle, match_mode=selected_mode
                )
            else:
                risk_matches = df_risk.copy()

            if selected_categories and "device_category" in risk_matches.columns:
                sel_clean = set(c.strip() for c in selected_categories)
                risk_matches = risk_matches[risk_matches["device_category"].astype(str).str.strip().isin(sel_clean)]

            if 'source_portal' in risk_matches.columns:
                risk_matches['Classification Source Portal'] = risk_matches['source_portal'].apply(
                    lambda x: 'Approved Device Class A (NSNM) Details' if 'NSSM' in str(x) else 'Approved Risk Device List'
                )
            else:
                risk_matches['Classification Source Portal'] = 'Approved Risk Device List'

            st.markdown(f"""
            <div class='audit-trace'>
                📊 Total Records: {len(df_risk):,} | Matches Found: {len(risk_matches):,}
            </div>
            """, unsafe_allow_html=True)

            if not risk_matches.empty:
                df_risk_disp = risk_matches[[
                    "medical_device_name", "device_category", "risk_classification_under_mdr_2017", "intended_use", "Classification Source Portal"
                ]].rename(columns={
                    "medical_device_name": "Product Name",
                    "device_category": "Category",
                    "risk_classification_under_mdr_2017": "Risk Class",
                    "intended_use": "Intended Use"
                })

                # Apply filters
                df_risk_filtered = excel_style_filter(df_risk_disp, filter_key_prefix="risk")
                
                st.download_button(
                    label="📥 Download Risk Classification Results (.xlsx)",
                    data=to_excel_bytes(df_risk_filtered, sheet_name="CDSCO_Risk"),
                    file_name=f"CDSCO_Risk_{device_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cdsco_risk"
                )

                st.dataframe(df_risk_filtered, use_container_width=True)
            else:
                st.warning(f"No CDSCO classification matches found for '{device_name}'.")

        st.markdown("---")

        # STEP 2: Manufacturers & Importers
        st.markdown("#### Step 2: Available Manufacturers & Importers")
        
        df_app = approved_payload["data"]
        if not df_app.empty:
            if search_scope == "Product Name Only":
                app_cols = ["devicename", "brandname", "modelname"]
            elif search_scope == "Company Name Only":
                app_cols = ["address", "premises_add"]
            else:
                app_cols = ["devicename", "brandname", "modelname", "str_intended_use", "address"]

            if term:
                app_matches = robust_dataframe_search(
                    df_app, term, app_cols, ai_mode=ai_search_toggle, match_mode=selected_mode
                )
            else:
                app_matches = df_app.copy()

            if cdsco_role == "Manufacturer Only":
                app_matches = app_matches[app_matches["role"] == "Manufacturer"]
            elif cdsco_role == "Importer Only":
                app_matches = app_matches[app_matches["role"] == "Importer"]

            st.markdown(f"📊 Found: {len(app_matches):,} registrations")

            if not app_matches.empty:
                disp_cols = ["devicename", "role", "address", "str_licence_no", "classname", "brandname"]
                df_app_disp = app_matches[[c for c in disp_cols if c in app_matches.columns]].rename(columns={
                    "devicename": "Device Name",
                    "role": "Role",
                    "address": "Company Name & Address",
                    "str_licence_no": "License No.",
                    "classname": "Class",
                    "brandname": "Brand Name"
                })

                # Apply filters
                df_app_filtered = excel_style_filter(df_app_disp, filter_key_prefix="approved")
                
                st.download_button(
                    label="📥 Download Approved Devices (.xlsx)",
                    data=to_excel_bytes(df_app_filtered, sheet_name="Approved_Devices"),
                    file_name=f"CDSCO_Devices_{device_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cdsco_app"
                )

                st.dataframe(df_app_filtered.head(300), use_container_width=True)
                if len(df_app_filtered) > 300:
                    st.caption(f"Showing 300 of {len(df_app_filtered):,} results")
            else:
                st.info(f"No approved devices matched '{device_name}'.")

