"""Stock-Planning's React grid with client-side filters and full-window details."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
_grid=components.declare_component("workspace_grid",path=str(Path(__file__).parent/"workspace_dist"))

def data_table(frame, key, title="Data", description=""):
    frame=frame.copy()
    frame.columns=frame.columns.map(str)
    # pandas encodes dates, NaN and numpy scalars safely for the component protocol.
    rows=json.loads(frame.to_json(orient="values",date_format="iso",default_handler=str))
    _grid(headers=list(frame.columns),rows=rows,title=title,description=description,
          role=st.session_state.get("workspace_role","viewer"),storageKey=key,key=key,default=None)

def workspace_theme():
    st.markdown("""<style>
    [data-testid='stAppViewContainer']{background:#F4F6F8!important}
    [data-testid='stSidebar']{background:#fff!important;border-right:1px solid #e0e8e3}
    .block-container{max-width:1900px;padding-top:2rem}
    h1,h2,h3{color:#285e4c!important}
    button[kind='primary']{background:#258467!important;border-color:#258467!important;color:white!important}
    [data-testid='stMetric']{background:#fff!important;border:1px solid #e0e8e3;border-radius:10px;padding:16px;color:#285e4c!important}
    [data-testid='stMetric'] label,[data-testid='stMetricValue']{color:#285e4c!important}
    [data-testid='stTabs'] button[aria-selected='true']{color:#258467!important}
    [data-testid='stTabs'] [role='tablist']{background:#fff;border:1px solid #e0e8e3;border-radius:10px;padding:6px;gap:6px;margin:12px 0 6px;flex-wrap:wrap;height:auto}
    [data-testid='stTabs'] [role='tab']{border-radius:7px;padding:11px 18px;height:auto;white-space:normal;color:#667c70}
    [data-testid='stTabs'] [role='tab'][aria-selected='true']{background:#eaf4ef;color:#226d51!important;font-weight:600}
    [data-testid='stTabs'] [data-baseweb='tab-highlight'],[data-testid='stTabs'] [data-baseweb='tab-border']{display:none}
    [data-testid='stExpander']{background:#fff;border-radius:9px}
    [data-testid='stCaptionContainer']{color:#718278;font-size:13px;line-height:1.6}
    </style>""",unsafe_allow_html=True)
