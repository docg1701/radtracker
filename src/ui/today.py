"""
Today tab — KPI cards, modality donut, and sparkline.

Renders the "Hoje" tab per DESIGN_SPEC §4.1, §4.1a, §4.5, §4.6.
"""

from datetime import date
from typing import Any, Literal

import pandas as pd
import streamlit as st
from streamlit_extras.stoggle import stoggle

from src.calculations import (
    add_earnings_column,
    compute_daily_stats,
    compute_mtd_earnings,
)
from src.charts import build_daily_sparkline, build_modality_donut
from src.db import load_month
from src.formatting import fmt_brl, md_escape
from src.ui.settings import ensure_settings


def render_today_tab(conn: Any) -> None:
    """
    Render the complete "Hoje" tab: KPI row, donut chart, sparkline.

    Displays an empty-state card when no data exists for today.
    """
    today = date.today()
    today_str = today.isoformat()
    year_month = today_str[:7]  # "2026-04"

    # Load settings from session state (cached from DB on boot)
    ensure_settings(conn)
    prices = st.session_state.prices
    monthly_goal = st.session_state.goal

    # Compute daily stats
    stats = compute_daily_stats(conn, today_str, prices)

    # Empty state: no data exists for today
    if not stats["has_data"]:
        _render_empty_state()
        return

    # ── KPI Row ──
    _render_kpi_row(stats, prices, monthly_goal, conn, year_month)

    # ── Donut + Sparkline side-by-side ──
    spark = _build_sparkline_figure(conn, prices, year_month)

    st.subheader(":material/dashboard: Visão geral")

    col_left, col_right = st.columns(2)
    with col_left:
        donut = build_modality_donut(
            stats["rm_count"], stats["tc_count"], stats["rx_count"]
        )
        st.plotly_chart(donut, width="stretch")
    with col_right:
        if spark is not None:
            st.plotly_chart(spark, width="stretch")

    # ── Raw data toggle ──
    today_data = {
        "Data": today_str,
        "RM": stats["rm_count"],
        "TC": stats["tc_count"],
        "RX": stats["rx_count"],
        "Faturamento": fmt_brl(stats["earnings_today"]),
        "Horas": f"{stats['estimated_hours']:.1f}h",
    }
    raw_text = "\n".join(f"{k}: {v}" for k, v in today_data.items())
    stoggle("Ver dados brutos", raw_text)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _render_empty_state() -> None:
    """Render the friendly empty-state card."""
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(":material/content_paste:", text_alignment="center")
            st.subheader("Nenhum registro ainda")
            st.markdown(
                "Comece registrando sua produção de hoje "
                "na **barra lateral**."
            )
            st.caption("Os dados aparecerão aqui assim que você salvar.")


def _render_kpi_row(
    stats: dict[str, Any],
    prices: dict[str, float],
    monthly_goal: float,
    conn: Any,
    year_month: str,
) -> None:
    """Render the 4 KPI metric cards in st.columns(4)."""
    k1, k2, k3, k4 = st.columns(4, vertical_alignment="center")

    # ── Card 1: Faturamento Hoje ──
    with k1:
        with st.container(border=True, height="stretch"):
            earnings = stats["earnings_today"]
            if stats["delta_pct"] is not None:
                delta_str = f"{stats['delta_pct']:+.1f}% vs ontem"
                delta_color: Literal["normal", "off"] = "normal"
            else:
                delta_str = "— sem dados de ontem"
                delta_color = "off"

            st.metric(
                label=":material/payments: Faturamento hoje",
                value=fmt_brl(earnings),
                delta=delta_str,
                delta_color=delta_color,
            )

    # ── Card 2: Exames Hoje ──
    with k2:
        with st.container(border=True, height="stretch"):
            total = stats["exam_count_today"]
            pills = _build_pill_indicators(
                stats["rm_count"], stats["tc_count"], stats["rx_count"]
            )
            st.metric(
                label=":material/content_paste: Exames hoje",
                value=str(total),
                delta=pills,
                delta_color="off",
            )

    # ── Card 3: Horas Estimadas ──
    with k3:
        with st.container(border=True, height="stretch"):
            hours = stats["estimated_hours"]
            time_range = stats["estimated_time_range"]
            st.metric(
                label=":material/timer: Horas estimadas",
                value=f"{hours:.1f}h",
                delta=time_range,
                delta_color="off",
            )

    # ── Card 4: Meta Mensal ──
    with k4:
        with st.container(border=True, height="stretch"):
            month_df = load_month(conn, year_month)
            mtd = compute_mtd_earnings(month_df, prices)
            pct = (mtd / monthly_goal * 100) if monthly_goal > 0 else 0.0
            badge_color: Literal["green", "orange"] = "green" if pct >= 50 else "orange"
            st.metric(
                label=":material/target: Meta mensal",
                value=f"{pct:.0f}%",
                delta=md_escape(f"{fmt_brl(mtd)} / {fmt_brl(monthly_goal)}"),
                delta_color="off",
            )
            st.badge(
                "No ritmo" if pct >= 50 else "Atenção",
                icon=":material/target:",
                color=badge_color,
            )


def _build_sparkline_figure(
    conn: Any, prices: dict[str, float], year_month: str
):
    """Load recent 7 days and build the sparkline chart figure.

    Returns plotly Figure or None if insufficient data.
    """
    current_df = load_month(conn, year_month)

    # If early in the month (<7 days), pull from previous month too
    if len(current_df) < 7:
        y, m = int(year_month[:4]), int(year_month[5:7])
        if m == 1:
            prev_ym = f"{y - 1}-12"
        else:
            prev_ym = f"{y}-{m - 1:02d}"
        prev_df = load_month(conn, prev_ym)
        all_days = pd.concat([prev_df, current_df], ignore_index=True)
    else:
        all_days = current_df

    if all_days.empty:
        return None

    # Compute earnings per day, keep last 7
    all_days = add_earnings_column(all_days, prices)
    all_days = all_days.sort_values("date").tail(7)

    if len(all_days) >= 1:
        return build_daily_sparkline(all_days)
    return None


def _build_pill_indicators(rm: int, tc: int, rx: int) -> str:
    """Build modality indicators as plain text (st.metric delta = markdown, not HTML)."""
    return f"RM {rm}  ·  TC {tc}  ·  RX {rx}"



