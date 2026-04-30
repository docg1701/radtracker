"""
Analysis tab — insight card, moving averages, WoW comparison, modality mix.

Renders the "Análise & Insights" tab per Sprint 4 plan.
"""

import os
import re
from datetime import date
from typing import Any

import streamlit as st

from src.calculations import compute_historical_stats
from src.chart_colors import CHART_COLORS
from src.charts_analysis import (
    build_modality_mix_evolution,
    build_moving_averages_chart,
    build_wow_comparison_chart,
)
from src.insights_rules import generate_rule_insights
from src.llm_client import LLMClient, LLMUnavailableError
from src.ui.settings import ensure_settings


def render_analysis_tab(conn: Any) -> None:
    """
    Render the complete "Análise & Insights" tab.

    Loads all historical data, computes stats, generates rules-based
    insights, and renders 3 charts.
    """
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    prices = st.session_state.prices
    goal = st.session_state.goal

    import json

    cache_key = f"{year_month}:{goal}:{json.dumps(prices, sort_keys=True)}"
    cached = st.session_state.get("historical_cache")

    if cached is None or cached.get("key") != cache_key:
        with st.spinner("Analisando dados históricos..."):
            stats = compute_historical_stats(conn, year_month, goal, prices)
        st.session_state.historical_cache = {"key": cache_key, "stats": stats}
    else:
        stats = cached["stats"]

    df = stats.get("df")
    if df is None or len(df) == 0:
        st.info(
            "Registre pelo menos **1 dia** de produção para ver "
            "análises históricas. Comece pela aba **📊 Hoje**."
        )
        return

    # ── Insight card (LLM with rule fallback) ──
    api_key = os.environ.get("OPENROUTER_API_KEY")

    try:
        with st.spinner("🧠 Gerando insights com IA..."):
            llm = LLMClient(api_key)
            insight_text = llm.generate(stats)
        _render_insight_card(insight_text, source="llm")
    except LLMUnavailableError:
        insight_text = generate_rule_insights(stats)
        st.info("🤖 IA indisponível — exibindo análise baseada em regras.")
        _render_insight_card(insight_text, source="rules")

    # ── Two-column: Moving Averages + WoW Comparison ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📈 Médias Móveis")
        current_month_df = df[df["date"].str[:7] == year_month]
        if current_month_df.empty:
            st.info("Nenhum dado no mês atual para médias móveis.")
        else:
            ma_chart = build_moving_averages_chart(current_month_df, year_month)
            st.plotly_chart(ma_chart, width="stretch")

    with col_right:
        st.subheader("📊 Comparação Semanal")
        weekly = stats.get("weekly_totals_last_4", [])
        if len(weekly) >= 2:
            wow_chart = build_wow_comparison_chart(weekly[-2:], prices)
        elif len(weekly) == 1:
            wow_chart = build_wow_comparison_chart(weekly, prices)
        else:
            st.info("Dados insuficientes para comparação semanal.")
            wow_chart = None
        if wow_chart is not None:
            st.plotly_chart(wow_chart, width="stretch")

    # ── Full-width: Modality Mix Evolution ──
    st.subheader("Evolução do Mix de Modalidades")
    mix_history = stats.get("modality_mix_historical", {})
    if mix_history:
        mix_chart = build_modality_mix_evolution(mix_history)
        st.plotly_chart(mix_chart, width="stretch")
    else:
        st.info("Dados insuficientes para evolução do mix.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _render_insight_card(text: str, source: str = "rules") -> None:
    """Render a bordered container with teal left accent and insight text.

    Args:
        text: Insight markdown (Portuguese).
        source: "llm" → GPT-OSS caption, "rules" → automatic analysis caption.
    """
    teal = CHART_COLORS["primary"]
    if source == "llm":
        caption = (
            "🤖 Gerado por GPT-OSS 120B (OpenRouter) · "
            "Análise automática baseada nos seus dados"
        )
    else:
        caption = "📊 Análise automática baseada nos seus dados"

    # Convert insight markdown to basic HTML (only **bold** and line breaks)
    html_body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    html_body = html_body.replace("\n", "<br>")
    with st.container(border=True):
        st.markdown(
            f"""<div style="border-left:4px solid {teal};padding-left:16px;">
            <h3 style="margin-top:0;">💡 Insights</h3>
            {html_body}
            <p style="color:{CHART_COLORS['muted']};font-size:0.8rem;margin-top:12px;">
            {caption}</p>
            </div>""",
            unsafe_allow_html=True,
        )



