"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprint 1: sidebar + SQLite + 4 placeholder tabs.
"""

import streamlit as st

from src.db import get_connection, init_db
from src.ui.sidebar import render_sidebar

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

# Tabs (4 placeholders)
tab_hoje, tab_mes, tab_analise, tab_config = st.tabs([
    "📊 Hoje",
    "📅 Mês Atual",
    "📈 Análise",
    "⚙️ Config",
])

with tab_hoje:
    st.header("📊 Hoje")
    st.info("Em breve — dados de hoje (Sprint 2)")

with tab_mes:
    st.header("📅 Mês Atual")
    st.info("Em breve — visão mensal (Sprint 3)")

with tab_analise:
    st.header("📈 Análise")
    st.info("Em breve — análises e insights (Sprint 4)")

with tab_config:
    st.header("⚙️ Configurações")
    st.info("Em breve — preços e meta (Sprint 5)")
