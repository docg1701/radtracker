"""
Settings tab — exam prices, monthly goal, danger zone.

Renders the "Config" tab per Sprint 5 plan.
Also exports ensure_settings() for session_state initialization used
by every tab module.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.db import (
    DEFAULT_GOAL,
    DEFAULT_PRICES,
    load_goal,
    load_prices,
    load_setting,
    save_goal,
    save_prices,
    save_setting,
)


def ensure_settings(conn: Any) -> None:
    """Idempotent: populates st.session_state from DB if absent.

    Called once at the start of every tab render function. The DB is the
    source of truth; session_state is a per-session cache.
    """
    if "prices" not in st.session_state:
        st.session_state.prices = load_prices(conn)
    if "goal" not in st.session_state:
        today = date.today()
        st.session_state.goal = load_goal(conn, today.isoformat()[:7])
    if "user_name" not in st.session_state:
        st.session_state.user_name = load_setting(conn, "user_name", "Galvani")
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_setting(conn, "api_key", "")
    if "llm_prompt" not in st.session_state:
        default_prompt = _DEFAULT_LLM_PROMPT.replace(
            "{user_name}", st.session_state.user_name
        )
        st.session_state.llm_prompt = load_setting(conn, "llm_prompt", default_prompt)


_DEFAULT_LLM_PROMPT = (
    "Você é um assistente pessoal de produtividade para um médico "
    "radiologista chamado {user_name}. "
    "Analise os dados de produção abaixo e produza uma análise completa "
    "e detalhada em português, com tom amigável, direto e profissional. "
    "Use os números reais. Analise tendências, sazonalidade, composição "
    "do mix de modalidades, ritmo de trabalho, projeções e riscos. "
    "Seja analítico e profundo. Dê sugestões acionáveis e específicas, "
    "cite valores exatos e compare com períodos anteriores."
)


def render_settings_tab(conn: Any) -> None:
    """Render the complete Settings tab: prices, monthly goal, danger zone."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    st.header(":material/settings: Configurações")

    _render_settings_form(conn, year_month)
    _render_danger_zone()


@st.fragment
def _render_settings_form(conn: Any, year_month: str) -> None:
    """Fragment: isolated rerun — save doesn't freeze the whole page."""
    prices = st.session_state.prices
    current_goal = st.session_state.goal
    current_name = st.session_state.get("user_name", "Galvani")
    current_api_key = st.session_state.get("api_key", "")
    current_prompt = st.session_state.get("llm_prompt", _DEFAULT_LLM_PROMPT)

    st.subheader("Preços dos exames")
    st.caption("Valores em reais (R$) por exame. Alterações entram em vigor imediatamente.")

    col_rm, col_tc, col_rx = st.columns(3)
    with col_rm:
        rm = st.number_input(
            "RM (R$)", min_value=0.01, step=0.01,
            format="%.2f", value=prices["rm"], key="cfg_rm",
        )
    with col_tc:
        tc = st.number_input(
            "TC (R$)", min_value=0.01, step=0.01,
            format="%.2f", value=prices["tc"], key="cfg_tc",
        )
    with col_rx:
        rx = st.number_input(
            "RX (R$)", min_value=0.01, step=0.50,
            format="%.2f", value=prices["rx"], key="cfg_rx",
        )

    st.subheader("Meta mensal")
    goal = st.number_input(
        "Meta mensal (R$)", min_value=0.0, step=100.0,
        value=current_goal, key="cfg_goal",
    )

    st.subheader("Personalização")
    user_name = st.text_input("Seu nome", value=current_name, key="cfg_name")

    st.subheader("IA — OpenRouter")
    api_key = st.text_input(
        "Chave API OpenRouter", type="password",
        value=current_api_key, key="cfg_apikey",
    )
    st.caption("[Obter chave gratuita no OpenRouter](https://openrouter.ai/keys)")

    system_prompt = st.text_area(
        "Prompt da IA", value=current_prompt, height=200, key="cfg_prompt",
    )
    st.caption("Use {user_name} como placeholder para o nome do usuário.")

    st.button(
        ":material/save: Salvar configurações", type="primary",
        on_click=lambda: _save_settings(
            conn, year_month, rm, tc, rx, goal,
            user_name, api_key, system_prompt,
        ),
    )


def _save_settings(
    conn: Any,
    year_month: str,
    rm: float,
    tc: float,
    rx: float,
    goal: float,
    user_name: str,
    api_key: str,
    system_prompt: str,
) -> None:
    """Persist settings to DB + session_state, then show toast."""
    if rm <= 0 or tc <= 0 or rx <= 0:
        st.error("Os preços devem ser maiores que zero.")
        return
    save_prices(conn, rm, tc, rx)
    save_goal(conn, year_month, goal)
    save_setting(conn, "user_name", user_name)
    save_setting(conn, "api_key", api_key)
    save_setting(conn, "llm_prompt", system_prompt)
    st.session_state.pop("historical_cache", None)
    st.session_state.prices = {"rm": rm, "tc": tc, "rx": rx}
    st.session_state.goal = goal
    st.session_state.user_name = user_name
    st.session_state.api_key = api_key
    st.session_state.llm_prompt = system_prompt
    st.toast(":material/check_circle: Configurações salvas! Recarregue para aplicar.")


@st.fragment
def _render_danger_zone() -> None:
    """Fragment: isolated rerun scope. Uses on_click to avoid double-click bug."""
    st.subheader("Zona de perigo")

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if not st.session_state.confirm_delete:
        st.button(
            ":material/delete: Limpar todos os dados", type="secondary",
            on_click=lambda: st.session_state.update(confirm_delete=True),
        )
    else:
        st.warning(
            "Tem certeza? **Esta ação não pode ser desfeita.** "
            "Todos os dados de produção, preços e metas serão removidos. "
            "Os valores padrão serão restaurados "
            "(RM=R\\$35, TC=R\\$25, RX=R\\$4,50, meta=R\\$45.000)."
        )
        col1, col2 = st.columns(2)
        with col1:
            st.button(
                ":material/check_circle: Sim, limpar tudo", type="primary",
                on_click=_execute_delete,
            )
        with col2:
            st.button(
                ":material/close: Cancelar",
                on_click=lambda: st.session_state.update(confirm_delete=False),
            )


def _execute_delete() -> None:
    """Delete all data and reset session state."""
    _delete_all_data()
    st.session_state.update(
        confirm_delete=False,
        prices=dict(DEFAULT_PRICES),
        goal=DEFAULT_GOAL,
    )
    st.session_state.pop("historical_cache", None)
    st.cache_data.clear()
    st.toast(":material/delete: Todos os dados foram removidos.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _delete_all_data() -> None:
    """Delete all rows from all 4 tables within a single transaction."""
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect("data/telerrad.db")) as raw:
        raw.execute("DELETE FROM daily_production")
        raw.execute("DELETE FROM exam_prices")
        raw.execute("DELETE FROM monthly_goals")
        raw.execute("DELETE FROM user_settings")
        raw.commit()
