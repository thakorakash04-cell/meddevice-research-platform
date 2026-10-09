"""Temporary complete search results, paged browser view and CSV download."""
import csv
import io
import json
import secrets
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

router = APIRouter()
ROOT = Path(tempfile.mkdtemp(prefix="meddevice-results-"))
JOBS = {}
LOCK = threading.RLock()
SLOTS = threading.BoundedSemaphore(2)
TTL = 3600
HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow"}


def get_job(token):
    with LOCK:
        job = JOBS.get(token)
        if not job or time.monotonic() - job["created"] > TTL:
            raise HTTPException(410, "Results expired. Run the search again.")
        return job


def add_rows(job, rows):
    with sqlite3.connect(job["path"]) as db:
        db.executemany("INSERT INTO records(payload) VALUES (?)", [(json.dumps(row, ensure_ascii=False),) for row in rows])
    with LOCK:
        job["loaded"] += len(rows)
        for row in rows:
            for column in row:
                if column not in job["columns"]:
                    job["columns"].append(column)


def finish(job):
    if job["loaded"] != job["total"]:
        raise ValueError("Incomplete results")
    job["status"] = "complete"


def collect_fda(job, next_url):
    visited = set()
    try:
        while next_url:
            parsed = urlparse(next_url)
            if parsed.scheme != "https" or parsed.netloc != "api.fda.gov" or parsed.path != "/device/510k.json" or next_url in visited:
                raise ValueError("Unexpected pagination URL")
            visited.add(next_url)
            response = requests.get(next_url, timeout=(5, 30))
            response.raise_for_status()
            payload = response.json()
            if payload.get("meta", {}).get("results", {}).get("total", job["total"]) != job["total"]:
                raise ValueError("Search changed during loading")
            rows = payload.get("results", [])
            if not rows:
                raise ValueError("Empty page before completion")
            add_rows(job, rows)
            if job["loaded"] >= job["total"]:
                break
            next_url = response.links.get("next", {}).get("url")
        finish(job)
    except Exception:
        job["status"] = "error"
        job["error"] = "Could not load all matching FDA records. Run the search again; partial results cannot be downloaded as complete."
    finally:
        SLOTS.release()


def save_results(rows, total, next_url=None, source="CDSCO"):
    with LOCK:
        for token, old in list(JOBS.items()):
            if old["status"] != "loading" and time.monotonic() - old["created"] > TTL:
                Path(old["path"]).unlink(missing_ok=True)
                del JOBS[token]
        if len(JOBS) >= 30:
            raise HTTPException(503, "Result storage busy. Please try again later.")
        pending = len(rows) < total
        if pending and not SLOTS.acquire(blocking=False):
            raise HTTPException(503, "Two full FDA searches are already loading. Please retry shortly.")
        token = secrets.token_urlsafe(32)
        job = {"created": time.monotonic(), "total": total, "loaded": 0, "status": "loading", "columns": [], "path": str(ROOT / (token + ".sqlite")), "source": source}
        with sqlite3.connect(job["path"]) as db:
            db.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        JOBS[token] = job
        add_rows(job, rows)
        if pending:
            threading.Thread(target=collect_fda, args=(job, next_url), daemon=True).start()
        else:
            finish(job)
    return token


def rows_page(job, offset, limit):
    with sqlite3.connect(job["path"]) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT payload FROM records ORDER BY id LIMIT ? OFFSET ?", (limit, offset))]


@router.get("/results/{token}/data")
def data(token: str, offset: int = Query(0, ge=0)):
    job = get_job(token)
    return JSONResponse({"status": job["status"], "total": job["total"], "loaded": job["loaded"], "error": job.get("error"), "rows": rows_page(job, offset, 100)}, headers=HEADERS)


def csv_cell(value):
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value if value is not None else "")
    # Protect spreadsheet users from formulas embedded in source data.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@router.get("/results/{token}/download")
def download(token: str):
    job = get_job(token)
    if job["status"] != "complete":
        raise HTTPException(409, "Full download available only after all records finish loading.")
    def stream():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(job["columns"])
        yield "\ufeff" + buffer.getvalue()
        with sqlite3.connect(job["path"]) as db:
            for (payload,) in db.execute("SELECT payload FROM records ORDER BY id"):
                row = json.loads(payload)
                buffer.seek(0)
                buffer.truncate(0)
                writer.writerow([csv_cell(row.get(c)) for c in job["columns"]])
                yield buffer.getvalue()
    return StreamingResponse(stream(), media_type="text/csv; charset=utf-8", headers={**HEADERS, "Content-Disposition": 'attachment; filename="all_matching_records.csv"'})


@router.get("/results/{token}", response_class=HTMLResponse)
def page(token: str):
    get_job(token)
    return HTMLResponse(PAGE, headers=HEADERS)


PAGE = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>All research records</title>
<style>body{font:16px system-ui;margin:24px;background:#f4f6f8;color:#172033}button,a{display:inline-block;padding:10px;margin:4px}table{border-collapse:collapse;background:white}td,th{padding:10px;border:1px solid #ddd;max-width:380px;white-space:pre-wrap;overflow-wrap:anywhere}#table{overflow:auto}a[hidden]{display:none}</style></head><body>
<h1>All matching research records</h1><p id="status">Loading…</p><p>Every matched record is accessible here. Browse 100 rows per page or download the complete CSV. Links expire after one hour or service restart; keep this link private.</p>
<a id="download" hidden>Download all records (CSV)</a><button id="prev">Previous</button><button id="next">Next</button><span id="range"></span><div id="table"></div>
<script>let offset=0,loaded=0;const base=location.pathname;
document.getElementById('prev').onclick=()=>{offset=Math.max(0,offset-100);refresh()};document.getElementById('next').onclick=()=>{if(offset+100<loaded){offset+=100;refresh()}};
async function refresh(){try{let r=await fetch(base+'/data?offset='+offset,{cache:'no-store'});if(!r.ok)throw Error('Results expired or unavailable. Run your search again.');let d=await r.json();loaded=d.loaded;
document.getElementById('status').textContent=d.error||('Loaded '+d.loaded+' of '+d.total+' records — '+d.status);
let dl=document.getElementById('download');dl.hidden=d.status!=='complete';dl.href=base+'/download';document.getElementById('prev').disabled=offset===0;document.getElementById('next').disabled=offset+100>=loaded;
document.getElementById('range').textContent=d.rows.length?((offset+1)+'–'+(offset+d.rows.length)):'No records';
let cols=[...new Set(d.rows.flatMap(x=>Object.keys(x)))],table=document.createElement('table'),head=document.createElement('tr');for(let c of cols){let th=document.createElement('th');th.textContent=c;head.append(th)}table.append(head);
for(let row of d.rows){let tr=document.createElement('tr');for(let c of cols){let td=document.createElement('td'),v=row[c];td.textContent=v==null?'':(typeof v==='object'?JSON.stringify(v):String(v));tr.append(td)}table.append(tr)}document.getElementById('table').replaceChildren(table);
if(d.status==='loading')setTimeout(refresh,3000);
}catch(e){document.getElementById('status').textContent=e.message}}refresh();</script></body></html>'''
