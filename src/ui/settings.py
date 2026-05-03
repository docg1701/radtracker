"""
Settings tab — modality configuration, monthly goal, LLM model, danger zone.

v2: replaces hardcoded RM/TC/RX prices with dynamic modality grid.
Each modality gets a row: label, price, exams/hour, active toggle.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.db import (
    DEFAULT_GOAL,
    DEFAULT_LLM_MODEL,
    load_active_modalities,
    load_all_modalities,
    load_goal,
    load_setting,
    save_goal,
    save_modality,
    save_setting,
)


def ensure_settings(conn: Any) -> None:
    """Idempotent: populates st.session_state from DB if absent.

    Called once at the start of every tab render function.
    """
    if "all_modalities" not in st.session_state:
        st.session_state.all_modalities = load_all_modalities(conn)
    if "active_modalities" not in st.session_state:
        st.session_state.active_modalities = load_active_modalities(conn)
    if "prices" not in st.session_state:
        st.session_state.prices = {
            m["slug"]: m["price"] for m in st.session_state.active_modalities
        }
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
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = load_setting(
            conn, "llm_model", DEFAULT_LLM_MODEL
        )


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
    """Render the complete Settings tab."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    _render_modality_grid(conn)
    _render_llm_section(conn, year_month)
    _render_danger_zone()


# ---------------------------------------------------------------------------
# Modality configuration grid
# ---------------------------------------------------------------------------

@st.fragment
def _render_modality_grid(conn: Any) -> None:
    """Fragment: per-modality price, exams/hour, and active toggle."""
    all_mods = st.session_state.all_modalities

    st.subheader(":material/medical_services: Modalidades")
    st.caption(
        "Configure o preço (R$) e a produtividade (exames/hora) de cada "
        "modalidade. Marque **Ativo** para que apareça na barra lateral. "
        "Modalidades sem preço ou produtividade não aparecem no dashboard."
    )

    # Header row
    h_label, h_price, h_eph, h_color, h_active = st.columns([2.5, 2, 2, 0.8, 0.8])
    with h_label:
        st.caption("**Modalidade**")
    with h_price:
        st.caption("**Preço (R$)**")
    with h_eph:
        st.caption("**Exames/h**")
    with h_color:
        st.caption("**Cor**")
    with h_active:
        st.caption("**Ativo**")

    # Track changes in a form-like structure (but don't use st.form —
    # we want individual saves to work without freezing the whole page).
    updated: dict[str, tuple[float, float, bool, str]] = {}

    for m in all_mods:
        slug = m["slug"]
        label = m["label"]
        col_label, col_price, col_eph, col_color, col_active = (
            st.columns([2.5, 2, 2, 0.8, 0.8])
        )

        with col_label:
            st.write(label)
        with col_price:
            price = st.number_input(
                f"Preço {slug}",
                min_value=0.0, step=0.50, format="%.2f",
                value=float(m["price"]),
                key=f"mod_price_{slug}",
                label_visibility="collapsed",
            )
        with col_eph:
            eph = st.number_input(
                f"Exames/h {slug}",
                min_value=0.0, step=0.5, format="%.1f",
                value=float(m["exams_per_hour"]),
                key=f"mod_eph_{slug}",
                label_visibility="collapsed",
            )
        with col_color:
            color = st.color_picker(
                f"Cor {slug}",
                value=str(m.get("color", "#64748B")),
                key=f"mod_color_{slug}",
                label_visibility="collapsed",
            )
        with col_active:
            active = st.checkbox(
                f"Ativo {slug}",
                value=bool(m["active"]),
                key=f"mod_active_{slug}",
                label_visibility="collapsed",
            )

        changed = (
            abs(price - float(m["price"])) > 0.001
            or abs(eph - float(m["exams_per_hour"])) > 0.001
            or active != bool(m["active"])
            or color != str(m.get("color", "#64748B"))
        )
        if changed:
            updated[slug] = (price, eph, active, color)

    if updated:
        st.button(
            ":material/save: Salvar modalidades", type="primary",
            on_click=lambda: _save_modalities(conn, updated),
        )
    else:
        st.caption("Nenhuma alteração pendente.")


def _save_modalities(
    conn: Any, updated: dict[str, tuple[float, float, bool, str]]
) -> None:
    """Persist updated modality rows to DB and refresh session state."""
    for slug, (price, eph, active, color) in updated.items():
        save_modality(conn, slug, price, eph, 1 if active else 0, color=color)

    # Clear caches so sidebar/dashboards pick up changes
    st.session_state.pop("historical_cache", None)
    st.session_state.all_modalities = load_all_modalities(conn)
    st.session_state.active_modalities = load_active_modalities(conn)
    st.session_state.prices = {
        m["slug"]: m["price"] for m in st.session_state.active_modalities
    }
    st.toast(":material/check_circle: Modalidades salvas! Barra lateral atualizada.")


# ---------------------------------------------------------------------------
# LLM section (goal + model + api key + prompt)
# ---------------------------------------------------------------------------

@st.fragment
def _render_llm_section(conn: Any, year_month: str) -> None:
    """Fragment: monthly goal, LLM model, API key, system prompt."""
    current_goal = st.session_state.goal
    current_name = st.session_state.get("user_name", "Galvani")
    current_api_key = st.session_state.get("api_key", "")
    current_prompt = st.session_state.get("llm_prompt", _DEFAULT_LLM_PROMPT)
    current_model = st.session_state.get("llm_model", DEFAULT_LLM_MODEL)

    st.subheader(":material/target: Meta mensal")
    goal = st.number_input(
        "Meta mensal (R$)", min_value=0.0, step=100.0,
        value=current_goal, key="cfg_goal",
    )

    st.subheader(":material/person: Personalização")
    user_name = st.text_input("Seu nome", value=current_name, key="cfg_name")

    st.subheader(":material/smart_toy: IA — OpenRouter")
    api_key = st.text_input(
        "Chave API OpenRouter", type="password",
        value=current_api_key, key="cfg_apikey",
    )
    st.caption("[Obter chave gratuita no OpenRouter](https://openrouter.ai/keys)")

    llm_model = st.text_input(
        "Modelo OpenRouter (slug completo)",
        value=current_model,
        key="cfg_llm_model",
        placeholder="openai/gpt-oss-120b:free",
    )
    st.caption(
        "Digite o slug exato do modelo como aparece no site do OpenRouter "
        "(google/gemini-2.5-flash, anthropic/claude-sonnet-4)."
    )
    if llm_model and "/" not in llm_model:
        st.warning(
            "Slug inválido: use o formato provedor/modelo "
            "(ex: openai/gpt-oss-120b:free).",
            icon=":material/warning:",
        )

    system_prompt = st.text_area(
        "Prompt da IA", value=current_prompt, height=200, key="cfg_prompt",
    )
    st.caption("Use {user_name} como placeholder para o nome do usuário.")

    st.button(
        ":material/save: Salvar configurações", type="primary",
        on_click=lambda: _save_llm_settings(
            conn, year_month, goal, user_name, api_key, llm_model, system_prompt,
        ),
    )


def _save_llm_settings(
    conn: Any,
    year_month: str,
    goal: float,
    user_name: str,
    api_key: str,
    llm_model: str,
    system_prompt: str,
) -> None:
    """Persist LLM settings to DB + session_state."""
    save_goal(conn, year_month, goal)
    save_setting(conn, "user_name", user_name)
    save_setting(conn, "api_key", api_key)
    save_setting(conn, "llm_model", llm_model or DEFAULT_LLM_MODEL)
    save_setting(conn, "llm_prompt", system_prompt)

    st.session_state.pop("historical_cache", None)
    st.session_state.goal = goal
    st.session_state.user_name = user_name
    st.session_state.api_key = api_key
    st.session_state.llm_model = llm_model or DEFAULT_LLM_MODEL
    st.session_state.llm_prompt = system_prompt
    st.toast(":material/check_circle: Configurações salvas!")


# ---------------------------------------------------------------------------
# Danger zone
# ---------------------------------------------------------------------------

@st.fragment
def _render_danger_zone() -> None:
    """Fragment: isolated rerun scope."""
    st.subheader(":material/warning: Zona de perigo")

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
            "Todos os dados de produção e configurações serão removidos."
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
        prices={},
        goal=DEFAULT_GOAL,
        all_modalities=[],
        active_modalities=[],
        llm_model=DEFAULT_LLM_MODEL,
    )
    st.session_state.pop("historical_cache", None)
    st.cache_data.clear()
    st.toast(":material/delete: Todos os dados foram removidos.")


def _delete_all_data() -> None:
    """Delete all rows from all tables within a single transaction."""
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect("data/telerrad.db")) as raw:
        raw.execute("DELETE FROM daily_production_items")
        raw.execute("DELETE FROM modalities")
        raw.execute("DELETE FROM daily_production")
        raw.execute("DELETE FROM exam_prices")
        raw.execute("DELETE FROM monthly_goals")
        raw.execute("DELETE FROM user_settings")
        raw.commit()
