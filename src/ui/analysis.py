"""
Analysis tab — insight card, moving averages, WoW comparison, modality mix.

Renders the "Análise & Insights" tab per Sprint 7 plan:
  - Rules-based insights in expander (default expanded, no auto-LLM)
  - "Ask AI" button with in-flight guard and session_state persistence
  - AI result in a separate expander
"""

from datetime import date
from typing import Any

import streamlit as st
from streamlit_extras.skeleton import skeleton

from src.calculations import compute_historical_stats
from src.charts_analysis import (
    build_modality_mix_evolution,
    build_moving_averages_chart,
    build_wow_comparison_chart,
    build_ytd_earnings_chart,
)
from src.formatting import md_escape
from src.insights_rules import generate_rule_insights
from src.llm_client import LLMClient, LLMUnavailableError
from src.ui.settings import ensure_settings


def render_analysis_tab(conn: Any) -> None:
    """
    Render the complete "Análise & Insights" tab.

    Loads all historical data, computes stats, and renders:
    - Rules-based insights (collapsible, expanded by default)
    - "Ask AI" button + AI result (collapsible, separate)
    - 4 charts (MA, WoW, mix evolution, YTD earnings)
    """
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    prices = st.session_state.prices
    goal = st.session_state.goal

    import json

    cache_key = f"{year_month}:{goal}:{json.dumps(prices, sort_keys=True)}"
    cached = st.session_state.get("historical_cache")

    # Invalidate LLM cache when historical data changes
    if cached is None or cached.get("key") != cache_key:
        st.session_state.pop("llm_insight_text", None)

        # Skeleton placeholders before expensive computation
        sk1, sk2 = st.columns(2)
        with sk1:
            skeleton(height=280)
        with sk2:
            skeleton(height=280)
        skeleton(height=280)

        with st.spinner("Analisando dados históricos..."):
            stats = compute_historical_stats(conn, year_month, goal, prices)
        st.session_state.historical_cache = {"key": cache_key, "stats": stats}
        st.rerun()
    else:
        stats = cached["stats"]

    df = stats.get("df")
    if df is None or len(df) == 0:
        _render_empty_state()
        return

    # ── Bloco 1: Insights por regras (expandido por padrão) ──
    with st.expander(":material/lightbulb: Insights", expanded=True):
        rule_text = generate_rule_insights(stats)
        _render_insight_body(rule_text, source="rules")

    # ── Bloco 2: IA (botão explícito, resultado colapsável) ──
    _render_ai_section(stats)

    # ── Two-column: Moving Averages + WoW Comparison ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(":material/trending_up: Médias móveis")
        current_month_df = df[df["date"].str[:7] == year_month]
        if current_month_df.empty:
            st.info("Nenhum dado no mês atual para médias móveis.")
        else:
            ma_chart = build_moving_averages_chart(current_month_df, year_month)
            st.plotly_chart(ma_chart, width="stretch")

    with col_right:
        st.subheader(":material/analytics: Comparação semanal")
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
    st.subheader(":material/pie_chart: Evolução do mix de modalidades")
    mix_history = stats.get("modality_mix_historical", {})
    if mix_history:
        mix_chart = build_modality_mix_evolution(mix_history)
        st.plotly_chart(mix_chart, width="stretch")
    else:
        st.info("Dados insuficientes para evolução do mix.")

    # ── Full-width: Year-to-Date Earnings ──
    st.subheader(":material/bar_chart: Faturamento por mês")
    ytd_chart = build_ytd_earnings_chart(df, year_month, goal)
    st.plotly_chart(ytd_chart, width="stretch")


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

def _render_empty_state() -> None:
    """Render empty-state card when no historical data exists."""
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(":material/bar_chart:", text_alignment="center")
            st.subheader("Nenhum registro ainda")
            st.markdown(
                "Registre sua produção na "
                "**barra lateral**."
            )
            st.caption("As análises históricas aparecerão aqui.")


# ---------------------------------------------------------------------------
# IA section (fragment-protected)
# ---------------------------------------------------------------------------

@st.fragment
def _render_ai_section(stats: dict[str, Any]) -> None:
    """Render the AI button + optional result expander.

    Fragment: clicks in this section only rerun this function,
    not the entire page. Session state persists the result across tabs.
    """
    api_key = st.session_state.get("api_key", "")

    # ── No API key configured ──
    if not api_key:
        st.caption(
            "Configure sua chave API na aba "
            ":material/settings: **Config** para ativar a análise com IA."
        )
        st.caption("[Obter chave gratuita no OpenRouter](https://openrouter.ai/keys)")
        st.button(
            ":material/psychology: Perguntar à IA",
            type="secondary", disabled=True,
        )
        return

    # ── Button ──
    st.caption(
        "Exemplos: 'Qual dia foi mais produtivo?', "
        "'Minha média é consistente?'"
    )
    st.button(
        ":material/psychology: Perguntar à IA",
        type="secondary",
        on_click=lambda: st.session_state.update(llm_insight_pending=True),
    )

    # ── Guard: show in-flight status ──
    if st.session_state.get("llm_insight_in_flight"):
        with st.status("Gerando análise com IA...", expanded=True):
            st.write("Conectando ao OpenRouter...")
            st.write("Aguardando resposta do modelo...")
        if st.button("Cancelar", type="secondary"):
            st.session_state.llm_insight_cancelled = True
            st.rerun()
        if st.session_state.get("llm_insight_cancelled"):
            st.session_state.pop("llm_insight_cancelled", None)
            st.session_state.pop("llm_insight_in_flight", None)
            st.session_state.pop("llm_insight_pending", None)
            st.info("Análise cancelada.")
            return
        return

    if not st.session_state.get("llm_insight_pending"):
        # Show cached result if available
        llm_text = st.session_state.get("llm_insight_text")
        if llm_text:
            with st.expander(":material/smart_toy: Análise da IA", expanded=True):
                _render_insight_body(llm_text, source="llm")
        return

    # ── Execute LLM call ──
    st.session_state.llm_insight_in_flight = True
    try:
        with st.spinner(":material/psychology: Gerando análise com IA..."):
            system_prompt = st.session_state.get("llm_prompt")
            llm = LLMClient(api_key, prompt=system_prompt)
            llm_text = llm.generate(stats, st.session_state.prices)
        if not llm_text:
            llm_text = "(A IA retornou uma resposta vazia.)"
        st.session_state.llm_insight_text = llm_text
        st.session_state.pop("llm_insight_pending", None)
        st.toast(":material/check_circle: Análise concluída!")
        with st.expander(":material/smart_toy: Análise da IA", expanded=True):
            _render_insight_body(llm_text, source="llm")
    except (LLMUnavailableError, Exception):
        st.error("Não foi possível gerar a análise. Verifique sua conexão ou chave de API.")
        st.session_state.pop("llm_insight_pending", None)
    finally:
        st.session_state.llm_insight_in_flight = False


# ---------------------------------------------------------------------------
# Insight body renderer
# ---------------------------------------------------------------------------

def _render_insight_body(text: str, source: str = "rules") -> None:
    """Render insight markdown with a source caption.

    Args:
        text: Markdown text (Portuguese). Streamlit renders **bold** natively.
        source: "llm" → GPT-OSS caption, "rules" → rules-based caption.
    """
    if source == "llm":
        caption = (
            ":material/smart_toy: Gerado por GPT-OSS 120B (OpenRouter) · "
            "Análise automática baseada nos seus dados"
        )
    else:
        caption = ":material/bar_chart: Análise automática baseada nos seus dados"

    st.markdown(md_escape(text))
    st.caption(caption)
