"""Shared Streamlit UI helpers: centered empty state + cached historical stats."""

from typing import Any

import streamlit as st

from src.calculations import compute_historical_stats
from src.i18n import t


def render_empty_state(
    icon: str,
    message: str,
    *,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """Centered bordered card with icon, title, message and optional caption."""
    if title is None:
        title = t("web.empty.default_title")
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
) -> dict[str, Any]:
    """Return cached historical stats; recomputed when goal or modalities change.

    Cached via st.cache_data (invalidation: st.cache_data.clear() on save).
    Spinner lives at the call site — decorator-time strings can't see the
    active language.
    """
    mods_key = tuple(
        (m["slug"], m["price"], m["exams_per_hour"]) for m in active_mods
    )
    with st.spinner(t("web.common.loading_history")):
        return _cached_historical_stats(conn, year_month, goal, mods_key)


@st.cache_data
def _cached_historical_stats(
    _conn: Any,
    year_month: str,
    goal: float,
    mods_key: tuple[tuple[str, float, float], ...],
) -> dict[str, Any]:
    mods = [
        {"slug": s, "price": p, "exams_per_hour": e} for s, p, e in mods_key
    ]
    return compute_historical_stats(_conn, year_month, goal, mods)
