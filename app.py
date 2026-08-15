"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprints 1–5: sidebar, SQLite persistence, KPI cards, charts,
LLM insights, settings, session_state wiring.
"""

import streamlit as st

from src.auth_store import AUTH_PATH, AuthError, load_auth
from src.cookies import get_last_tab_index, set_last_tab_index
from src.db import get_connection, init_db
from src.ui.analysis import render_analysis_tab
from src.ui.chat import render_chat_tab
from src.ui.login import (
    render_login_gate,
    render_logout_button,
    render_sidebar_footer,
    render_sidebar_header,
)
from src.ui.month import render_month_tab
from src.ui.settings import render_settings_tab
from src.ui.sidebar import render_sidebar
from src.ui.today import render_today_tab

# Page config — MUST be first Streamlit command
st.set_page_config(
    page_title="Radtracker",
    page_icon=":material/monitor_heart:",
    layout="wide",
    initial_sidebar_state="auto",
)

# Tab labels (stRadio) render at 14px while sidebar exam names render at
# 16px. Streamlit has no per-component font-size API — this single rule
# aligns the tabs with the sidebar text, per owner's request.
st.markdown(
    "<style>div[data-testid='stRadio'] label p { font-size: 1rem; }</style>",
    unsafe_allow_html=True,
)

# Authentication gate — fail loud when not configured; blocks until authenticated
try:
    auth = load_auth(AUTH_PATH)
except AuthError as exc:
    st.error(f"Autenticação não configurada: {exc}")
    st.markdown("Execute o deploy Ansible ou o script `radtracker-auth` via SSH.")
    st.stop()

render_login_gate(auth)
render_sidebar_header()
# Database initialization (idempotent)
conn = get_connection()
init_db(conn)

# Sidebar
render_sidebar(conn)
render_sidebar_footer(auth)

# ── Navigation (cookie-persisted tab selection) ──
TAB_LABELS = [
    ":material/today: Hoje",
    ":material/calendar_month: Mês Atual",
    ":material/trending_up: Análise",
    ":material/smart_toy: Chat IA",
    ":material/settings: Configuração",
]

if "active_tab_idx" not in st.session_state:
    try:
        st.session_state.active_tab_idx = int(get_last_tab_index())
    except Exception:
        st.session_state.active_tab_idx = 0
    if not 0 <= st.session_state.active_tab_idx < len(TAB_LABELS):
        st.session_state.active_tab_idx = 0

tab_col, logout_col = st.columns([7, 1.2], vertical_alignment="center")
with tab_col:
    active = st.radio(
        "Navegação",
        TAB_LABELS,
        index=st.session_state.active_tab_idx,
        horizontal=True,
        label_visibility="collapsed",
        key="main_tabs",
    )
with logout_col:
    render_logout_button()

selected_idx = TAB_LABELS.index(active)
if selected_idx != st.session_state.active_tab_idx:
    st.session_state.active_tab_idx = selected_idx
    set_last_tab_index(str(selected_idx))

# ── Tab content ──
if selected_idx == 0:
    render_today_tab(conn)
elif selected_idx == 1:
    render_month_tab(conn)
elif selected_idx == 2:
    render_analysis_tab(conn)
elif selected_idx == 3:
    render_chat_tab(conn)
else:
    render_settings_tab(conn)
