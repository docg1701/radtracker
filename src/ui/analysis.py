"""
Analysis tab — insight card, moving averages, WoW comparison, modality mix.

v2: dynamic modalities, configurable LLM model.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.charts_analysis import (
    build_modality_mix_evolution,
    build_moving_averages_chart,
    build_wow_comparison_chart,
    build_ytd_earnings_chart,
)
from src.formatting import md_escape
from src.insights_rules import generate_rule_insights
from src.ui.common import get_historical_stats, render_empty_state
from src.ui.settings import ensure_settings


def render_analysis_tab(conn: Any) -> None:
    """Render the complete "Análise & Insights" tab."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    goal = st.session_state.goal

    if not active_mods:
        render_empty_state(
            ":material/bar_chart:",
            "Nenhuma modalidade ativa. Configure na aba **Configuração**.",
        )
        return

    stats = get_historical_stats(conn, year_month, goal, active_mods)

    df = stats.get("df")
    if df is None or len(df) == 0:
        render_empty_state(
            ":material/bar_chart:",
            "Registre sua produção na **barra lateral**.",
            caption="As análises históricas aparecerão aqui.",
        )
        return

    # ── Insights por regras ──
    with st.expander(":material/lightbulb: Insights", expanded=True):
        rule_text = generate_rule_insights(stats)
        _render_insight_body(rule_text)

    # ── Two-column: MA + WoW ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(":material/trending_up: Médias móveis")
        current_month_df = df[df["date"].str[:7] == year_month]
        if current_month_df.empty:
            st.info("Nenhum dado no mês atual.")
        else:
            ma_chart = build_moving_averages_chart(current_month_df, year_month)
            st.plotly_chart(ma_chart, width="stretch")

    with col_right:
        st.subheader(":material/analytics: Comparação semanal")
        wow_items = stats["items_df"]
        wow_chart = build_wow_comparison_chart(wow_items, active_mods)
        st.plotly_chart(wow_chart, width="stretch")

    # ── Modality Mix Evolution ──
    st.subheader(":material/pie_chart: Evolução do mix de modalidades")
    mix_history = stats.get("modality_mix_historical", {})
    if mix_history:
        mix_chart = build_modality_mix_evolution(mix_history, active_mods)
        st.plotly_chart(mix_chart, width="stretch")
    else:
        st.info("Dados insuficientes para evolução do mix.")

    # ── YTD Earnings ──
    st.subheader(":material/bar_chart: Faturamento por mês")
    ytd_chart = build_ytd_earnings_chart(df, year_month, goal)
    st.plotly_chart(ytd_chart, width="stretch")


# ---------------------------------------------------------------------------
# Insight body
# ---------------------------------------------------------------------------

def _render_insight_body(text: str) -> None:
    """Render insight markdown with a source caption."""
    caption = ":material/bar_chart: Análise automática baseada nos seus dados"
    st.markdown(md_escape(text))
    st.caption(caption)
