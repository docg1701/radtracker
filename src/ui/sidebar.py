"""
Sidebar data-entry form.

Renders the app title, greeting, date picker, 3 modality inputs,
and the save button. Handles UPSERT via db.upsert_daily().
"""

import streamlit as st
from datetime import date

from src.db import upsert_daily, load_daily


def render_sidebar(conn) -> None:
    """
    Render the complete sidebar: header, date picker, modality inputs, save button.

    On save:
      - Calls db.upsert_daily() with current form values.
      - Shows a toast notification (insert or update).
      - Triggers st.rerun() to refresh the dashboard.
    """
    with st.sidebar:
        # Header
        st.title("📊 radtracker")
        st.markdown("Olá, **Galvani** 👋")

        # Date picker
        selected_date = st.date_input(
            "📅 Data",
            value=date.today(),
            format="DD/MM/YYYY",
            max_value=date.today(),
        )
        date_str = selected_date.isoformat()

        # Pre-fill from existing data
        existing = load_daily(conn, date_str)
        default_rm = existing["rm_count"] if existing else 0
        default_tc = existing["tc_count"] if existing else 0
        default_rx = existing["rx_count"] if existing else 0

        # Modality inputs (3 columns)
        cols = st.columns(3)
        with cols[0]:
            rm = st.number_input("RM", min_value=0, step=1, value=default_rm, key="sb_rm")
        with cols[1]:
            tc = st.number_input("TC", min_value=0, step=1, value=default_tc, key="sb_tc")
        with cols[2]:
            rx = st.number_input("RX", min_value=0, step=1, value=default_rx, key="sb_rx")

        # Save button
        if st.button("💾 Salvar produção", type="primary", use_container_width=True):
            upsert_daily(conn, date_str, rm, tc, rx)
            formatted = selected_date.strftime("%d/%m")
            if existing:
                st.toast(f"📝 Produção de {formatted} atualizada!", icon="📝")
            else:
                st.toast(f"✅ Produção de {formatted} salva!", icon="✅")
            st.rerun()

        # Footer
        st.sidebar.divider()
        st.sidebar.caption("radtracker v1.0 · local")
