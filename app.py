"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprints 1–5: sidebar, SQLite persistence, KPI cards, charts,
LLM insights, settings, session_state wiring.
"""

import streamlit as st

from src.db import get_connection, init_db
from src.ui.analysis import render_analysis_tab
from src.ui.month import render_month_tab
from src.ui.settings import render_settings_tab
from src.ui.sidebar import render_sidebar
from src.ui.today import render_today_tab

# Page config — MUST be first Streamlit command
st.set_page_config(
    page_title="radtracker",
    page_icon=":material/monitor_heart:",
    layout="wide",
    initial_sidebar_state="auto",
)

# Database initialization (idempotent)
conn = get_connection()
init_db(conn)

# Sidebar
render_sidebar(conn)

# Tabs (4 implemented)
tab_hoje, tab_mes, tab_analise, tab_config = st.tabs([
    ":material/today: Hoje",
    ":material/calendar_month: Mês Atual",
    ":material/trending_up: Análise",
    ":material/settings: Config",
])

with tab_hoje:
    render_today_tab(conn)

with tab_mes:
    render_month_tab(conn)

with tab_analise:
    render_analysis_tab(conn)

with tab_config:
    render_settings_tab(conn)
