"""Shared Streamlit UI helpers: centered empty state + historical stats cache."""

from typing import Any

import streamlit as st

from src.calculations import compute_historical_stats, historical_cache_key


def render_empty_state(
    icon: str,
    message: str,
    *,
    title: str = "Nenhum registro ainda",
    caption: str | None = None,
) -> None:
    """Centered bordered card with icon, title, message and optional caption."""
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(icon, text_alignment="center")
            st.subheader(title)
            st.markdown(message)
            if caption:
                st.caption(caption)


def get_historical_stats(
    conn: Any,
    year_month: str,
    goal: float,
    active_mods: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Return cached-or-fresh historical stats; second value True when recomputed."""
    cache_key = historical_cache_key(year_month, goal, active_mods)
    cached = st.session_state.get("historical_cache")
    if cached is not None and cached.get("key") == cache_key:
        return cached["stats"], False
    with st.spinner("Analisando dados históricos..."):
        stats = compute_historical_stats(conn, year_month, goal, active_mods)
    st.session_state.historical_cache = {"key": cache_key, "stats": stats}
    return stats, True
