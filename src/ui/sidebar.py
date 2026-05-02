"""
Sidebar data-entry form — v2 dynamic modalities.

Renders the app title, greeting, date picker, dynamic modality inputs
(based on st.session_state.active_modalities), and the save button.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.db import load_daily_items, upsert_daily_items
from src.ui.settings import ensure_settings


def render_sidebar(conn: Any) -> None:
    """
    Render the complete sidebar: header, date picker, dynamic modality inputs, save.

    On save:
      - Calls db.upsert_daily_items() with current form values.
      - Shows a toast notification.
      - Triggers st.rerun() to refresh the dashboard.
    """
    ensure_settings(conn)
    active_mods = st.session_state.active_modalities

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

        if not active_mods:
            st.info(
                "Nenhuma modalidade ativa. Configure os preços e a "
                "produtividade na aba **:material/settings: Configuração**."
            )
            return

        # Pre-fill from existing data
        existing = load_daily_items(conn, date_str)

        # Modality inputs in compact rows
        values: dict[str, int] = {}
        cols = st.columns(3)
        col_idx = 0

        for m in active_mods:
            slug = m["slug"]
            label = m["label"]
            default_val = existing.get(slug, 0)

            with cols[col_idx % 3]:
                val = st.number_input(
                    label, min_value=0, step=1,
                    value=default_val,
                    key=f"sidebar_{slug}_{date_str}",
                )
                values[slug] = val
            col_idx += 1

        # Save button
        if st.button(
            "Salvar produção", icon=":material/save:",
            type="primary", width="stretch",
        ):
            with st.spinner("Salvando..."):
                # Only save non-zero values
                to_save = {s: c for s, c in values.items() if c > 0}
                upsert_daily_items(conn, date_str, to_save)

            st.session_state.pop("historical_cache", None)
            formatted = selected_date.strftime("%d/%m")
            st.toast(f"Produção de {formatted} salva!", icon=":material/check_circle:")
            st.rerun()

        # Footer
        st.caption("radtracker v1.2 · local")
