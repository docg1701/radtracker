"""
Sidebar data-entry form.

Renders the app title, greeting, date picker, 3 modality inputs,
and the save button. Handles UPSERT via db.upsert_daily().
"""

from datetime import date
from typing import Any

import streamlit as st

from src.db import load_daily, upsert_daily


def render_sidebar(conn: Any) -> None:
    """
    Render the complete sidebar: header, date picker, modality inputs, save button.

    On save:
      - Calls db.upsert_daily() with current form values.
      - Shows a toast notification (insert or update).
      - Triggers st.rerun() to refresh the dashboard.
    """
    with st.sidebar:
        # Header
        st.markdown("**radtracker**")
        user_name = st.session_state.get("user_name", "Galvani")
        st.markdown(f"Olá, {user_name}.")

        # Date picker
        selected_date = st.date_input(
            "Data",
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
            rm = st.number_input("RM", min_value=0, step=1, value=default_rm, key=f"rm_{date_str}")
        with cols[1]:
            tc = st.number_input("TC", min_value=0, step=1, value=default_tc, key=f"tc_{date_str}")
        with cols[2]:
            rx = st.number_input("RX", min_value=0, step=1, value=default_rx, key=f"rx_{date_str}")

        # Save button
        if st.button(
            "Salvar produção", icon=":material/save:",
            type="primary", width="stretch",
        ):
            with st.spinner("Salvando..."):
                upsert_daily(conn, date_str, rm, tc, rx)
            st.session_state.pop("historical_cache", None)
            formatted = selected_date.strftime("%d/%m")
            if existing:
                st.toast(f"Produção de {formatted} atualizada!", icon=":material/check_circle:")
            else:
                st.toast(f"Produção de {formatted} salva!", icon=":material/check_circle:")
            st.rerun()

        # Footer
        st.caption("radtracker v1.0 · local")
