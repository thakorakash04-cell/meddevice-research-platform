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

from workspace_auth import require_workspace, admin_download
from workspace_ui import data_table, workspace_theme
workspace_theme()
workspace_store, workspace_actor, workspace_identity = require_workspace()

# ─── BASE DIRECTORY FOR PARQUET FILES ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if 'search_executed' not in st.session_state:
    st.session_state.search_executed = False

from research_engine import sha256, get_fda_pmn_link, get_fda_pdf_link, expand_terms, robust_dataframe_search

def to_excel_bytes(df, sheet_name="Results"):
    output = io.BytesIO()
    export_df = df
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()

# ─── DATA LOADERS ────────────────────────────────────────────────────────────
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

@st.cache_data(ttl=900, show_spinner=False)
def search_us_fda(device_query: str, applicant: str, ai_mode=True):
    search_parts = []
    if device_query.strip():
        dev_clean = device_query.strip()
        words = re.findall(r'\w+', dev_clean)
        if ai_mode:
            terms = expand_terms(dev_clean, enable_synonyms=True)
            term_str = " OR ".join([f'"{t}"' for t in terms])
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
    url = f"https://api.fda.gov/device/510k.json?search={quote(raw_query)}&limit=1000&sort=decision_date:asc"
    results = []
    total = 0
    digest = hashlib.sha256()
    visited = set()
    next_url = url
    try:
        with requests.Session() as session:
            adapter = requests.adapters.HTTPAdapter(
                max_retries=urllib3.util.Retry(
                    total=4, backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET"], respect_retry_after_header=True
                )
            )
            session.mount("https://", adapter)
            while next_url:
                if next_url in visited:
                    raise ValueError("FDA pagination repeated a page; please retry.")
                visited.add(next_url)
                resp = session.get(next_url, timeout=60)
                if resp.status_code == 404 and not results:
                    error = resp.json().get("error", {})
                    if error.get("code") == "NOT_FOUND":
                        return {"status": "success", "hash": sha256(resp.content),
                                "url": url, "query": raw_query,
                                "timestamp": datetime.now().isoformat(),
                                "total": 0, "results": []}
                resp.raise_for_status()
                digest.update(resp.content)
                data = resp.json()
                total = data.get("meta", {}).get("results", {}).get("total", total)
                page = data.get("results", [])
                if not page and len(results) < total:
                    raise ValueError("FDA returned an empty page before all records loaded.")
                results.extend(page)
                if len(results) >= total:
                    break
                # Follow openFDA search-after links, including searches over 26,000 hits.
                next_url = next(
                    (link["url"] for relation, link in resp.links.items()
                     if relation.lower() == "next"), None
                )
                if next_url and not next_url.startswith("https://api.fda.gov/"):
                    raise ValueError("Unexpected FDA pagination URL.")
        if len(results) != total:
            raise ValueError(f"Only {len(results):,} of {total:,} FDA records loaded. Please retry.")
        return {"status": "success", "hash": digest.hexdigest(), "url": url,
                "query": raw_query, "timestamp": datetime.now().isoformat(),
                "total": total, "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e), "total": total,
                "loaded": len(results), "url": url}


workspace_theme()

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Regulatory Intelligence")

    with st.expander("Database update details"):
        st.caption("Last fetched: " + str(sync_meta["last_updated"]))
        st.caption("Schedule: " + str(sync_meta["schedule"]))
        st.caption(f"{sync_meta['risk_records']:,} risk classifications · {sync_meta['approved_records']:,} registrations")

    st.markdown("---")
    jurisdiction = st.selectbox("Regulatory Target", ["Dual (US FDA + CDSCO)", "CDSCO India Only", "US FDA Only"])
    st.markdown("---")
    device_name = st.text_input("Product / Device Name", value="Laser", placeholder="e.g. Laser, Diode, Stent")
    applicant_name = st.text_input("Manufacturer / Importer", value="", placeholder="e.g. Meril, Abbott")

    st.markdown("---")
    st.markdown("**Search options**")

    ai_search_toggle = st.toggle(
        "Smart search",
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
        st.caption("Includes related terms, ranked by relevance.")

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

    search_btn = st.button("Run search", type="primary", use_container_width=True)

    if search_btn:
        st.session_state.search_executed = True

    if workspace_identity["role"] == "admin":
        with st.expander("Database downloads"):
            if os.path.exists(os.path.join(BASE_DIR, "cdsco_combined_risk.xlsx")):
                with open(os.path.join(BASE_DIR, "cdsco_combined_risk.xlsx"), "rb") as f:
                    admin_download("CDSCO Risk List (.xlsx)", data=f, file_name="cdsco_combined_risk.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.title("MedDevice Research")
st.caption("Search regulatory records, compare results, and open full-window record details.")

# ─── MAIN UI EXECUTION ────────────────────────────────────────────────────────
if st.session_state.search_executed and (device_name.strip() or applicant_name.strip()):

    tab_fda, tab_risk, tab_approved = st.tabs([
        "FDA 510(k)", "CDSCO Risk Classification", "Approved Devices"
    ])
    term = device_name.strip()
    app_term = applicant_name.strip()

    with tab_fda:
        if jurisdiction in ["Dual (US FDA + CDSCO)", "US FDA Only"]:
            with st.spinner("Loading all matching FDA 510(k) records..."):
                fda_res = search_us_fda(device_name, applicant_name, ai_mode=ai_search_toggle)

            if fda_res.get("status") == "success" and fda_res["results"]:
                df_fda_filter = pd.DataFrame([{
                    "510(k) Number": r.get("k_number", ""),
                    "Device Name": r.get("device_name", ""),
                    "Applicant": r.get("applicant", ""),
                    "Clearance Date": r.get("decision_date", ""),
                    "Device Class": ", ".join(r.get("openfda", {}).get("device_class", []))
                        if isinstance(r.get("openfda", {}).get("device_class", ""), list)
                        else r.get("openfda", {}).get("device_class", ""),
                } for r in fda_res["results"]])
                df_fda_filtered = df_fda_filter

                df_fda_display = df_fda_filtered.copy()
                df_fda_display["View PMN"] = df_fda_display["510(k) Number"].map(get_fda_pmn_link)
                df_fda_display["PDF Summary"] = df_fda_display["510(k) Number"].map(get_fda_pdf_link)
                data_table(df_fda_display, "research-fda", "FDA 510(k)",
                           description="US premarket clearances · 20 results per page")
                with st.expander("Source details", key="fda_source_details"):
                    st.caption(f"Loaded {len(df_fda_filtered):,} of {fda_res['total']:,} matching records from openFDA.")
                    st.caption("Data fingerprint: " + fda_res["hash"])
                    st.link_button("Open source query", fda_res["url"])
                    if workspace_identity["role"] == "admin":
                        admin_download("Download all search results (.xlsx)",
                            data=to_excel_bytes(df_fda_filtered, sheet_name="FDA_510k"),
                            file_name="FDA_510k_Results.xlsx", key="dl_fda")
            elif fda_res.get("status") == "error":
                st.error(f"FDA search could not finish: {fda_res.get('message', 'Unknown error')}. Please run the search again.")
            else:
                st.warning("No FDA 510(k) records matched.")

            st.write("")

        else:
            st.info("Select a regulatory target that includes US FDA to search this tab.")

    with tab_risk:
        if jurisdiction in ["Dual (US FDA + CDSCO)", "CDSCO India Only"]:

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

                if not risk_matches.empty:
                    df_risk_disp = risk_matches[[
                        "medical_device_name", "device_category", "risk_classification_under_mdr_2017", "intended_use", "Classification Source Portal"
                    ]].rename(columns={
                        "medical_device_name": "Product Name",
                        "device_category": "Category",
                        "risk_classification_under_mdr_2017": "Risk Class",
                        "intended_use": "Intended Use"
                    })

                    data_table(df_risk_disp, "research-risk", "CDSCO Risk Classification",
                               description="Indian device risk classifications · 20 results per page")
                    with st.expander("Source details", key="risk_source_details"):
                        st.caption(f"{len(risk_matches):,} matching records from {len(df_risk):,} classifications.")
                        st.caption("Sources: Approved Risk Device List and Class A non-sterile, non-measuring device list.")
                        if workspace_identity["role"] == "admin":
                            admin_download("Download all search results (.xlsx)",
                                data=to_excel_bytes(df_risk_disp, sheet_name="CDSCO_Risk"),
                                file_name="CDSCO_Risk_Results.xlsx", key="dl_cdsco_risk")
                else:
                    st.warning(f"No CDSCO classification matches found for '{device_name}'.")


        else:
            st.info("Select a regulatory target that includes CDSCO to search this tab.")

    with tab_approved:
        if jurisdiction in ["Dual (US FDA + CDSCO)", "CDSCO India Only"]:

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

                    data_table(df_app_disp, "research-approved", "Approved Devices",
                               description="Registered manufacturers and importers · 20 results per page")
                    with st.expander("Source details", key="approved_source_details"):
                        st.caption(f"{len(app_matches):,} matching registrations from {len(df_app):,} records.")
                        st.caption("Source: CDSCO approved device registrations.")
                        if workspace_identity["role"] == "admin":
                            admin_download("Download all search results (.xlsx)",
                                data=to_excel_bytes(df_app_disp, sheet_name="Approved_Devices"),
                                file_name="CDSCO_Approved_Devices.xlsx", key="dl_cdsco_app")
                else:
                    st.info(f"No approved devices matched '{device_name}'.")
        else:
            st.info("Select a regulatory target that includes CDSCO to search this tab.")
else:
    st.info("Enter a device or manufacturer in the sidebar, then select Run search.")
