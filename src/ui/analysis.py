"""
Analysis tab — insight card, moving averages, WoW comparison, modality mix.

v2: dynamic modalities, configurable LLM model.
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
    """Render the complete "Análise & Insights" tab."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    goal = st.session_state.goal

    if not active_mods:
        _render_empty_state("Nenhuma modalidade ativa. Configure na aba **Configuração**.")
        return

    import json

    cache_key_parts = {
        "ym": year_month,
        "goal": goal,
        "mods": [(m["slug"], m["price"], m["exams_per_hour"]) for m in active_mods],
    }
    cache_key = json.dumps(cache_key_parts, sort_keys=True)
    cached = st.session_state.get("historical_cache")

    if cached is None or cached.get("key") != cache_key:
        st.session_state.pop("llm_insight_text", None)

        sk1, sk2 = st.columns(2)
        with sk1:
            skeleton(height=280)
        with sk2:
            skeleton(height=280)
        skeleton(height=280)

        with st.spinner("Analisando dados históricos..."):
            stats = compute_historical_stats(conn, year_month, goal, active_mods)
        st.session_state.historical_cache = {"key": cache_key, "stats": stats}
        st.rerun()
    else:
        stats = cached["stats"]

    df = stats.get("df")
    if df is None or len(df) == 0:
        _render_empty_state(
            "Registre sua produção na **barra lateral**."
        )
        return

    # ── Insights por regras ──
    with st.expander(":material/lightbulb: Insights", expanded=True):
        rule_text = generate_rule_insights(stats, active_mods)
        _render_insight_body(rule_text, source="rules")

    # ── IA ──
    _render_ai_section(stats, active_mods)

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
        weekly = stats.get("weekly_totals_last_4", [])
        if len(weekly) >= 1:
            wow_chart = build_wow_comparison_chart(weekly, df, active_mods)
            st.plotly_chart(wow_chart, width="stretch")
        else:
            st.info("Dados insuficientes para comparação semanal.")

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
# Empty state
# ---------------------------------------------------------------------------

def _render_empty_state(message: str) -> None:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(":material/bar_chart:", text_alignment="center")
            st.subheader("Nenhum registro ainda")
            st.markdown(message)
            st.caption("As análises históricas aparecerão aqui.")


# ---------------------------------------------------------------------------
# IA section
# ---------------------------------------------------------------------------

@st.fragment
def _render_ai_section(
    stats: dict[str, Any], active_mods: list[dict[str, Any]],
) -> None:
    """Render the AI button + optional result expander."""
    api_key = st.session_state.get("api_key", "")
    llm_model = (
        st.session_state.get("llm_model", "openai/gpt-oss-120b:free")
        or "openai/gpt-oss-120b:free"
    )

    if not api_key:
        st.caption(
            "Configure sua chave API na aba "
            ":material/settings: **Config** para ativar a análise com IA."
        )
        st.button(
            ":material/psychology: Perguntar à IA",
            type="secondary", disabled=True,
        )
        return

    # Show current model
    st.caption(f"Modelo: `{llm_model}`")

    st.caption(
        "Exemplos: 'Qual dia foi mais produtivo?', "
        "'Minha média é consistente?'"
    )
    st.button(
        ":material/psychology: Perguntar à IA",
        type="secondary",
        on_click=lambda: st.session_state.update(llm_insight_pending=True),
    )

    # In-flight guard
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
        llm_text = st.session_state.get("llm_insight_text")
        if llm_text:
            with st.expander(
                ":material/smart_toy: Análise da IA", expanded=True
            ):
                _render_insight_body(llm_text, source="llm")
        return

    # Execute LLM call
    st.session_state.llm_insight_in_flight = True
    try:
        with st.spinner(":material/psychology: Gerando análise com IA..."):
            system_prompt = st.session_state.get("llm_prompt")
            llm = LLMClient(
                api_key,
                model=llm_model,
                prompt=system_prompt,
            )
            llm_text = llm.generate(stats, active_mods)
        if not llm_text:
            llm_text = "(A IA retornou uma resposta vazia.)"
        st.session_state.llm_insight_text = llm_text
        st.session_state.pop("llm_insight_pending", None)
        st.toast(":material/check_circle: Análise concluída!")
        with st.expander(":material/smart_toy: Análise da IA", expanded=True):
            _render_insight_body(llm_text, source="llm")
    except (LLMUnavailableError, Exception):
        st.error(
            "Não foi possível gerar a análise. "
            "Verifique sua conexão ou chave de API."
        )
        st.session_state.pop("llm_insight_pending", None)
    finally:
        st.session_state.llm_insight_in_flight = False


# ---------------------------------------------------------------------------
# Insight body
# ---------------------------------------------------------------------------

def _render_insight_body(text: str, source: str = "rules") -> None:
    """Render insight markdown with a source caption."""
    if source == "llm":
        model = st.session_state.get("llm_model", "GPT-OSS")
        caption = (
            f":material/smart_toy: Gerado por {model} (OpenRouter) · "
            "Análise automática baseada nos seus dados"
        )
    else:
        caption = ":material/bar_chart: Análise automática baseada nos seus dados"

    st.markdown(md_escape(text))
    st.caption(caption)
