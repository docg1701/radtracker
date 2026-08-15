"""
Month tab — monthly KPI row, progress gauge, daily earnings line, modality donut.

v2: dynamic modalities.
"""

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from src.calculations import (
    _compute_daily_earnings_from_items,
    attach_revenue,
    compute_daily_target,
    compute_monthly_stats,
)
from src.charts import (
    build_monthly_earnings_chart,
    build_monthly_modality_donut,
    build_progress_gauge,
)
from src.db import load_month_items
from src.formatting import fmt_money, md_escape
from src.i18n import t
from src.ui.common import render_empty_state
from src.ui.settings import ensure_settings


def render_month_tab(conn: Any) -> None:
    """Render the complete This Month tab."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    goal = st.session_state.goal

    if not active_mods:
        render_empty_state(
            ":material/calendar_month:",
            t("web.tabs.no_modalities"),
        )
        return

    lang = st.session_state.get("lang", "en")
    stats = compute_monthly_stats(conn, year_month, goal, active_mods)
    daily_target = compute_daily_target(goal, stats["total_calendar_days"])

    if stats["days_worked"] == 0:
        render_empty_state(
            ":material/calendar_month:",
            t("web.month.start_hint"),
            caption=t("web.month.start_caption"),
        )
        return

    # ── KPI Row ──
    _render_kpi_row(stats, goal, daily_target, lang)

    # ── Progress Gauge ──
    pct_goal = stats["pct_goal"]
    gauge = build_progress_gauge(pct_goal, lang)
    st.plotly_chart(gauge, width="stretch")

    # ── Star rating ──
    # ponytail: full-star rounding replaces fractional star_rating;
    # add half-stars if granularity matters
    stars = round(min(5.0, pct_goal / 20.0))
    st.markdown("★" * stars + "☆" * (5 - stars))

    # ── Celebration rain ──
    _maybe_celebrate(pct_goal, year_month)

    # ── Build daily earnings dataframe from items ──
    earn_df = _build_earnings_dataframe(conn, year_month)

    # ── Charts ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(f":material/trending_up: {t('web.month.chart.daily')}")
        if not earn_df.empty:
            line_chart = build_monthly_earnings_chart(
                earn_df, daily_target, year_month, lang
            )
            st.plotly_chart(line_chart, width="stretch")
        else:
            st.info(t("web.month.chart.no_daily"))

    with col_right:
        st.subheader(f":material/pie_chart: {t('web.month.chart.by_modality')}")
        items_df = attach_revenue(conn, load_month_items(conn, year_month))
        donut = build_monthly_modality_donut(items_df, active_mods, lang)
        st.plotly_chart(donut, width="stretch")

    # ── Rhythm Alert ──
    _render_rhythm_alert(stats, goal, lang)

    # ── Raw data toggle ──
    if not earn_df.empty:
        with st.expander(t("web.common.view_raw_data")):
            st.text(earn_df.to_string(index=False))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_earnings_dataframe(
    conn: Any, year_month: str,
) -> pd.DataFrame:
    """Build a daily earnings DataFrame (price-vigent revenue) from items."""
    items_df = load_month_items(conn, year_month)
    if items_df.empty:
        return pd.DataFrame()

    daily = _compute_daily_earnings_from_items(conn, items_df)
    return daily[["date", "earnings"]]


def _render_kpi_row(
    stats: dict[str, Any], goal: float, daily_target: float, lang: str,
) -> None:
    """Render the 4 KPI metric cards."""
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=f":material/payments: {t('web.month.kpi.mtd')}",
                value=fmt_money(stats["mtd_earnings"], lang),
                delta=md_escape(
                    t(
                        "web.month.kpi.projected",
                        value=fmt_money(stats["projection_month_end"], lang),
                    )
                ),
                delta_color="off",
            )

    with k2:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=f":material/target: {t('web.month.kpi.goal_pct')}",
                value=f"{stats['pct_goal']:.0f}%",
                delta=md_escape(
                    f"{fmt_money(stats['mtd_earnings'], lang)} / {fmt_money(goal, lang)}"
                ),
                delta_color="off",
            )

    with k3:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=f":material/calendar_month: {t('web.month.kpi.days')}",
                value=t(
                    "web.month.kpi.days_value",
                    worked=stats["days_worked"],
                    total=stats["total_calendar_days"],
                ),
                delta=t(
                    "web.month.kpi.remaining",
                    count=stats["remaining_days"],
                ),
                delta_color="off",
            )

    with k4:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=f":material/trending_up: {t('web.month.kpi.daily_avg')}",
                value=fmt_money(stats["daily_avg"], lang),
                delta=t(
                    "web.month.kpi.target",
                    value=md_escape(fmt_money(daily_target, lang)),
                ),
                delta_color="off",
            )


def _should_show_rhythm_alert(stats: dict[str, Any], goal: float) -> bool:
    """True when the user is behind pace enough to warrant a warning.

    Early-month suppression is based on elapsed calendar days (not days
    worked), consistent with the per-calendar-day productivity model where
    every day counts as a potential production day.
    """
    total = stats["total_calendar_days"]
    if total == 0:
        return False
    if stats["elapsed_days"] < 5:
        return False
    if stats["mtd_earnings"] >= goal:
        return False
    if stats["remaining_days"] == 0:
        return False
    expected_pct = (stats["elapsed_days"] / total) * 100.0
    return stats["pct_goal"] < expected_pct


def _render_rhythm_alert(stats: dict[str, Any], goal: float, lang: str) -> None:
    """Show a warning if behind pace."""
    if not _should_show_rhythm_alert(stats, goal):
        return

    missing = goal - stats["mtd_earnings"]
    remaining = stats["remaining_days"]
    needed = stats["daily_target_needed"]

    day_text = (
        t("web.month.day_one")
        if remaining == 1
        else t("web.month.day_many", count=remaining)
    )

    st.warning(
        t(
            "web.month.rhythm_alert",
            name=st.session_state.get("user_name", ""),
            goal=md_escape(fmt_money(goal, lang)),
            missing=md_escape(fmt_money(missing, lang)),
            days=day_text,
            needed=md_escape(fmt_money(needed, lang)),
            avg=md_escape(fmt_money(stats["daily_avg"], lang)),
        )
    )


def _maybe_celebrate(pct_goal: float, year_month: str) -> None:
    """Trigger balloons when goal is achieved."""
    if pct_goal < 100.0:
        return
    celebrate_key = f"goal_celebrated_{year_month}"
    if st.session_state.get(celebrate_key):
        return
    st.balloons()
    st.toast(f":material/check_circle: {t('web.month.goal_toast')}")
    st.session_state[celebrate_key] = True
