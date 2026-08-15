"""
Today tab — KPI cards, modality donut, and sparkline.

v2: dynamic modalities from st.session_state.active_modalities.
"""

from datetime import date
from typing import Any, Literal

import pandas as pd
import streamlit as st

from src.calculations import (
    _compute_daily_earnings_from_items,
    compute_daily_stats,
    compute_monthly_stats,
)
from src.charts import build_daily_sparkline, build_modality_bar
from src.db import load_month_items
from src.formatting import fmt_money, md_escape
from src.i18n import t
from src.ui.common import render_empty_state
from src.ui.settings import ensure_settings


def render_today_tab(conn: Any) -> None:
    """Render the complete "Hoje" tab."""
    today = date.today()
    today_str = today.isoformat()
    year_month = today_str[:7]

    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    goal = st.session_state.goal

    if not active_mods:
        render_empty_state(
            ":material/content_paste:",
            t("web.tabs.no_modalities_plain"),
        )
        return

    lang = st.session_state.get("lang", "en")
    stats = compute_daily_stats(conn, today_str, active_mods)

    if not stats["has_data"]:
        render_empty_state(
            ":material/content_paste:",
            t("web.today.start_hint"),
            caption=t("web.today.start_caption"),
        )
        return

    # ── KPI Row ──
    _render_kpi_row(stats, goal, conn, year_month, active_mods, lang)

    # ── Donut + Sparkline ──
    spark = _build_sparkline_figure(conn, year_month, active_mods, lang)

    st.subheader(f":material/dashboard: {t('web.today.overview')}")
    col_left, col_right = st.columns(2)
    with col_left:
        bar_chart = build_modality_bar(
            stats["modality_counts"], stats["modality_labels"],
            modalities=st.session_state.active_modalities,
            lang=lang,
        )
        st.plotly_chart(bar_chart, width="stretch")
    with col_right:
        if spark is not None:
            st.plotly_chart(spark, width="stretch")

    # ── Raw data toggle ──
    raw_lines = [f"{t('web.sidebar.date_label')} {today_str}"]
    for slug, count in stats["modality_counts"].items():
        label = stats["modality_labels"].get(slug, slug)
        raw_lines.append(f"{label}: {count}")
    raw_lines.append(f"{t('web.today.raw.revenue')} {fmt_money(stats['earnings_today'], lang)}")
    raw_lines.append(f"{t('web.today.raw.hours')} {stats['estimated_hours']:.1f}h")
    with st.expander(t("web.common.view_raw_data")):
        st.text("\n".join(raw_lines))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _render_kpi_row(
    stats: dict[str, Any],
    goal: float,
    conn: Any,
    year_month: str,
    active_mods: list[dict[str, Any]],
    lang: str,
) -> None:
    """Render the 4 KPI metric cards."""
    k1, k2, k3, k4 = st.columns(4, vertical_alignment="center")

    # ── Card 1: Faturamento Hoje ──
    with k1:
        with st.container(border=True, height="stretch"):
            earnings = stats["earnings_today"]
            if stats["delta_pct"] is not None:
                delta_str = t(
                    "web.today.kpi.vs_yesterday",
                    delta=f"{stats['delta_pct']:+.1f}%",
                )
            else:
                delta_str = t("web.today.kpi.no_yesterday")

            st.metric(
                label=f":material/payments: {t('web.today.kpi.earnings')}",
                value=fmt_money(earnings, lang),
                delta=delta_str,
                delta_color="normal" if stats["delta_pct"] is not None else "off",
            )

    # ── Card 2: Exames Hoje ──
    with k2:
        with st.container(border=True, height="stretch"):
            total = stats["exam_count_today"]
            parts = []
            for slug, count in sorted(stats["modality_counts"].items()):
                label = stats["modality_labels"].get(slug, slug)
                parts.append(f"{label} {count}")
            pills = "  ·  ".join(parts) if parts else "—"

            st.metric(
                label=f":material/content_paste: {t('web.today.kpi.exams')}",
                value=str(total),
                delta=pills,
                delta_color="off",
            )

    # ── Card 3: Horas Estimadas ──
    with k3:
        with st.container(border=True, height="stretch"):
            hours = stats["estimated_hours"]
            st.metric(
                label=f":material/timer: {t('web.today.kpi.hours')}",
                value=f"{hours:.1f}h",
            )

    # ── Card 4: Meta Mensal ──
    with k4:
        with st.container(border=True, height="stretch"):
            month_stats = compute_monthly_stats(conn, year_month, goal, active_mods)
            mtd = month_stats["mtd_earnings"]
            pct = (mtd / goal * 100) if goal > 0 else 0.0
            badge_color: Literal["green", "orange"] = (
                "green" if pct >= 50 else "orange"
            )
            st.metric(
                label=f":material/target: {t('web.today.kpi.goal')}",
                value=f"{pct:.0f}%",
                delta=md_escape(f"{fmt_money(mtd, lang)} / {fmt_money(goal, lang)}"),
                delta_color="off",
            )
            st.badge(
                t("web.today.badge.on_pace" if pct >= 50 else "web.today.badge.watch"),
                icon=":material/target:",
                color=badge_color,
            )


def _build_sparkline_figure(
    conn: Any, year_month: str, active_mods: list[dict[str, Any]], lang: str,
):
    """Load recent 7 days of earnings and build sparkline."""

    current_items = load_month_items(conn, year_month)

    # Compute daily earnings from items
    if current_items.empty:
        return None

    daily = _compute_daily_earnings_from_items(conn, current_items)
    if daily.empty:
        return None

    # If <7 days in current month, pull from previous month
    if len(daily) < 7:
        y, m = int(year_month[:4]), int(year_month[5:7])
        if m == 1:
            prev_ym = f"{y - 1}-12"
        else:
            prev_ym = f"{y}-{m - 1:02d}"
        prev_items = load_month_items(conn, prev_ym)
        if not prev_items.empty:
            prev_daily = _compute_daily_earnings_from_items(conn, prev_items)
            daily = pd.concat([prev_daily, daily], ignore_index=True)

    daily = daily.sort_values("date").tail(7)

    if len(daily) >= 1:
        return build_daily_sparkline(daily, lang)
    return None


