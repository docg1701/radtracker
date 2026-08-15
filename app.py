"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprints 1–5: sidebar, SQLite persistence, KPI cards, charts,
LLM insights, settings, session_state wiring.
"""

import logging

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
    # Detail goes to the server log only — the browser must not expose file
    # paths, schema internals, or validation messages.
    logging.getLogger(__name__).error("auth gate: %s", exc)
    st.error("Autenticação indisponível neste servidor. Contate o administrador.")
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

# index= is only used while the radio has no session state (first render);
# afterwards key="main_tabs" owns the selection (see docs/meta-prompt.md).
try:
    cookie_idx = int(get_last_tab_index())
except Exception:
    cookie_idx = 0

with st.container(horizontal=True, vertical_alignment="center"):
    active = st.radio(
        "Navegação",
        TAB_LABELS,
        index=cookie_idx if 0 <= cookie_idx < len(TAB_LABELS) else 0,
        horizontal=True,
        label_visibility="collapsed",
        key="main_tabs",
    )
    st.space("stretch")
    render_logout_button()

selected_idx = TAB_LABELS.index(active)
if str(selected_idx) != get_last_tab_index():
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
