"""Command-based Cliq bot API. Run: uvicorn api:app --host 0.0.0.0 --port 8000."""
import os
import re
import secrets
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from research_engine import robust_dataframe_search, get_fda_pmn_link

app = FastAPI(title="MedDevice Cliq Bot", docs_url=None, redoc_url=None)
BASE_DIR = Path(__file__).resolve().parent
HELP = "Commands: fda <device>, risk <device>, manufacturer <device>, importer <device>. Example: fda photodynamic. FDA: add | applicant name to filter applicants. Use your Streamlit website for full searches and Excel downloads."


def authenticate(x_api_key: str = Header(default="")):
    expected = os.environ.get("CLIQ_API_KEY", "")
    if not expected:
        raise HTTPException(503, "Server API key is not configured")
    if not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(401, "Invalid API key")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


@lru_cache(maxsize=2)
def load_database(filename):
    path = BASE_DIR / filename
    if not path.is_file():
        raise HTTPException(503, "CDSCO database unavailable; check deployment files")
    return pd.read_parquet(path)


def clean(value):
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"[\r\n\[\]*`]+", " ", str(value))[:240]


def reply(text, total=None):
    website = os.environ.get("STREAMLIT_APP_URL", "")
    if website.startswith("https://"):
        text += "\nFull searches and downloads: " + website
    return {"text": text, "total": total}


def fda_search(query):
    device, _, applicant = query.partition("|")
    parts = []
    for field, value in (("device_name", device), ("applicant", applicant)):
        words = re.findall(r"\w+", value)
        parts.extend(f'{field}:"{word}"' for word in words)
    if not parts:
        return reply(HELP)
    # A single bounded request keeps this endpoint suitable for Cliq's synchronous handler.
    try:
        response = requests.get("https://api.fda.gov/device/510k.json", params={
            "search": " AND ".join(parts), "limit": 5, "sort": "decision_date:desc"
        }, timeout=(3, 12))
        if response.status_code == 404:
            if response.json().get("error", {}).get("code") == "NOT_FOUND":
                return reply("No matching FDA 510(k) records found.", 0)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return reply("FDA search is temporarily unavailable. Please try again shortly.")
    records = payload.get("results", [])
    total = payload.get("meta", {}).get("results", {}).get("total", len(records))
    lines = [f"FDA 510(k): {total:,} matches. Showing up to 5, newest first (keyword matching)."]
    for record in records:
        k = clean(record.get("k_number"))
        lines.append(f"{k}: {clean(record.get('device_name'))}\nApplicant: {clean(record.get('applicant'))}\nDecision: {clean(record.get('decision_date'))}\n{get_fda_pmn_link(k) or ''}")
    return reply("\n\n".join(lines), total)


def cdsco_search(command, query):
    if command == "risk":
        df = load_database("cdsco_combined_risk.parquet")
        columns = ["medical_device_name", "intended_use", "device_category"]
        fields = [("Device", "medical_device_name"), ("Risk class", "risk_classification_under_mdr_2017"), ("Category", "device_category"), ("Intended use", "intended_use")]
    else:
        df = load_database("cdsco_approved_devices.parquet")
        if "role" not in df.columns:
            raise HTTPException(503, "CDSCO role column unavailable")
        role = "Manufacturer" if command == "manufacturer" else "Importer"
        df = df[df["role"].astype(str).str.casefold() == role.casefold()]
        columns = ["devicename", "brandname", "modelname", "str_intended_use"]
        fields = [("Device", "devicename"), ("Company / address", "address"), ("Licence", "str_licence_no"), ("Class", "classname"), ("Brand", "brandname")]
    columns = [column for column in columns if column in df.columns]
    if not columns:
        raise HTTPException(503, "CDSCO search columns unavailable")
    matches = robust_dataframe_search(df, query, columns, ai_mode=False)
    lines = [f"CDSCO {command}: {len(matches):,} matching records. Showing up to 5 (keyword matching)."]
    for _, row in matches.head(5).iterrows():
        lines.append("\n".join(f"{label}: {clean(row.get(column))}" for label, column in fields))
    return reply("\n\n".join(lines), len(matches))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", dependencies=[Depends(authenticate)])
def chat(request: ChatRequest):
    message = request.message.strip()
    if message.lower() in {"hi", "hello", "help", "start"}:
        return reply(HELP)
    command, _, query = message.partition(" ")
    command = command.lower()
    if command not in {"fda", "risk", "manufacturer", "importer"} or not re.search(r"\w", query):
        return reply(HELP)
    if command == "fda":
        return fda_search(query)
    return cdsco_search(command, query.strip())
