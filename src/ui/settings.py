"""
Settings tab — modality configuration, monthly goal, LLM model, danger zone.

v2: replaces hardcoded RM/TC/RX prices with dynamic modality grid.
Each modality gets a row: label, price, exams/hour, active toggle.
"""

from datetime import date
from typing import Any

import sqlalchemy as sa
import streamlit as st

from src.db import (
    add_modality,
    deactivate_modality,
    get_connection,
    load_active_modalities,
    load_all_modalities,
    load_goal,
    load_setting,
    save_goal,
    save_modality,
    save_setting,
    slugify,
)
from src.i18n import t


def ensure_settings(conn: Any) -> None:
    """Idempotent: populates st.session_state from DB if absent.

    Called once at the start of every tab render function.
    """
    if "all_modalities" not in st.session_state:
        st.session_state.all_modalities = load_all_modalities(conn)
    if "active_modalities" not in st.session_state:
        st.session_state.active_modalities = load_active_modalities(conn)
    if "goal" not in st.session_state:
        today = date.today()
        st.session_state.goal = load_goal(conn, today.isoformat()[:7])
    if "user_name" not in st.session_state:
        st.session_state.user_name = load_setting(conn, "user_name", "")
    if "lang" not in st.session_state:
        st.session_state.lang = load_setting(conn, "language", "en")
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
        raw = load_setting(conn, "thinking_effort", "high")
        valid_efforts = {"low", "medium", "high", "xhigh"}
        st.session_state.thinking_effort = raw if raw in valid_efforts else "high"
    if "thinking_budget" not in st.session_state:
        raw = load_setting(conn, "thinking_budget", "")
        try:
            st.session_state.thinking_budget = int(raw) if raw else None
        except (ValueError, TypeError):
            st.session_state.thinking_budget = None
    if "thinking_mode" not in st.session_state:
        raw = load_setting(conn, "thinking_mode", "effort")
        valid_modes = {"effort", "budget"}
        st.session_state.thinking_mode = raw if raw in valid_modes else "effort"
    if "temperature" not in st.session_state:
        st.session_state.temperature = float(load_setting(conn, "temperature", "0.3"))


_DEFAULT_LLM_PROMPT = (
    "You are a personal productivity assistant for a radiologist "
    "named {user_name}. "
    "Analyze the production data below and produce a complete, detailed "
    "analysis in American English, with a friendly, direct, professional "
    "tone. Use the real numbers. Analyze trends, seasonality, modality "
    "mix composition, work pace, projections and risks. "
    "Be analytical and deep. Give actionable, specific suggestions, "
    "cite exact values and compare with previous periods."
)

# Budget constraints (OpenRouter docs: 1024–32000)
_MIN_REASONING_BUDGET = 1024
_MAX_REASONING_BUDGET = 32000


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
    st.cache_data.clear()
    st.session_state.all_modalities = load_all_modalities(conn)
    st.session_state.active_modalities = load_active_modalities(conn)


@st.fragment
def _render_modality_grid(conn: Any) -> None:
    """Fragment: per-modality label, price, exams/hour, color, active, delete."""
    all_mods = st.session_state.all_modalities

    st.subheader(f":material/medical_services: {t('web.settings.section.modalities')}")
    st.caption(t("web.settings.modalities.caption"))

    # Header row — extra column for delete button
    h_label, h_price, h_eph, h_color, h_active, h_del = st.columns(
        [3.0, 2.0, 2.0, 0.4, 0.3, 0.3]
    )
    with h_label:
        st.caption(f"**{t('web.settings.grid.modality')}**")
    with h_price:
        st.caption(f"**{t('web.settings.grid.price')}**")
    with h_eph:
        st.caption(f"**{t('web.settings.grid.exams_h')}**")
    with h_color:
        st.caption(f"**{t('web.settings.grid.color')}**")
    with h_active:
        st.caption(f"**{t('web.settings.grid.active')}**")
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
                t("web.settings.grid.name_a11y", slug=slug),
                value=label,
                key=f"mod_label_{slug}",
                label_visibility="collapsed",
            )
        with col_price:
            price = st.number_input(
                t("web.settings.grid.price_a11y", slug=slug),
                min_value=0.0, step=0.50, format="%.2f",
                value=float(m["price"]),
                key=f"mod_price_{slug}",
                label_visibility="collapsed",
            )
        with col_eph:
            eph = st.number_input(
                t("web.settings.grid.eph_a11y", slug=slug),
                min_value=0.0, step=0.5, format="%.1f",
                value=float(m["exams_per_hour"]),
                key=f"mod_eph_{slug}",
                label_visibility="collapsed",
            )
        with col_color:
            color = st.color_picker(
                t("web.settings.grid.color_a11y", slug=slug),
                value=str(m.get("color", "#64748B")),
                key=f"mod_color_{slug}",
                label_visibility="collapsed",
            )
        with col_active:
            active = st.checkbox(
                t("web.settings.grid.active_a11y", slug=slug),
                value=bool(m["active"]),
                key=f"mod_active_{slug}",
                label_visibility="collapsed",
            )
        with col_del:
            if st.button(
                ":material/delete:", key=f"mod_del_btn_{slug}",
                help=t("web.settings.grid.delete_help", label=label),
            ):
                st.session_state.confirm_delete_slug = slug
                st.rerun()

        # Inline delete confirmation for this row
        if st.session_state.get("confirm_delete_slug") == slug:
            st.warning(t("web.settings.grid.confirm_deactivate", label=label))
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button(t("web.settings.grid.deactivate"), key=f"mod_del_confirm_{slug}"):
                    deactivate_modality(conn, slug)
                    _reload_modalities(conn)
                    st.session_state.confirm_delete_slug = None
                    st.rerun()
            with col_no:
                if st.button(t("web.settings.grid.cancel"), key=f"mod_del_cancel_{slug}"):
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
            f":material/save: {t('web.settings.grid.save')}",
            on_click=lambda: _save_modalities(conn, updated),
        )
    else:
        st.caption(t("web.settings.grid.no_changes"))

    # ── Add new modality section ──
    if not st.session_state.get("new_modality_pending", False):
        if st.button(f":material/add: {t('web.settings.grid.add')}", type="secondary"):
            st.session_state.new_modality_pending = True
            st.rerun()
    else:
        col_label, col_price, col_eph, col_color, col_save, col_cancel = st.columns(
            [3.0, 2.0, 2.0, 0.4, 0.3, 0.3]
        )

        with col_label:
            new_label = st.text_input(
                t("web.settings.grid.new_name"),
                key="mod_new_label",
                label_visibility="collapsed",
                placeholder=t("web.settings.grid.new_name_ph"),
            )
            if new_label:
                new_slug = slugify(new_label)
                st.caption(t("web.settings.grid.slug", slug=new_slug))
            else:
                new_slug = ""

        with col_price:
            new_price = st.number_input(
                t("web.settings.grid.price"), min_value=0.0, step=0.50, value=0.0,
                key="mod_new_price", label_visibility="collapsed",
            )
        with col_eph:
            new_eph = st.number_input(
                t("web.settings.grid.exams_h"), min_value=0.0, step=0.5, value=0.0,
                key="mod_new_eph", label_visibility="collapsed",
            )
        with col_color:
            new_color = st.color_picker(
                t("web.settings.grid.color"), value="#64748B",
                key="mod_new_color", label_visibility="collapsed",
            )

        with col_save:
            if st.button(
                ":material/save:", key="mod_new_save",
                disabled=not new_label,
            ):
                new_slug = slugify(new_label)
                success = add_modality(
                    conn, new_slug, new_label, new_price, new_eph, 1, new_color,
                )
                if success:
                    _reload_modalities(conn)
                    st.session_state.new_modality_pending = False
                    st.toast(
                        f":material/check_circle: "
                        f"{t('web.settings.grid.added_toast', label=new_label)}"
                    )
                    st.rerun()
                else:
                    st.warning(t("web.settings.grid.slug_exists", slug=new_slug))
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
        f":material/check_circle: {t('web.settings.grid.saved_toast')}"
    )


# ---------------------------------------------------------------------------
# Personalization section (name + monthly goal)
# ---------------------------------------------------------------------------


@st.fragment
def _render_personalization_section(conn: Any, year_month: str) -> None:
    """Fragment: user name and monthly goal side by side."""
    current_goal = st.session_state.goal
    current_name = st.session_state.get("user_name", "")

    st.subheader(f":material/person: {t('web.settings.section.personal')}")
    col_name, col_goal = st.columns(2)
    with col_name:
        st.text_input(
            t("web.settings.personal.name"), value=current_name, key="cfg_name",
            placeholder=t("web.settings.personal.name"),
        )
    with col_goal:
        st.number_input(
            t("web.settings.personal.goal"), min_value=0.0, step=100.0,
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

    st.subheader(f":material/smart_toy: {t('web.settings.section.ai')}")

    col_api, col_model = st.columns(2)
    with col_api:
        api_key = st.text_input(
            t("web.settings.ai.api_key"), type="password",
            value=current_api_key, key="cfg_apikey",
            placeholder="sk-or-v1-...",
        )
    with col_model:
        llm_model = st.text_input(
            t("web.settings.ai.model"),
            value=current_model,
            key="cfg_llm_model",
            placeholder="openai/gpt-oss-120b:free",
        )
    if llm_model and "/" not in llm_model:
        st.warning(
            t("web.settings.ai.invalid_slug"),
            icon=":material/warning:",
        )

    thinking_enabled = st.toggle(
        t("web.settings.ai.thinking"),
        value=st.session_state.thinking_enabled,
        help=t("web.settings.ai.thinking_help"),
    )

    thinking_mode = st.session_state.thinking_mode

    if thinking_enabled:
        st.radio(
            "modo_pensamento",
            options=["effort", "budget"],
            format_func={
                "effort": t("web.settings.ai.mode_effort"),
                "budget": t("web.settings.ai.mode_budget"),
            }.get,
            horizontal=True,
            key="thinking_mode",
            label_visibility="collapsed",
        )

    col_effort, col_budget, col_temp = st.columns(3)
    with col_effort:
        thinking_effort = (
            st.selectbox(
                t("web.settings.ai.effort"),
                options=["low", "medium", "high", "xhigh"],
                index=["low", "medium", "high", "xhigh"].index(
                    st.session_state.thinking_effort
                ) if st.session_state.thinking_effort in ("low", "medium", "high", "xhigh") else 2,
                help=t("web.settings.ai.effort_help"),
            )
            if thinking_enabled else None
        )
    with col_budget:
        thinking_budget = (
            st.number_input(
                t("web.settings.ai.budget"),
                min_value=_MIN_REASONING_BUDGET, max_value=_MAX_REASONING_BUDGET, step=1024,
                value=st.session_state.thinking_budget or _MAX_REASONING_BUDGET,
                help=t("web.settings.ai.budget_help"),
                key="cfg_budget",
            )
            if thinking_enabled else None
        )
    with col_temp:
        temperature = st.slider(
            t("web.settings.ai.temperature"),
            min_value=0.0, max_value=2.0, step=0.1,
            value=st.session_state.get("temperature", 0.3),
            help=t("web.settings.ai.temperature_help"),
        )

    system_prompt = st.text_area(
        t("web.settings.ai.prompt"), value=current_prompt, height=200, key="cfg_prompt",
        placeholder=_DEFAULT_LLM_PROMPT,
    )
    st.caption(t("web.settings.ai.prompt_hint"))

    st.button(
        f":material/save: {t('web.settings.ai.save')}",
        on_click=lambda: _save_llm_settings(
            conn, st.session_state.cfg_goal, st.session_state.cfg_name,
            api_key, llm_model, system_prompt,
            thinking_enabled, thinking_mode, thinking_effort, thinking_budget,
            temperature,
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
    thinking_mode: str,
    thinking_effort: str | None,
    thinking_budget: int | None,
    temperature: float,
) -> None:
    """Persist LLM settings to DB + session_state. Validates required fields."""
    year_month = date.today().isoformat()[:7]
    errors: list[str] = []
    if not user_name.strip():
        errors.append(t("web.settings.ai.err.name"))
    if not (goal > 0.0):
        errors.append(t("web.settings.ai.err.goal"))
    if not api_key.strip():
        errors.append(t("web.settings.ai.err.api_key"))
    if not system_prompt.strip():
        errors.append(t("web.settings.ai.err.prompt"))
    if not llm_model.strip():
        errors.append(t("web.settings.ai.err.model"))
    if "/" not in llm_model.strip():
        errors.append(t("web.settings.ai.err.model_slug"))

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
    save_setting(conn, "thinking_mode", thinking_mode)
    save_setting(conn, "temperature", str(temperature))

    st.cache_data.clear()
    st.session_state.goal = goal
    st.session_state.user_name = user_name
    st.session_state.api_key = api_key
    st.session_state.llm_model = llm_model.strip()
    st.session_state.llm_prompt = system_prompt
    st.session_state.thinking_enabled = thinking_enabled
    st.session_state.thinking_effort = thinking_effort
    st.session_state.thinking_budget = thinking_budget
    st.session_state.temperature = temperature
    st.toast(f":material/check_circle: {t('web.settings.ai.saved_toast')}")


# ---------------------------------------------------------------------------
# Danger zone
# ---------------------------------------------------------------------------

@st.fragment
def _render_danger_zone() -> None:
    """Fragment: isolated rerun scope."""
    st.subheader(f":material/warning: {t('web.settings.danger.title')}")

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if not st.session_state.confirm_delete:
        st.button(
            f":material/delete: {t('web.settings.danger.clear')}", type="secondary",
            on_click=lambda: st.session_state.update(confirm_delete=True),
        )
    else:
        st.warning(t("web.settings.danger.confirm"))
        col1, col2 = st.columns(2)
        with col1:
            st.button(
                f":material/check_circle: {t('web.settings.danger.yes')}", type="primary",
                on_click=_execute_delete,
            )
        with col2:
            st.button(
                f":material/close: {t('web.settings.grid.cancel')}",
                on_click=lambda: st.session_state.update(confirm_delete=False),
            )


def _execute_delete() -> None:
    """Delete all data and reset session state."""
    _delete_all_data()
    st.session_state.update(
        confirm_delete=False,
        goal=0.0,
        all_modalities=[],
        active_modalities=[],
        llm_model="",
    )
    st.cache_data.clear()
    st.toast(f":material/delete: {t('web.settings.danger.cleared_toast')}")


def _delete_all_data() -> None:
    """Delete all rows from all tables via the app's SQL connection."""
    conn = get_connection()
    with conn.connect() as db_conn:
        db_conn.execute(sa.text("DELETE FROM daily_production_items"))
        db_conn.execute(sa.text("DELETE FROM modality_prices"))
        db_conn.execute(sa.text("DELETE FROM modalities"))
        db_conn.execute(sa.text("DELETE FROM monthly_goals"))
        db_conn.execute(sa.text("DELETE FROM user_settings"))
        db_conn.commit()
