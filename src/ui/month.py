"""
Month tab — monthly KPI row, progress gauge, daily earnings line, modality donut.

Renders the "Mês Atual" tab per DESIGN_SPEC §4.2.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.calculations import (
    add_earnings_column,
    compute_daily_target,
    compute_monthly_stats,
)
from src.charts import (
    build_monthly_earnings_chart,
    build_monthly_modality_donut,
    build_progress_gauge,
)
from src.db import load_month
from src.formatting import fmt_brl, md_escape
from src.ui.settings import ensure_settings


def render_month_tab(conn: Any) -> None:
    """
    Render the complete "Mês Atual" tab for the current month.

    Loads data, computes monthly statistics, and renders:
    - KPI row (4 metric cards)
    - Progress gauge
    - Daily earnings line chart + modality revenue donut
    - Rhythm alert (warning when behind pace)
    """
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    prices = st.session_state.prices
    goal = st.session_state.goal

    stats = compute_monthly_stats(conn, year_month, goal, prices)
    daily_target = compute_daily_target(goal, stats["total_calendar_days"])

    # Empty state: no data recorded this month
    if stats["days_worked"] == 0:
        st.info(
            "Nenhum dado registrado neste mês. "
            "Comece registrando sua produção na aba **📊 Hoje**."
        )
        return

    # ── KPI Row ──
    _render_kpi_row(stats, goal, daily_target)

    # ── Progress Gauge ──
    gauge = build_progress_gauge(stats["pct_goal"])
    st.plotly_chart(gauge, width="stretch")

    # ── Charts Row (2-column) ──
    month_df = load_month(conn, year_month)
    earnings_df = add_earnings_column(month_df, prices)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📈 Faturamento Diário")
        line_chart = build_monthly_earnings_chart(
            earnings_df, daily_target, year_month
        )
        st.plotly_chart(line_chart, width="stretch")

    with col_right:
        st.subheader("Receita por Modalidade")
        donut = build_monthly_modality_donut(month_df, prices)
        st.plotly_chart(donut, width="stretch")

    # ── Rhythm Alert ──
    _render_rhythm_alert(stats, goal)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _render_kpi_row(
    stats: dict[str, Any],
    goal: float,
    daily_target: float,
) -> None:
    """Render the 4 KPI metric cards for the month tab."""
    k1, k2, k3, k4 = st.columns(4, vertical_alignment="center")

    with k1:
        st.metric(
            label="💰 Faturamento MTD",
            value=fmt_brl(stats["mtd_earnings"]),
            delta=md_escape(f"{fmt_brl(stats['projection_month_end'])} projetado"),
            delta_color="off",
        )

    with k2:
        st.metric(
            label="🎯 % da Meta",
            value=f"{stats['pct_goal']:.0f}%",
            delta=md_escape(f"{fmt_brl(stats['mtd_earnings'])} / {fmt_brl(goal)}"),
            delta_color="off",
        )

    with k3:
        st.metric(
            label="📅 Dias trabalhados",
            value=f"{stats['days_worked']} de {stats['total_calendar_days']}",
            delta=f"{stats['remaining_calendar_days']} restantes",
            delta_color="off",
        )

    with k4:
        daily_avg_str = fmt_brl(stats["daily_avg"])
        target_str = md_escape(fmt_brl(daily_target))
        st.metric(
            label="📊 Média Diária",
            value=daily_avg_str,
            delta=f"Alvo: {target_str}/dia",
            delta_color="off",
        )


def _render_rhythm_alert(stats: dict[str, Any], goal: float) -> None:
    """Show a warning if behind pace to meet the monthly goal."""
    total = stats["total_calendar_days"]
    if total == 0:
        return

    if stats["mtd_earnings"] >= goal:
        return

    if stats["remaining_calendar_days"] == 0:
        return

    days_worked = stats["days_worked"]
    pct_goal = stats["pct_goal"]

    expected_pct = (days_worked / total) * 100.0
    if pct_goal >= expected_pct:
        return

    missing = goal - stats["mtd_earnings"]
    remaining = stats["remaining_calendar_days"]
    needed = stats["daily_target_needed"]

    st.warning(
        "⚠️ **Atenção ao ritmo**\n\n"
        f"Galvani, você está atrás do ritmo para bater a meta "
        f"de {md_escape(fmt_brl(goal))}.\n\n"
        f"Faltam {md_escape(fmt_brl(missing))} em {remaining} dias — "
        f"você precisa de **{md_escape(fmt_brl(needed))}/dia** daqui pra frente.\n\n"
        f"Sua média atual: {md_escape(fmt_brl(stats['daily_avg']))}/dia."
    )



