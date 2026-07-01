"""
Month tab — monthly KPI row, progress gauge, daily earnings line, modality donut.

v2: dynamic modalities.
"""

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from streamlit_extras.let_it_rain import rain
from streamlit_extras.star_rating import star_rating
from streamlit_extras.stoggle import stoggle

from src.calculations import (
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
from src.formatting import fmt_brl, md_escape
from src.ui.settings import ensure_settings


def render_month_tab(conn: Any) -> None:
    """Render the complete "Mês Atual" tab."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    goal = st.session_state.goal

    if not active_mods:
        _render_empty_state("Nenhuma modalidade ativa. Configure na aba **Configuração**.")
        return

    stats = compute_monthly_stats(conn, year_month, goal, active_mods)
    daily_target = compute_daily_target(goal, stats["total_calendar_days"])

    if stats["days_worked"] == 0:
        _render_empty_state(
            "Comece registrando sua produção na **barra lateral**."
        )
        return

    # ── KPI Row ──
    _render_kpi_row(stats, goal, daily_target)

    # ── Progress Gauge ──
    pct_goal = stats["pct_goal"]
    gauge = build_progress_gauge(pct_goal)
    st.plotly_chart(gauge, width="stretch")

    # ── Star rating ──
    stars = min(5.0, pct_goal / 20.0)
    star_rating(stars)

    # ── Celebration rain ──
    _maybe_celebrate(pct_goal, year_month)

    # ── Build daily earnings dataframe from items ──
    earn_df = _build_earnings_dataframe(conn, year_month)

    # ── Charts ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(":material/trending_up: Faturamento diário")
        if not earn_df.empty:
            line_chart = build_monthly_earnings_chart(
                earn_df, daily_target, year_month
            )
            st.plotly_chart(line_chart, width="stretch")
        else:
            st.info("Sem dados para o gráfico diário.")

    with col_right:
        st.subheader(":material/pie_chart: Receita por Modalidade")
        items_df = attach_revenue(conn, load_month_items(conn, year_month))
        donut = build_monthly_modality_donut(items_df, active_mods)
        st.plotly_chart(donut, width="stretch")

    # ── Rhythm Alert ──
    _render_rhythm_alert(stats, goal)

    # ── Raw data toggle ──
    if not earn_df.empty:
        raw_text = earn_df.to_string(index=False)
        stoggle("Ver dados brutos", raw_text)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _render_empty_state(message: str) -> None:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(":material/calendar_month:", text_alignment="center")
            st.subheader("Nenhum registro ainda")
            st.markdown(message)
            st.caption("Os dados mensais aparecerão aqui.")


def _build_earnings_dataframe(
    conn: Any, year_month: str,
) -> pd.DataFrame:
    """Build a daily earnings DataFrame (price-vigent revenue) from items."""
    items_df = load_month_items(conn, year_month)
    if items_df.empty:
        return pd.DataFrame()

    items_df = attach_revenue(conn, items_df)
    daily = items_df.groupby("date", as_index=False).agg(earnings=("revenue", "sum"))
    return daily


def _render_kpi_row(
    stats: dict[str, Any], goal: float, daily_target: float,
) -> None:
    """Render the 4 KPI metric cards."""
    k1, k2, k3, k4 = st.columns(4, vertical_alignment="center")

    with k1:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/payments: Faturamento MTD",
                value=fmt_brl(stats["mtd_earnings"]),
                delta=md_escape(
                    f"{fmt_brl(stats['projection_month_end'])} projetado"
                ),
                delta_color="off",
            )

    with k2:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/target: % da meta",
                value=f"{stats['pct_goal']:.0f}%",
                delta=md_escape(
                    f"{fmt_brl(stats['mtd_earnings'])} / {fmt_brl(goal)}"
                ),
                delta_color="off",
            )

    with k3:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/calendar_month: Dias trabalhados",
                value=f"{stats['days_worked']} de {stats['total_calendar_days']}",
                delta=f"{stats['remaining_days']} restantes",
                delta_color="off",
            )

    with k4:
        with st.container(border=True, height="stretch"):
            st.metric(
                label=":material/trending_up: Média diária",
                value=fmt_brl(stats["daily_avg"]),
                delta=f"Alvo: {md_escape(fmt_brl(daily_target))}/dia",
                delta_color="off",
            )


def _render_rhythm_alert(stats: dict[str, Any], goal: float) -> None:
    """Show a warning if behind pace."""
    total = stats["total_calendar_days"]
    if total == 0:
        return

    days_worked = stats["days_worked"]
    if days_worked < 5:
        return

    if stats["mtd_earnings"] >= goal:
        return

    if stats["remaining_days"] == 0:
        return

    pct_goal = stats["pct_goal"]
    expected_pct = (stats["elapsed_days"] / total) * 100.0
    if pct_goal >= expected_pct:
        return

    missing = goal - stats["mtd_earnings"]
    remaining = stats["remaining_days"]
    needed = stats["daily_target_needed"]

    day_text = "1 dia" if remaining == 1 else f"{remaining} dias"

    st.warning(
        ":material/warning: **Atenção ao ritmo**\n\n"
        f"{st.session_state.get('user_name', '')}, "
        f"você está atrás do ritmo para bater a meta "
        f"de {md_escape(fmt_brl(goal))}.\n\n"
        f"Faltam {md_escape(fmt_brl(missing))} em {day_text} — "
        f"você precisa de **{md_escape(fmt_brl(needed))}/dia** "
        f"daqui pra frente.\n\n"
        f"Sua média atual: {md_escape(fmt_brl(stats['daily_avg']))}/dia."
    )


def _maybe_celebrate(pct_goal: float, year_month: str) -> None:
    """Trigger rain when goal is achieved."""
    if pct_goal < 100.0:
        return
    celebrate_key = f"goal_celebrated_{year_month}"
    if st.session_state.get(celebrate_key):
        return
    rain(emoji="🎉", font_size=36, falling_speed=5, animation_length=3)
    st.toast(":material/check_circle: Meta do mês atingida! Parabéns!")
    st.session_state[celebrate_key] = True
