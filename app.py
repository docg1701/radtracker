"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprint 1: sidebar + SQLite persistence (3 tables, UPSERT, toast notifications).
Sprint 2: Hoje tab (KPI cards, modality donut, daily sparkline, empty state).
Sprint 3: Mês tab (progress gauge, daily trend, modality donut, rhythm alert).
Sprint 4: Análise tab (rule insights, MA7/MA30, WoW, modality mix evolution).
"""

import streamlit as st

from src.db import get_connection, init_db
from src.ui.sidebar import render_sidebar
from src.ui.today import render_today_tab
from src.ui.month import render_month_tab
from src.ui.analysis import render_analysis_tab

# Page config — MUST be first Streamlit command
st.set_page_config(
    page_title="radtracker",
    page_icon="📊",
    layout="wide",
)

# Database initialization (idempotent)
conn = get_connection()
init_db(conn)

# Sidebar
render_sidebar(conn)

# Tabs (3 implemented, 1 placeholder)
tab_hoje, tab_mes, tab_analise, tab_config = st.tabs([
    "📊 Hoje",
    "📅 Mês Atual",
    "📈 Análise",
    "⚙️ Config",
])

with tab_hoje:
    render_today_tab(conn)

with tab_mes:
    render_month_tab(conn)

with tab_analise:
    render_analysis_tab(conn)

with tab_config:
    st.header("⚙️ Configurações")
    st.info("Em breve — preços e meta (Sprint 5)")
