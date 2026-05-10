"""
Settings tab — modality configuration, monthly goal, LLM model, danger zone.

v2: replaces hardcoded RM/TC/RX prices with dynamic modality grid.
Each modality gets a row: label, price, exams/hour, active toggle.
"""

from datetime import date
from typing import Any

import streamlit as st

from src.db import (
    add_modality,
    delete_modality,
    load_active_modalities,
    load_all_modalities,
    load_goal,
    load_setting,
    save_goal,
    save_modality,
    save_setting,
    slugify,
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
        st.session_state.user_name = load_setting(conn, "user_name", "")
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_setting(conn, "api_key", "")
    if "llm_prompt" not in st.session_state:
        st.session_state.llm_prompt = load_setting(conn, "llm_prompt", "")
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = load_setting(conn, "llm_model", "")
    if "thinking_enabled" not in st.session_state:
        raw = load_setting(conn, "thinking_enabled", "1")
        st.session_state.thinking_enabled = raw in ("1", "true", "True")
    if "thinking_effort" not in st.session_state:
        st.session_state.thinking_effort = load_setting(conn, "thinking_effort", "high")
    if "thinking_budget" not in st.session_state:
        raw = load_setting(conn, "thinking_budget", "")
        st.session_state.thinking_budget = int(raw) if raw else None
    if "temperature" not in st.session_state:
        st.session_state.temperature = float(load_setting(conn, "temperature", "0.3"))


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
    _render_personalization_section(conn, year_month)
    _render_ai_section(conn)
    _render_danger_zone()


# ---------------------------------------------------------------------------
# Modality configuration grid
# ---------------------------------------------------------------------------


def _reload_modalities(conn: Any) -> None:
    """Clear caches and reload modalities + prices into session_state."""
    st.session_state.pop("historical_cache", None)
    st.session_state.all_modalities = load_all_modalities(conn)
    st.session_state.active_modalities = load_active_modalities(conn)
    st.session_state.prices = {
        m["slug"]: m["price"] for m in st.session_state.active_modalities
    }


@st.fragment
def _render_modality_grid(conn: Any) -> None:
    """Fragment: per-modality label, price, exams/hour, color, active, delete."""
    all_mods = st.session_state.all_modalities

    st.subheader(":material/medical_services: Modalidades")
    st.caption(
        "Configure nome, preço (R$) e produtividade (exames/hora) de cada "
        "modalidade. Marque **Ativo** para que apareça na barra lateral. "
        "Modalidades sem preço ou produtividade não aparecem no dashboard."
    )

    # Header row — extra column for delete button
    h_label, h_price, h_eph, h_color, h_active, h_del = st.columns(
        [3.0, 2.0, 2.0, 0.4, 0.3, 0.3]
    )
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
    with h_del:
        st.caption("")

    # Track changes — tuple: (label, price, eph, active, color)
    updated: dict[str, tuple[str, float, float, bool, str]] = {}

    for m in all_mods:
        slug = m["slug"]
        label = m["label"]
        col_label, col_price, col_eph, col_color, col_active, col_del = st.columns(
            [3.0, 2.0, 2.0, 0.4, 0.3, 0.3]
        )

        with col_label:
            new_label = st.text_input(
                f"Nome {slug}",
                value=label,
                key=f"mod_label_{slug}",
                label_visibility="collapsed",
            )
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
        with col_del:
            if st.button(
                ":material/delete:", key=f"mod_del_btn_{slug}",
                help=f"Remover {label}",
            ):
                st.session_state.confirm_delete_slug = slug
                st.rerun()

        # Inline delete confirmation for this row
        if st.session_state.get("confirm_delete_slug") == slug:
            st.warning(f"Remover **{label}**? Dados de produção serão perdidos.")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Confirmar", key=f"mod_del_confirm_{slug}"):
                    delete_modality(conn, slug)
                    _reload_modalities(conn)
                    st.session_state.confirm_delete_slug = None
                    st.rerun()
            with col_no:
                if st.button("Cancelar", key=f"mod_del_cancel_{slug}"):
                    st.session_state.confirm_delete_slug = None
                    st.rerun()

        changed = (
            new_label != label
            or abs(price - float(m["price"])) > 0.001
            or abs(eph - float(m["exams_per_hour"])) > 0.001
            or active != bool(m["active"])
            or color != str(m.get("color", "#64748B"))
        )
        if changed:
            updated[slug] = (new_label, price, eph, active, color)

    if updated:
        st.button(
            ":material/save: Salvar modalidades", type="primary",
            on_click=lambda: _save_modalities(conn, updated),
        )
    else:
        st.caption("Nenhuma alteração pendente.")

    # ── Add new modality section ──
    if not st.session_state.get("new_modality_pending", False):
        if st.button(":material/add: Adicionar modalidade", type="secondary"):
            st.session_state.new_modality_pending = True
            st.rerun()
    else:
        col_label, col_price, col_eph, col_color, col_save, col_cancel = st.columns(
            [3.0, 2.0, 2.0, 0.4, 0.3, 0.3]
        )

        with col_label:
            new_label = st.text_input(
                "Nome da nova modalidade",
                key="mod_new_label",
                label_visibility="collapsed",
                placeholder="Ex: Tomografia de Crânio",
            )
            if new_label:
                new_slug = slugify(new_label)
                st.caption(f"Slug: {new_slug}")
            else:
                new_slug = ""

        with col_price:
            new_price = st.number_input(
                "Preço", min_value=0.0, step=0.50, value=0.0,
                key="mod_new_price", label_visibility="collapsed",
            )
        with col_eph:
            new_eph = st.number_input(
                "Exames/h", min_value=0.0, step=0.5, value=0.0,
                key="mod_new_eph", label_visibility="collapsed",
            )
        with col_color:
            new_color = st.color_picker(
                "Cor", value="#64748B",
                key="mod_new_color", label_visibility="collapsed",
            )

        with col_save:
            if st.button(
                ":material/save:", key="mod_new_save", type="primary",
                disabled=not new_label,
            ):
                new_slug = slugify(new_label)
                success = add_modality(
                    conn, new_slug, new_label, new_price, new_eph, 1, new_color,
                )
                if success:
                    _reload_modalities(conn)
                    st.session_state.new_modality_pending = False
                    st.toast(f":material/check_circle: {new_label} adicionada!")
                    st.rerun()
                else:
                    st.warning(
                        f"Slug '{new_slug}' já existe. Escolha outro nome."
                    )
        with col_cancel:
            if st.button(":material/close:", key="mod_new_cancel"):
                st.session_state.new_modality_pending = False
                for key in ("mod_new_label", "mod_new_price", "mod_new_eph", "mod_new_color"):
                    st.session_state.pop(key, None)
                st.rerun()


def _save_modalities(
    conn: Any, updated: dict[str, tuple[str, float, float, bool, str]]
) -> None:
    """Persist updated modality rows to DB and refresh session state."""
    for slug, (label, price, eph, active, color) in updated.items():
        save_modality(
            conn, slug, price, eph, 1 if active else 0,
            label=label, color=color,
        )

    _reload_modalities(conn)
    st.toast(
        ":material/check_circle: Modalidades salvas! Barra lateral atualizada."
    )


# ---------------------------------------------------------------------------
# Personalization section (name + monthly goal)
# ---------------------------------------------------------------------------


@st.fragment
def _render_personalization_section(conn: Any, year_month: str) -> None:
    """Fragment: user name and monthly goal side by side."""
    current_goal = st.session_state.goal
    current_name = st.session_state.get("user_name", "")

    st.subheader(":material/person: Personalização")
    col_name, col_goal = st.columns(2)
    with col_name:
        st.text_input(
            "Seu nome", value=current_name, key="cfg_name",
            placeholder="Seu nome",
        )
    with col_goal:
        st.number_input(
            "Meta mensal (R$)", min_value=0.0, step=100.0,
            value=current_goal, key="cfg_goal",
        )


# ---------------------------------------------------------------------------
# AI section (api key + model + thinking + temperature + prompt)
# ---------------------------------------------------------------------------

@st.fragment
def _render_ai_section(conn: Any) -> None:
    """Fragment: OpenRouter API key, model, thinking, temperature, prompt."""
    current_api_key = st.session_state.get("api_key", "")
    current_prompt = st.session_state.get("llm_prompt", "")
    current_model = st.session_state.get("llm_model", "")

    st.subheader(":material/smart_toy: Inteligência Artificial")

    col_api, col_model = st.columns(2)
    with col_api:
        api_key = st.text_input(
            "Chave API OpenRouter", type="password",
            value=current_api_key, key="cfg_apikey",
            placeholder="sk-or-v1-...",
        )
    with col_model:
        llm_model = st.text_input(
            "Modelo OpenRouter (slug completo)",
            value=current_model,
            key="cfg_llm_model",
            placeholder="openai/gpt-oss-120b:free",
        )
    if llm_model and "/" not in llm_model:
        st.warning(
            "Slug inválido: use o formato provedor/modelo "
            "(ex: openai/gpt-oss-120b:free).",
            icon=":material/warning:",
        )

    thinking_enabled = st.toggle(
        "Ativar thinking mode",
        value=st.session_state.thinking_enabled,
        help="Modelo gera raciocínio interno antes da resposta. "
             "Mais qualidade analítica, maior custo de tokens.",
    )

    if thinking_enabled:
        col_effort, col_temp, col_budget = st.columns(3)
        with col_effort:
            thinking_effort = st.selectbox(
                "Nível de esforço",
                options=["low", "medium", "high", "xhigh"],
                index=["low", "medium", "high", "xhigh"].index(
                    st.session_state.thinking_effort
                ),
                help="Controla quantos tokens o modelo gasta pensando. "
                     "xhigh = análise mais profunda. "
                     "O OpenRouter traduz para o formato nativo de cada modelo.",
            )
        with col_temp:
            temperature = st.slider(
                "Temperatura",
                min_value=0.0, max_value=2.0, step=0.1,
                value=st.session_state.get("temperature", 0.3),
                help="Controla aleatoriedade (0 = determinístico, 2 = criativo). "
                     "Alguns modelos ignoram com thinking ligado. "
                     "Recomendado: 0.3 para análises.",
            )
        with col_budget:
            use_budget = st.toggle(
                "",
                value=st.session_state.thinking_budget is not None,
                label_visibility="collapsed",
            )
            thinking_budget = st.number_input(
                "Tokens de reasoning (ignora esforço)",
                min_value=1024, max_value=32000, step=1024,
                value=st.session_state.thinking_budget or 32000,
                disabled=not use_budget,
            )
    else:
        thinking_effort = None
        thinking_budget = None
        temperature = st.slider(
            "Temperatura",
            min_value=0.0, max_value=2.0, step=0.1,
            value=st.session_state.get("temperature", 0.3),
            help="Controla aleatoriedade (0 = determinístico, 2 = criativo). "
                 "Alguns modelos ignoram com thinking ligado. "
                 "Recomendado: 0.3 para análises.",
        )

    system_prompt = st.text_area(
        "Prompt inicial", value=current_prompt, height=200, key="cfg_prompt",
        placeholder=_DEFAULT_LLM_PROMPT,
    )
    st.caption("Use {user_name} como placeholder para o nome do usuário.")

    st.button(
        ":material/save: Salvar configurações", type="primary",
        on_click=lambda: _save_llm_settings(
            conn, st.session_state.cfg_goal, st.session_state.cfg_name,
            api_key, llm_model, system_prompt,
            thinking_enabled, thinking_effort, thinking_budget, temperature,
        ),
    )


def _save_llm_settings(
    conn: Any,
    goal: float,
    user_name: str,
    api_key: str,
    llm_model: str,
    system_prompt: str,
    thinking_enabled: bool,
    thinking_effort: str | None,
    thinking_budget: int | None,
    temperature: float,
) -> None:
    """Persist LLM settings to DB + session_state. Validates required fields."""
    year_month = date.today().isoformat()[:7]
    errors: list[str] = []
    if not user_name.strip():
        errors.append("Nome do usuário é obrigatório.")
    if not (goal > 0.0):
        errors.append("Meta mensal deve ser maior que zero.")
    if not api_key.strip():
        errors.append("Chave API OpenRouter é obrigatória.")
    if not system_prompt.strip():
        errors.append("Prompt inicial é obrigatório.")
    if not llm_model.strip():
        errors.append("Modelo LLM é obrigatório.")
    if "/" not in llm_model.strip():
        errors.append("Slug do modelo LLM inválido (formato: provedor/modelo).")

    if errors:
        for err in errors:
            st.error(err, icon=":material/error:")
        return

    save_goal(conn, year_month, goal)
    save_setting(conn, "user_name", user_name.strip())
    save_setting(conn, "api_key", api_key.strip())
    save_setting(conn, "llm_model", llm_model.strip())
    save_setting(conn, "llm_prompt", system_prompt.strip())
    save_setting(conn, "thinking_enabled", "1" if thinking_enabled else "0")
    if thinking_effort:
        save_setting(conn, "thinking_effort", thinking_effort)
    if thinking_budget is not None:
        save_setting(conn, "thinking_budget", str(thinking_budget))
    save_setting(conn, "temperature", str(temperature))

    st.session_state.pop("historical_cache", None)
    st.session_state.goal = goal
    st.session_state.user_name = user_name
    st.session_state.api_key = api_key
    st.session_state.llm_model = llm_model.strip()
    st.session_state.llm_prompt = system_prompt
    st.session_state.thinking_enabled = thinking_enabled
    st.session_state.thinking_effort = thinking_effort
    st.session_state.thinking_budget = thinking_budget
    st.session_state.temperature = temperature
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
        goal=0.0,
        all_modalities=[],
        active_modalities=[],
        llm_model="",
    )
    st.session_state.pop("historical_cache", None)
    st.cache_data.clear()
    st.toast(":material/delete: Todos os dados foram removidos.")


def _delete_all_data() -> None:
    """Delete all rows from all tables via the app's SQL connection."""
    import sqlalchemy as sa
    import streamlit as st

    conn = st.connection("telerrad", type="sql")
    with conn.connect() as db_conn:
        db_conn.execute(sa.text("DELETE FROM daily_production_items"))
        db_conn.execute(sa.text("DELETE FROM modalities"))
        db_conn.execute(sa.text("DELETE FROM daily_production"))
        db_conn.execute(sa.text("DELETE FROM exam_prices"))
        db_conn.execute(sa.text("DELETE FROM monthly_goals"))
        db_conn.execute(sa.text("DELETE FROM user_settings"))
        db_conn.commit()
