import requests
import hashlib
from datetime import datetime
import json
import pandas as pd
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _get_session(url_base: str):
    s = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    r = s.get(url_base, headers=headers, verify=False, timeout=20)
    soup = BeautifulSoup(r.content, 'html.parser')
    csrf_meta = soup.find('meta', {'name': '_csrf'})
    header_meta = soup.find('meta', {'name': '_csrf_header'})
    if not csrf_meta or not header_meta:
        raise RuntimeError("Could not extract CSRF token")
    return s, csrf_meta['content'], header_meta['content'], headers

def fetch_risk_device_list() -> dict:
    """Fetches the complete risk list from ListOfApprovedRiskDevice + ListOfApprovedRiskNSSMDevice"""
    try:
        # 1. Standard Risk Device
        s1, tok1, hdr1, headers = _get_session("https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedRiskDevice")
        headers1 = {**headers, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', hdr1: tok1}
        r1 = s1.post('https://cdscomdonline.gov.in/NewMedDev/viewApprovedRiskDevice', json={}, headers=headers1, verify=False, timeout=30)
        d1 = json.loads(r1.text).get('aaData', [])
        for row in d1:
            row['source_portal'] = 'ListOfApprovedRiskDevice'

        # 2. NSSM Risk Device (Class A NSNM)
        s2, tok2, hdr2, _ = _get_session("https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedRiskNSSMDevice")
        headers2 = {**headers, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', hdr2: tok2}
        r2 = s2.post('https://cdscomdonline.gov.in/NewMedDev/viewApprovedRiskDeviceNSSM', json={}, headers=headers2, verify=False, timeout=30)
        d2 = json.loads(r2.text).get('aaData', [])
        for row in d2:
            row['source_portal'] = 'ListOfApprovedRiskNSSMDevice'

        combined = d1 + d2
        raw_hash = sha256(str(combined).encode('utf-8'))
        return {"records": combined, "hash": raw_hash, "timestamp": datetime.now().isoformat(), "error": None}
    except Exception as e:
        return {"records": [], "hash": "", "timestamp": datetime.now().isoformat(), "error": str(e)}

def fetch_approved_devices_by_form(form_type: int, role_label: str) -> list:
    try:
        s = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0'}
        s.get("https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedDevices", headers=headers, verify=False, timeout=30)
        url = 'https://cdscomdonline.gov.in/NewMedDev/viewListOfApprovedDevices'

        all_rows = []
        # Fetch all pages by increasing 'start' parameter
        # Start with start=0, length=10000 to get all at once
        r = s.get(url, params={'selectFormType': form_type, 'categval': 1, 'start': 0, 'length': 100000}, headers=headers, verify=False, timeout=120)
        if r.status_code == 200:
            data = r.json()
            rows = data.get('aaData', [])
            for row in rows:
                row['role'] = role_label
            return rows
        return []
    except Exception as e:
        print(f"Error fetching form_type {form_type}: {e}")
        return []

def fetch_all_approved_devices() -> dict:
    """Fetches ALL approved devices: Manufacturers (form_type=2) + Importers (form_type=1)"""
    try:
        mfg = fetch_approved_devices_by_form(2, 'Manufacturer')
        imp = fetch_approved_devices_by_form(1, 'Importer')
        combined = mfg + imp
        raw_hash = sha256(str(combined).encode('utf-8'))
        return {"records": combined, "total": len(combined), "hash": raw_hash, "timestamp": datetime.now().isoformat(), "error": None}
    except Exception as e:
        return {"records": [], "total": 0, "hash": "", "timestamp": datetime.now().isoformat(), "error": str(e)}

if __name__ == "__main__":
    # CLI for manual testing
    import pandas as pd
    print("Fetching Risk Devices...")
    r = fetch_risk_device_list()
    print(f"Risk: {len(r['records'])} records")
    df_r = pd.DataFrame(r['records'])
    df_r.to_parquet('cdsco_combined_risk.parquet', index=False)

    print("Fetching Approved Devices...")
    a = fetch_all_approved_devices()
    print(f"Approved: {len(a['records'])} records")
    df_a = pd.DataFrame(a['records'])
    df_a.to_parquet('cdsco_approved_devices.parquet', index=False)
    print("Done.")