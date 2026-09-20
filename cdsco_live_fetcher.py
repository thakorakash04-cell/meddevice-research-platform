import requests
import hashlib
from datetime import datetime
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
import os

try:
    import orjson
    def fast_json_loads(data_bytes):
        return orjson.loads(data_bytes)
except ImportError:
    import json
    def fast_json_loads(data_bytes):
        return json.loads(data_bytes)

urllib3.disable_warnings()

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _get_session(url_base: str):
    s = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    r = s.get(url_base, headers=headers, verify=False, timeout=30)
    soup = BeautifulSoup(r.content, 'html.parser')
    csrf_meta = soup.find('meta', {'name': '_csrf'})
    header_meta = soup.find('meta', {'name': '_csrf_header'})
    if not csrf_meta or not header_meta:
        raise RuntimeError("Could not extract CSRF token from CDSCO portal")
    return s, csrf_meta['content'], header_meta['content'], headers

def fetch_risk_device_list() -> dict:
    """
    Fetches the complete risk list from BOTH portals:
    1. ListOfApprovedRiskDevice (General Notified Devices)
    2. ListOfApprovedRiskNSSMDevice (Class A Non-Sterile / Non-Measuring details)
    """
    try:
        # 1. Standard Risk Device Portal
        s1, tok1, hdr1, headers = _get_session("https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedRiskDevice")
        headers1 = {**headers, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', hdr1: tok1}
        r1 = s1.post('https://cdscomdonline.gov.in/NewMedDev/viewApprovedRiskDevice', json={}, headers=headers1, verify=False, timeout=45)
        d1 = fast_json_loads(r1.content).get('aaData', [])
        for row in d1:
            row['source_portal'] = 'ListOfApprovedRiskDevice'

        # 2. NSSM Risk Device Portal (Class A NSNM)
        s2, tok2, hdr2, _ = _get_session("https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedRiskNSSMDevice")
        headers2 = {**headers, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', hdr2: tok2}
        r2 = s2.post('https://cdscomdonline.gov.in/NewMedDev/viewApprovedRiskDeviceNSSM', json={}, headers=headers2, verify=False, timeout=45)
        d2 = fast_json_loads(r2.content).get('aaData', [])
        for row in d2:
            row['source_portal'] = 'ListOfApprovedRiskNSSMDevice'

        combined = d1 + d2
        raw_hash = sha256(str(combined).encode('utf-8'))
        return {
            "records": combined,
            "total": len(combined),
            "general_count": len(d1),
            "nssm_count": len(d2),
            "hash": raw_hash,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
    except Exception as e:
        return {"records": [], "total": 0, "hash": "", "timestamp": datetime.now().isoformat(), "error": str(e)}

def fetch_approved_devices_by_form(form_type: int, role_label: str) -> list:
    """
    Fetches approved registrations:
    form_type=2 ➔ Domestic Manufacturers (Form MD-3/5/7/8/28)
    form_type=1 ➔ Importers (Form MD-14/15)
    """
    try:
        s = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        s.get("https://cdscomdonline.gov.in/NewMedDev/ListOfApprovedDevices", headers=headers, verify=False, timeout=30)
        url = 'https://cdscomdonline.gov.in/NewMedDev/viewListOfApprovedDevices'

        # Stream request to prevent memory bloat on 100MB payloads
        r = s.get(url, params={'selectFormType': form_type, 'categval': 1}, headers=headers, verify=False, timeout=120)
        if r.status_code == 200:
            data = fast_json_loads(r.content)
            rows = data.get('aaData', [])
            for row in rows:
                row['role'] = role_label
            return rows
        return []
    except Exception as e:
        print(f"Error fetching form_type {form_type} ({role_label}): {e}")
        return []

def fetch_all_approved_devices() -> dict:
    """
    Fetches ALL approved registrations combining:
    1. Domestic Manufacturers (Form 2)
    2. Importers (Form 1)
    """
    try:
        mfg = fetch_approved_devices_by_form(2, 'Manufacturer')
        imp = fetch_approved_devices_by_form(1, 'Importer')
        combined = mfg + imp
        raw_hash = sha256(str(combined).encode('utf-8'))
        return {
            "records": combined,
            "total": len(combined),
            "mfg_count": len(mfg),
            "imp_count": len(imp),
            "hash": raw_hash,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
    except Exception as e:
        return {"records": [], "total": 0, "hash": "", "timestamp": datetime.now().isoformat(), "error": str(e)}

if __name__ == "__main__":
    print("Testing live CDSCO extraction...")
    r = fetch_risk_device_list()
    print(f"Risk Devices Total: {r['total']} (General: {r.get('general_count')}, NSSM: {r.get('nssm_count')})")
    a = fetch_all_approved_devices()
    print(f"Approved Devices Total: {a['total']} (Mfg: {a.get('mfg_count')}, Imp: {a.get('imp_count')})")
