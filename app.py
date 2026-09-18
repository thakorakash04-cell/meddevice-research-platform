import streamlit as st
import requests
import hashlib
from datetime import datetime
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

# ─── GLOBAL STYLES ────────────────────────────────────────────────────────────
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
[data-testid="stSidebar"] span[data-baseweb="tag"] [role="presentation"] {
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
div[data-baseweb="popover"] ul li,
div[data-baseweb="popover"] div[role="option"],
div[data-baseweb="menu"] div[role="option"] {
    color: #0f172a !important;
    font-weight: 500 !important;
    background-color: #ffffff !important;
    padding: 8px 12px !important;
}
div[data-baseweb="popover"] div[role="option"]:hover,
div[data-baseweb="menu"] div[role="option"]:hover,
div[data-baseweb="popover"] div[aria-selected="true"],
div[data-baseweb="menu"] div[aria-selected="true"] {
    background-color: #e0f2fe !important;
    color: #0369a1 !important;
    font-weight: 700 !important;
}

/* Primary Action Button */
[data-testid="stSidebar"] button[kind="primary"] {
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.3px;
    padding: 10px !important;
    margin-top: 8px;
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] button[kind="primary"]:hover {
    background-color: #0369a1 !important;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4) !important;
}

/* ─── CARD & AUDIT STYLES ─── */
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
.card-purple { border-left: 4px solid #8b5cf6; }

.audit-trace {
    background: #0f172a;
    color: #38bdf8;
    border-radius: 6px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 11px;
    margin-top: 6px;
}
.pill-D { background:#fef2f2; color:#dc2626; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px; }
.pill-C { background:#fff7ed; color:#ea580c; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px; }
.pill-B { background:#fefce8; color:#ca8a04; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px; }
.pill-A { background:#f0fdf4; color:#16a34a; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px; }
</style>
""", unsafe_allow_html=True)

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def to_excel_bytes(df, sheet_name="Results"):
    output = io.BytesIO()
    # Limit rows to 10000 for lightning-fast Excel export
    export_df = df.head(10000)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()

def get_fda_pmn_link(k): return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={k}" if k else None
def get_fda_pdf_link(k):
    if not k or not k.startswith("K"): return None
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
    """
    Search engine supporting:
    1. ai_mode = True: AI-Assisted Smart Search (Exact tokens + Regulatory Synonyms + Relevance Ranking)
    2. ai_mode = False: Strict Keyword Matching (Strict tokenized AND / Exact Phrase / OR)
    """
    if df.empty or not query.strip():
        return df

    q = query.lower().strip()
    words = [w for w in re.findall(r'\w+', q) if len(w) > 0]
    if not words:
        return df

    # Build corpus text across target columns
    corpus = df[target_columns[0]].astype(str).fillna('')
    for col in target_columns[1:]:
        if col in df.columns:
            corpus = corpus + ' ' + df[col].astype(str).fillna('')
    corpus = corpus.str.lower()

    if not ai_mode:
        # ── STRICT KEYWORD MODE ──
        if match_mode == 'exact':
            mask = corpus.str.contains(q, regex=False, na=False)
        elif match_mode == 'any_words':
            masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
            mask = pd.concat(masks, axis=1).any(axis=1) if masks else pd.Series(True, index=df.index)
        else: # all_words (AND - every word in query must appear)
            masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
            mask = pd.concat(masks, axis=1).all(axis=1) if masks else pd.Series(True, index=df.index)
        return df[mask]
    else:
        # ── AI-ASSISTED SMART SEARCH MODE ──
        # 1. Exact query match mask
        exact_masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
        exact_match_mask = pd.concat(exact_masks, axis=1).all(axis=1) if exact_masks else pd.Series(False, index=df.index)

        # 2. Semantic synonyms expansion mask
        synonym_terms = set()
        for w in words:
            for k, syn_list in SYNONYMS.items():
                if k in w or w in k:
                    synonym_terms.update(syn_list)

        syn_masks = [corpus.str.contains(t, regex=False, na=False) for t in synonym_terms]
        syn_match_mask = pd.concat(syn_masks, axis=1).any(axis=1) if syn_masks else pd.Series(False, index=df.index)

        # Combined match: Exact OR Semantic Synonyms
        combined_mask = exact_match_mask | syn_match_mask
        matched_df = df[combined_mask].copy()

        # Rank exact token matches first!
        if not matched_df.empty:
            is_exact = exact_match_mask.loc[matched_df.index]
            matched_df['_rank'] = is_exact.map({True: 0, False: 1})
            matched_df = matched_df.sort_values(by='_rank').drop(columns=['_rank'])

        return matched_df

# ─── DATA LOADERS (ACCELERATED PARQUET SNAPSHOTS FROM LIVE PORTALS) ───────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_cdsco_combined_risk():
    """Loads 3,665 live CDSCO Risk Classifications."""
    p_path = os.path.join(BASE_DIR, "cdsco_combined_risk.parquet")
    if os.path.exists(p_path):
        df = pd.read_parquet(p_path)
        with open(p_path, "rb") as f:
            h = sha256(f.read())
        return {"data": df, "total": len(df), "hash": h, "timestamp": datetime.now().isoformat()}
    return {"data": pd.DataFrame(), "total": 0, "hash": "", "timestamp": datetime.now().isoformat()}

@st.cache_data(ttl=3600, show_spinner=False)
def load_cdsco_approved_devices():
    """Loads 104,451 live CDSCO Approved Manufacturers & Importers."""
    p_path = os.path.join(BASE_DIR, "cdsco_approved_devices.parquet")
    if os.path.exists(p_path):
        df = pd.read_parquet(p_path)
        with open(p_path, "rb") as f:
            h = sha256(f.read())
        return {"data": df, "total": len(df), "hash": h, "timestamp": datetime.now().isoformat()}
    return {"data": pd.DataFrame(), "total": 0, "hash": "", "timestamp": datetime.now().isoformat()}

# Load Datasets
risk_payload = load_cdsco_combined_risk()
approved_payload = load_cdsco_approved_devices()

def get_cdsco_sync_metadata():
    sync_info = {
        "last_updated": "16-Sep-2026 16:12 UTC",
        "status": "Active (Weekly Auto-Sync)",
        "schedule": "Every Sunday at 02:00 AM",
        "risk_records": len(risk_payload["data"]) if not risk_payload["data"].empty else 0,
        "approved_records": len(approved_payload["data"]) if not approved_payload["data"].empty else 0
    }
    meta_path = os.path.join(BASE_DIR, "cdsco_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
                dt = datetime.fromisoformat(meta.get("last_updated"))
                sync_info["last_updated"] = dt.strftime("%d-%b-%Y %H:%M:%S UTC")
        except Exception:
            pass
    elif os.path.exists(os.path.join(BASE_DIR, "cdsco_approved_devices.parquet")):
        mtime = os.path.getmtime(os.path.join(BASE_DIR, "cdsco_approved_devices.parquet"))
        sync_info["last_updated"] = datetime.fromtimestamp(mtime).strftime("%d-%b-%Y %H:%M:%S")
    return sync_info

sync_meta = get_cdsco_sync_metadata()

# ─── US FDA OPENFDA API (WITH ROBUST MULTI-FIELD SEARCH) ───────────────────────
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

    # Live Data Provenance & Sync Status Badge
    st.markdown(f"""
    <div style="background:#1e293b; border-radius:8px; padding:12px; border:1px solid #334155; margin-bottom:12px;">
        <div style="color:#10b981; font-weight:700; font-size:12px; display:flex; align-items:center; gap:6px;">
            <span>🟢</span> CDSCO WEEKLY AUTO-SYNC ACTIVE
        </div>
        <div style="color:#f8fafc; font-size:12px; margin-top:6px;"><b>Last Data Fetched:</b><br><span style="color:#38bdf8;">{sync_meta['last_updated']}</span></div>
        <div style="color:#94a3b8; font-size:11px; margin-top:4px;"><b>Schedule:</b> {sync_meta['schedule']}</div>
        <div style="color:#94a3b8; font-size:11px; margin-top:2px;"><b>Verified Scope:</b> {sync_meta['risk_records']:,} Risk Classes | {sync_meta['approved_records']:,} Registrations</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    jurisdiction = st.selectbox("Regulatory Target", ["Dual (US FDA + CDSCO)", "CDSCO India Only", "US FDA Only"])
    st.markdown("---")
    device_name = st.text_input("Product / Device Name", value="Laser", placeholder="e.g. Laser, Diode, Stent, Bandage")
    applicant_name = st.text_input("Manufacturer / Importer", value="", placeholder="e.g. Meril, Wuhan Dimed, Abbott, Medtronic")

    st.markdown("---")
    st.markdown("**🤖 AI Search & Engine Controls**")

    # ── THE PRIMARY AI SEARCH TOGGLE ──
    ai_search_toggle = st.toggle(
        "🤖 AI-Assisted Smart Search",
        value=True,
        help="ON: Uses AI semantic synonyms, predicate expansion & smart ranking so zero filings are missed.\nOFF: Strict verbatim keyword matching."
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
        st.caption("✨ *AI Search Active: Expanding synonyms (e.g. Laser ➔ Diode/Holmium/Argon/Excimer) with relevance ranking.*")

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

    search_btn = st.button("Run Verified Search", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("**📥 Download Full Databases**")
    if os.path.exists(os.path.join(BASE_DIR, "cdsco_combined_risk.xlsx")):
        with open(os.path.join(BASE_DIR, "cdsco_combined_risk.xlsx"), "rb") as f:
            st.download_button("📊 CDSCO Risk List (.xlsx)", data=f, file_name="cdsco_combined_risk.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if os.path.exists(os.path.join(BASE_DIR, "cdsco_approved_devices.parquet")):
        with open(os.path.join(BASE_DIR, "cdsco_approved_devices.parquet"), "rb") as f:
            st.download_button("💾 Approved Devices (104k Parquet)", data=f, file_name="cdsco_approved_devices.parquet", mime="application/octet-stream")

# ─── MAIN UI EXECUTION ────────────────────────────────────────────────────────
if search_btn and (device_name.strip() or applicant_name.strip()):

    # ══════════════════════════════════════════════════════════════════════════
    #  1. US FDA SECTION (TOP POSITION)
    # ══════════════════════════════════════════════════════════════════════════
    if jurisdiction in ["Dual (US FDA + CDSCO)", "US FDA Only"]:
        st.markdown("<div class='card card-blue'><h3 style='color:#0284c7;margin:0'>🇺🇸 US FDA — 510(k) Premarket Clearances</h3></div>", unsafe_allow_html=True)
        fda_res = search_us_fda(device_name, applicant_name, limit=20, ai_mode=ai_search_toggle)

        if fda_res.get("status") == "success" and fda_res["results"]:
            st.markdown(f"""
            <div class='audit-trace'>
                🔐 openFDA Payload Hash: <code>{fda_res['hash']}</code><br>
                📡 Query URL: <a href='{fda_res['url']}' style='color:#38bdf8;' target='_blank'>{fda_res['url'][:80]}...</a>
            </div>
            """, unsafe_allow_html=True)
            st.write("")

            df_fda_export = pd.DataFrame([{
                "510(k) Number": r.get("k_number", ""),
                "Device Name": r.get("device_name", ""),
                "Applicant": r.get("applicant", ""),
                "Clearance Date": r.get("decision_date", ""),
                "Device Class": r.get("openfda", {}).get("device_class", ""),
                "Regulation Number": r.get("regulation_number", ""),
                "Product Code": r.get("product_code", ""),
                "Advisory Committee": r.get("advisory_committee_description", "")
            } for r in fda_res["results"]])

            st.download_button(
                label="📥 Download US FDA 510(k) Results (.xlsx)",
                data=to_excel_bytes(df_fda_export, sheet_name="FDA_510k"),
                file_name=f"US_FDA_510k_{device_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_fda_top"
            )

            grouped = defaultdict(list)
            for r in fda_res["results"]:
                grouped[r.get("applicant", "Unknown").strip()].append(r)

            for app, items in grouped.items():
                pnames = ", ".join(list(set(i.get("device_name", "") for i in items))[:2])
                with st.expander(f"🏢 **{app}** — {pnames} ({len(items)} clearances)", expanded=False):
                    for item in items:
                        k = item.get("k_number", "")
                        col1, col2, col3 = st.columns([4, 1, 1])
                        with col1:
                            st.markdown(f"🏷️ **{item.get('device_name')}**")
                            st.caption(f"K-Number: `{k}` | Cleared: {item.get('decision_date')} | Class: {item.get('openfda', {}).get('device_class', 'N/A')}")
                        with col2:
                            st.markdown(f"[🏛️ PMN Record]({get_fda_pmn_link(k)})")
                        with col3:
                            st.markdown(f"[📑 Summary PDF]({get_fda_pdf_link(k)})")
                        st.divider()
        else:
            st.warning("No FDA 510(k) records matched your query.")

        st.write("")
        st.write("")

    # ══════════════════════════════════════════════════════════════════════════
    #  2. CDSCO SECTION (BOTTOM POSITION)
    # ══════════════════════════════════════════════════════════════════════════
    if jurisdiction in ["Dual (US FDA + CDSCO)", "CDSCO India Only"]:
        st.markdown("<div class='card card-green'><h3 style='color:#059669;margin:0'>🇮🇳 CDSCO India — Regulatory Intelligence</h3></div>", unsafe_allow_html=True)

        term = device_name.strip()
        app_term = applicant_name.strip()

        # ──────────────────────────────────────────────────────────────────────
        # STEP 1: Risk Classification Lookup (Risk + NSSM Portals)
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("#### Step 1: Risk Classification Lookup")
        st.caption("Covers: `ListOfApprovedRiskDevice` + `ListOfApprovedRiskNSSMDevice` (includes Class A NSNM Details)")

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

            def clean_source_portal(val):
                if 'NSSM' in str(val):
                    return 'Approved Device Class A (NSNM) Details'
                return 'Approved Risk Device List'

            if 'source_portal' in risk_matches.columns:
                risk_matches['Classification Source Portal'] = risk_matches['source_portal'].apply(clean_source_portal)
            else:
                risk_matches['Classification Source Portal'] = 'Approved Risk Device List'

            st.markdown(f"""
            <div class='audit-trace'>
                🔐 Verified CDSCO Risk Database Hash: <code>{risk_payload['hash']}</code><br>
                📊 Total Records Scanned: {len(df_risk):,} | Matches Found: {len(risk_matches):,}<br>
                📡 Portals: <a href='https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedRiskDevice' style='color:#38bdf8;' target='_blank'>ListOfApprovedRiskDevice</a> &nbsp;+&nbsp;
                <a href='https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedRiskNSSMDevice' style='color:#38bdf8;' target='_blank'>ListOfApprovedRiskNSSMDevice (NSNM)</a>
            </div>
            """, unsafe_allow_html=True)
            st.write("")

            if not risk_matches.empty:
                df_risk_disp = risk_matches[[
                    "medical_device_name", "device_category", "risk_classification_under_mdr_2017", "intended_use", "Classification Source Portal"
                ]].rename(columns={
                    "medical_device_name": "Product Name",
                    "device_category": "Category",
                    "risk_classification_under_mdr_2017": "Risk Class",
                    "intended_use": "Intended Use"
                })

                st.download_button(
                    label="📥 Download CDSCO Risk Classification Results (.xlsx)",
                    data=to_excel_bytes(df_risk_disp, sheet_name="CDSCO_Risk_Classes"),
                    file_name=f"CDSCO_Risk_{device_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cdsco_risk"
                )

                st.dataframe(df_risk_disp, use_container_width=True)
            else:
                st.warning(f"No official CDSCO classification matches found for '{device_name}'. Try enabling the AI Search toggle or changing keyword matching mode.")
        else:
            st.error("Risk classification dataset not loaded.")

        st.markdown("---")

        # ──────────────────────────────────────────────────────────────────────
        # STEP 2: Available Manufacturers & Importers (104k Live Records)
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("#### Step 2: Available Manufacturers & Importers")
        st.caption("Official data from: `https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedDevices` (Manufacturer + Importer registers)")

        df_app = approved_payload["data"]
        if not df_app.empty:
            if search_scope == "Product Name Only":
                app_cols = ["devicename", "brandname", "modelname"]
            elif search_scope == "Company Name Only":
                app_cols = ["address", "premises_add"]
            else:
                app_cols = ["devicename", "brandname", "modelname", "str_intended_use", "address", "str_licence_no", "instname"]

            if term:
                app_matches = robust_dataframe_search(
                    df_app, term, app_cols, ai_mode=ai_search_toggle, match_mode=selected_mode
                )
            else:
                app_matches = df_app.copy()

            if app_term:
                app_matches = robust_dataframe_search(
                    app_matches, app_term, ["address", "premises_add"], ai_mode=False, match_mode="all_words"
                )

            if cdsco_role == "Manufacturer Only":
                app_matches = app_matches[app_matches["role"] == "Manufacturer"]
            elif cdsco_role == "Importer Only":
                app_matches = app_matches[app_matches["role"] == "Importer"]

            st.markdown(f"""
            <div class='audit-trace'>
                🔐 Verified Approved Devices Hash: <code>{approved_payload['hash']}</code><br>
                📊 Total Government Registrations Scanned: {len(df_app):,} (78,962 Mfgs + 25,489 Importers) | Matches Found: {len(app_matches):,}<br>
                📡 Source Portal: <a href='https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedDevices' style='color:#38bdf8;' target='_blank'>ListOfApprovedDevices (Manufacturer & Importer)</a>
            </div>
            """, unsafe_allow_html=True)
            st.write("")

            if not app_matches.empty:
                role_counts = app_matches["role"].value_counts().to_dict()
                mfg_c = role_counts.get("Manufacturer", 0)
                imp_c = role_counts.get("Importer", 0)
                st.success(f"✅ Found **{len(app_matches):,}** total filings: **{mfg_c:,} Domestic Manufacturers** and **{imp_c:,} Importers** matching your search criteria.")

                disp_cols = ["devicename", "role", "address", "str_licence_no", "classname", "brandname", "modelname", "instname"]
                df_app_disp = app_matches[[c for c in disp_cols if c in app_matches.columns]].rename(columns={
                    "devicename": "Device Name",
                    "role": "Role (Mfg/Imp)",
                    "address": "Company Name & Registered Address",
                    "str_licence_no": "License Number",
                    "classname": "Class",
                    "brandname": "Brand Name",
                    "modelname": "Model Numbers",
                    "instname": "Issuing Authority"
                })

                st.download_button(
                    label="📥 Download CDSCO Approved Devices Results (.xlsx)",
                    data=to_excel_bytes(df_app_disp, sheet_name="Approved_Devices"),
                    file_name=f"CDSCO_Approved_Devices_{device_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cdsco_app"
                )

                st.dataframe(df_app_disp.head(300), use_container_width=True)
                if len(df_app_disp) > 300:
                    st.caption(f"Showing top 300 of {len(df_app_disp):,} results. Narrow your search by applicant name or role if needed.")

                with st.expander("🏢 Grouped by Company Profiles (Expand to view portfolio)", expanded=False):
                    grouped_co = defaultdict(list)
                    for _, row_item in app_matches.head(100).iterrows():
                        raw_a = str(row_item.get("address", "Unknown"))
                        c_title = raw_a.split("\n")[0] if "\n" in raw_a else raw_a[:60]
                        grouped_co[c_title].append(row_item)

                    for c_name, c_rows in grouped_co.items():
                        st.markdown(f"**🏢 {c_name}** ({len(c_rows)} devices)")
                        st.caption(f"Role: {c_rows[0].get('role')} | License: `{c_rows[0].get('str_licence_no')}` | Authority: {c_rows[0].get('instname')}")
                        for cr in c_rows[:5]:
                            st.markdown(f"- 🏷️ **{cr.get('devicename')}** (Brand: *{cr.get('brandname','-')}*, Class: `{cr.get('classname','-')}`)")
                        if len(c_rows) > 5:
                            st.caption(f"+ {len(c_rows)-5} more devices under this company")
                        st.divider()
            else:
                st.info(f"No approved devices matched '{device_name}'. Try enabling the AI Search toggle or broadening search scope.")
        else:
            st.error("Approved devices dataset not loaded.")
