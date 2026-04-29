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
from src.db import load_month, load_prices, load_goal


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

    prices = load_prices(conn)
    goal = load_goal(conn, year_month)

    stats = compute_monthly_stats(conn, year_month, goal, prices)
    daily_target = compute_daily_target(goal, stats["total_work_days"])

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
    st.plotly_chart(gauge, use_container_width=True)

    # ── Charts Row (2-column) ──
    month_df = load_month(conn, year_month)
    earnings_df = add_earnings_column(month_df, prices)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📈 Faturamento Diário")
        line_chart = build_monthly_earnings_chart(
            earnings_df, daily_target, year_month
        )
        st.plotly_chart(line_chart, use_container_width=True)

    with col_right:
        st.subheader("🍩 Receita por Modalidade")
        donut = build_monthly_modality_donut(month_df, prices)
        st.plotly_chart(donut, use_container_width=True)

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
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.metric(
            label="💰 Faturamento MTD",
            value=_fmt_brl(stats["mtd_earnings"]),
            delta=f"{_fmt_brl(stats['projection_month_end'])} projetado",
            delta_color="off",
        )

    with k2:
        st.metric(
            label="🎯 % da Meta",
            value=f"{stats['pct_goal']:.0f}%",
            delta=f"{_fmt_brl(stats['mtd_earnings'])} / {_fmt_brl(goal)}",
            delta_color="off",
        )

    with k3:
        st.metric(
            label="📅 Dias Trabalhados",
            value=f"{stats['days_worked']} de {stats['total_work_days']}",
            delta=f"{stats['remaining_work_days']} restantes",
            delta_color="off",
        )

    with k4:
        daily_avg_str = _fmt_brl(stats["daily_avg"])
        target_str = _fmt_brl(daily_target)
        st.metric(
            label="📊 Média Diária",
            value=daily_avg_str,
            delta=f"Alvo: {target_str}/dia",
            delta_color="off",
        )


def _render_rhythm_alert(stats: dict[str, Any], goal: float) -> None:
    """Show a warning if behind pace to meet the monthly goal."""
    total = stats["total_work_days"]
    if total == 0:
        return

    days_worked = stats["days_worked"]
    pct_goal = stats["pct_goal"]

    expected_pct = (days_worked / total) * 100.0
    if pct_goal >= expected_pct:
        return

    missing = goal - stats["mtd_earnings"]
    remaining = stats["remaining_work_days"]
    needed = stats["daily_target_needed"]

    st.warning(
        f"⚠️ **Atenção ao ritmo**\n\n"
        f"Galvani, você está atrás do ritmo para bater a meta "
        f"de {_fmt_brl(goal)}.\n\n"
        f"Faltam {_fmt_brl(missing)} em {remaining} dias úteis — "
        f"você precisa de **{_fmt_brl(needed)}/dia** daqui pra frente.\n\n"
        f"Sua média atual: {_fmt_brl(stats['daily_avg'])}/dia."
    )


# TODO: extract to src/formatting.py in Sprint 6
def _fmt_brl(value: float) -> str:
    """
    Format a float as Brazilian Real currency.

    Example:
        >>> _fmt_brl(1250.0)
        'R$ 1.250,00'
        >>> _fmt_brl(0.0)
        'R$ 0,00'
    """
    if value < 0:
        return f"\u2212{_fmt_brl(-value)}"
    # int(value*100 + 0.5) gives correct half-up rounding.
    # Built-in round() uses banker's rounding (round(0.5)==0), which
    # would under-round half-centavos when non-standard prices are in use.
    cents = int(value * 100 + 0.5)
    integer_part = cents // 100
    decimal_part = cents % 100
    int_str = f"{integer_part:,}".replace(",", ".")
    return f"R$ {int_str},{decimal_part:02d}"
