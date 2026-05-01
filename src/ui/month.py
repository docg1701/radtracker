"""
Month tab — monthly KPI row, progress gauge, daily earnings line, modality donut.

Renders the "Mês Atual" tab per DESIGN_SPEC §4.2.
"""

from datetime import date
from typing import Any

import streamlit as st
from streamlit_extras.let_it_rain import rain
from streamlit_extras.star_rating import star_rating
from streamlit_extras.stoggle import stoggle

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
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            with st.container(border=True):
                st.markdown(":material/calendar_month:", text_alignment="center")
                st.subheader("Nenhum registro ainda")
                st.markdown(
                    "Comece registrando sua produção "
                    "na **barra lateral**."
                )
                st.caption("Os dados mensais aparecerão aqui.")
        return

    # ── KPI Row ──
    _render_kpi_row(stats, goal, daily_target)

    # ── Progress Gauge ──
    pct_goal = stats["pct_goal"]
    gauge = build_progress_gauge(pct_goal)
    st.plotly_chart(gauge, width="stretch")

    # ── Star rating (visual performance indicator) ──
    stars = min(5.0, pct_goal / 20.0)
    star_rating(stars)

    # ── Celebration rain (once per goal achievement) ──
    _maybe_celebrate(pct_goal, year_month)

    # ── Charts Row (2-column) ──
    month_df = load_month(conn, year_month)
    earnings_df = add_earnings_column(month_df, prices)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(":material/trending_up: Faturamento diário")
        line_chart = build_monthly_earnings_chart(
            earnings_df, daily_target, year_month
        )
        st.plotly_chart(line_chart, width="stretch")

    with col_right:
        st.subheader(":material/pie_chart: Receita por Modalidade")
        donut = build_monthly_modality_donut(month_df, prices)
        st.plotly_chart(donut, width="stretch")

    # ── Rhythm Alert ──
    _render_rhythm_alert(stats, goal)

    # ── Raw data toggle ──
    raw_text = month_df.to_string(index=False)
    stoggle("Ver dados brutos", raw_text)


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
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/payments: Faturamento MTD",
                value=fmt_brl(stats["mtd_earnings"]),
                delta=md_escape(f"{fmt_brl(stats['projection_month_end'])} projetado"),
                delta_color="off",
            )

    with k2:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/target: % da meta",
                value=f"{stats['pct_goal']:.0f}%",
                delta=md_escape(f"{fmt_brl(stats['mtd_earnings'])} / {fmt_brl(goal)}"),
                delta_color="off",
            )

    with k3:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/calendar_month: Dias trabalhados",
                value=f"{stats['days_worked']} de {stats['total_calendar_days']}",
                delta=f"{stats['remaining_calendar_days']} restantes",
                delta_color="off",
            )

    with k4:
        with st.container(border=True, height="stretch"):
            daily_avg_str = fmt_brl(stats["daily_avg"])
            target_str = md_escape(fmt_brl(daily_target))
            st.metric(
                label=":material/trending_up: Média diária",
                value=daily_avg_str,
                delta=f"Alvo: {target_str}/dia",
                delta_color="off",
            )


def _render_rhythm_alert(stats: dict[str, Any], goal: float) -> None:
    """Show a warning if behind pace to meet the monthly goal.

    Only fires when there are at least 5 days of data — earlier than
    that, the pace calculation is too volatile to be meaningful.
    """
    total = stats["total_calendar_days"]
    if total == 0:
        return

    days_worked = stats["days_worked"]
    if days_worked < 5:
        return

    if stats["mtd_earnings"] >= goal:
        return

    if stats["remaining_calendar_days"] == 0:
        return

    pct_goal = stats["pct_goal"]

    expected_pct = (days_worked / total) * 100.0
    if pct_goal >= expected_pct:
        return

    missing = goal - stats["mtd_earnings"]
    remaining = stats["remaining_calendar_days"]
    needed = stats["daily_target_needed"]

    if remaining == 1:
        day_text = "1 dia"
    else:
        day_text = f"{remaining} dias"

    st.warning(
        ":material/warning: **Atenção ao ritmo**\n\n"
        f"{st.session_state.get('user_name', 'Galvani')}, "
        f"você está atrás do ritmo para bater a meta "
        f"de {md_escape(fmt_brl(goal))}.\n\n"
        f"Faltam {md_escape(fmt_brl(missing))} em {day_text} — "
        f"você precisa de **{md_escape(fmt_brl(needed))}/dia** daqui pra frente.\n\n"
        f"Sua média atual: {md_escape(fmt_brl(stats['daily_avg']))}/dia."
    )


def _maybe_celebrate(pct_goal: float, year_month: str) -> None:
    """Trigger rain animation once when monthly goal is achieved.

    Uses st.session_state.goal_celebrated to prevent re-triggering
    on reruns. The key includes year_month so a new month resets it.
    """
    if pct_goal < 100.0:
        return
    celebrate_key = f"goal_celebrated_{year_month}"
    if st.session_state.get(celebrate_key):
        return
    rain(emoji="🎉", font_size=36, falling_speed=5, animation_length=3)
    st.toast(":material/check_circle: Meta do mês atingida! Parabéns!")
    st.session_state[celebrate_key] = True



