"""
Sidebar data-entry form — v2 dynamic modalities.

Renders the app title, greeting, date picker, dynamic modality inputs
(based on st.session_state.active_modalities), and the save button.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.db import load_daily_items, upsert_daily_items
from src.i18n import t
from src.ui.settings import ensure_settings


def render_sidebar(conn: Any) -> None:
    """
    Render the complete sidebar: header, date picker, dynamic modality inputs, save.

    On save:
      - Calls db.upsert_daily_items() with current form values.
      - Shows a toast notification.

    No st.rerun(): the button click already triggers a full script run and
    the upsert happens before the tabs render, so the dashboard refreshes
    in the same run. A st.rerun() here would abort the run BEFORE the tab
    radio renders — Streamlit deletes the state of any widget not rendered
    in a run, so the active tab would reset to the cookie fallback.
    """
    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    lang = st.session_state.get("lang", "en")

    with st.sidebar:
        # Greeting — the Radtracker title + Sair row above comes from
        # render_sidebar_header() (src/ui/login.py), called before this.
        user_name = st.session_state.get("user_name", "")
        if user_name:
            st.markdown(t("web.sidebar.greeting", name=user_name))

        # Date picker — label and box on the same row
        col_label, col_input = st.columns([1, 3], vertical_alignment="center")
        with col_label:
            st.markdown(t("web.sidebar.date_label"))
        with col_input:
            selected_date = st.date_input(
                t("web.sidebar.date_label"),
                value=date.today(),
                format="MM/DD/YYYY" if lang == "en" else "DD/MM/YYYY",
                max_value=date.today(),
                label_visibility="collapsed",
            )
        date_str = selected_date.isoformat()

        if not active_mods:
            st.info(t("web.sidebar.no_modalities"))
            return

        # Pre-fill from existing data
        existing = load_daily_items(conn, date_str)

        # Modality inputs — label + input on same row
        values: dict[str, int] = {}

        for m in active_mods:
            slug = m["slug"]
            label = m["label"]
            default_val = existing.get(slug, 0)

            col_label, col_input = st.columns([3, 1])
            with col_label:
                st.write(label)
            with col_input:
                val = st.number_input(
                    label, min_value=0, step=1,
                    value=default_val,
                    key=f"sidebar_{slug}_{date_str}",
                    label_visibility="collapsed",
                )
                values[slug] = val

        # Save button — natural width, left aligned, same style as Sair
        if st.button(
            t("web.sidebar.save"), icon=":material/save:",
        ):
            with st.spinner(t("web.sidebar.saving")):
                # Send all values — zeros will be deleted, non-zeros upserted
                upsert_daily_items(conn, date_str, values)

            st.cache_data.clear()
            formatted = selected_date.strftime("%m/%d" if lang == "en" else "%d/%m")
            st.toast(
                t("web.sidebar.saved_toast", date=formatted),
                icon=":material/check_circle:",
            )
