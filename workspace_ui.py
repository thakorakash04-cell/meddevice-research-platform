"""Stock-Planning's React grid with client-side filters and full-window details."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
_grid=components.declare_component("workspace_grid",path=str(Path(__file__).parent/"workspace_dist"))

def data_table(frame, key, title="Data"):
    frame=frame.copy()
    frame.columns=frame.columns.map(str)
    # pandas encodes dates, NaN and numpy scalars safely for the component protocol.
    rows=json.loads(frame.to_json(orient="values",date_format="iso",default_handler=str))
    _grid(headers=list(frame.columns),rows=rows,title=title,
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
    </style>""",unsafe_allow_html=True)
