"""Shared authenticated workspace; no default or public account registration."""
import os,time
import pandas as pd
import streamlit as st
from workspace_store import Store,AccessDenied

@st.cache_resource
def initialize(url,username,password):
    store=Store(url);store.bootstrap_admin(username,password);return store

def sign_out():
    st.session_state.clear();st.rerun()

def login_page(store):
    _,middle,_=st.columns([1,1.3,1])
    with middle:
        st.title("MedDevice Research Platform")
        st.write("Sign in to your workspace.")
        with st.form("login",clear_on_submit=True):
            username=st.text_input("Username",autocomplete="username",key="login_username")
            password=st.text_input("Password",type="password",autocomplete="current-password",key="login_password")
            submit=st.form_submit_button("Sign in",type="primary",width="stretch")
        if submit:
            actor=store.login(username,password)
            if actor:
                st.session_state.actor=actor
                st.session_state.login_at=st.session_state.last_active=time.time()
                st.rerun()
            st.error("Invalid credentials, disabled account, or temporary lock. After repeated failures, wait 15 minutes.")
        st.caption("Accounts are created by the administrator. There is no public registration.")
    st.stop()

def require_admin(store,actor):
    if store.identity(actor)["role"]!="admin":
        raise AccessDenied("Administrator access required.")

def user_page(store,actor):
    require_admin(store,actor)
    st.title("Manage viewer accounts")
    st.caption("Only the configured administrator can create, disable or reset viewer accounts.")
    users=store.users(actor)
    st.table(pd.DataFrame(users)[["username","role","active"]])
    with st.form("create_viewer",clear_on_submit=True):
        st.subheader("Create viewer")
        username=st.text_input("New viewer username")
        password=st.text_input("Initial password (at least 12 characters)",type="password")
        create=st.form_submit_button("Create viewer",type="primary")
    if create:
        try:store.create_viewer(actor,username,password);st.success("Viewer created. Share their credentials privately.")
        except ValueError as exc:st.error(str(exc))
    viewers=[r["username"] for r in users if r["role"]=="viewer"]
    if viewers:
        with st.form("update_viewer",clear_on_submit=True):
            st.subheader("Reset or enable/disable viewer")
            selected=st.selectbox("Viewer",viewers)
            action=st.selectbox("Action",["Reset password","Disable account","Enable account"])
            new_password=st.text_input("New password for reset only",type="password")
            update=st.form_submit_button("Apply change")
        if update:
            try:
                if action=="Reset password":store.update_viewer(actor,selected,password=new_password)
                else:store.update_viewer(actor,selected,active=action=="Enable account")
                st.success("Account updated. Existing sessions for this user have been revoked.")
            except ValueError as exc:st.error(str(exc))



def require_workspace():
    try: secrets=dict(st.secrets)
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError): secrets={}
    cfg={k:str(secrets.get(k,os.environ.get(k,""))) for k in ("DATABASE_URL","ADMIN_USERNAME","ADMIN_PASSWORD")}
    if not all(cfg.values()) or len(cfg["ADMIN_PASSWORD"])<12:
        st.title("MedDevice Research Platform — setup")
        st.info("Set DATABASE_URL, ADMIN_USERNAME and ADMIN_PASSWORD in Streamlit Secrets. See WORKSPACE_SETUP.md. No default login is enabled.")
        st.stop()
    if os.environ.get("STREAMLIT_SHARING_MODE") or os.environ.get("HOSTNAME","").startswith("streamlit"):
        if cfg["DATABASE_URL"].startswith("sqlite:"):
            st.error("Use PostgreSQL for persistent accounts on Streamlit Cloud.");st.stop()
    try:store=initialize(cfg["DATABASE_URL"],cfg["ADMIN_USERNAME"],cfg["ADMIN_PASSWORD"])
    except Exception:
        st.error("Cannot connect to the account database. Check Streamlit Secrets.");st.stop()
    actor=st.session_state.get("actor")
    if actor is None:login_page(store)
    now=time.time()
    if now-st.session_state.get("login_at",0)>8*3600 or now-st.session_state.get("last_active",0)>1800:sign_out()
    try:identity=store.identity(actor)
    except AccessDenied:sign_out()
    st.session_state.last_active=now
    st.session_state.workspace_role=identity["role"]
    with st.sidebar:
        st.caption("Signed in as "+identity["username"]+" · "+identity["role"])
        if st.button("Sign out",key="workspace_signout"):sign_out()
        if identity["role"]=="admin":
            manage=st.toggle("Manage users",key="workspace_users")
        else:manage=False
    if manage:
        user_page(store,actor);st.stop()
    return store,actor,identity

def can_export():
    return st.session_state.get("workspace_role")=="admin"

def admin_download(*args,**kwargs):
    if not can_export():return False
    return st.download_button(*args,**kwargs)
