"""
Settings tab — exam prices, monthly goal, danger zone.

Renders the "Config" tab per Sprint 5 plan.
Also exports ensure_settings() for session_state initialization used
by every tab module.
"""

from datetime import date
from typing import Any

import sqlalchemy as sa
import streamlit as st

from src.db import DEFAULT_GOAL, DEFAULT_PRICES, load_goal, load_prices, save_goal, save_prices


def ensure_settings(conn: Any) -> None:
    """Idempotent: populates st.session_state.prices and .goal from DB if absent.

    Called once at the start of every tab render function. The DB is the
    source of truth; session_state is a per-session cache.
    """
    if "prices" not in st.session_state:
        st.session_state.prices = load_prices(conn)
    if "goal" not in st.session_state:
        today = date.today()
        st.session_state.goal = load_goal(conn, today.isoformat()[:7])


def render_settings_tab(conn: Any) -> None:
    """Render the complete Settings tab: prices, monthly goal, danger zone."""
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    st.header("⚙️ Configurações")

    _render_settings_form(conn, year_month)
    st.divider()
    _render_danger_zone(conn)


@st.fragment
def _render_settings_form(conn: Any, year_month: str) -> None:
    """Fragment: isolated rerun — save doesn't freeze the whole page."""
    prices = st.session_state.prices
    current_goal = st.session_state.goal

    st.subheader("Preços dos Exames")
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
            "RX (R$)", min_value=0.01, step=0.01,
            format="%.2f", value=prices["rx"], key="cfg_rx",
        )

    st.subheader("Meta Mensal")
    goal = st.number_input(
        "Meta mensal (R$)", min_value=0.0, step=100.0,
        value=current_goal, key="cfg_goal",
    )

    st.button(
        "💾 Salvar configurações", type="primary",
        on_click=lambda: _save_settings(conn, year_month, rm, tc, rx, goal),
    )


def _save_settings(
    conn: Any, year_month: str, rm: float, tc: float, rx: float, goal: float
) -> None:
    """Persist settings to DB + session_state, then show toast."""
    if rm <= 0 or tc <= 0 or rx <= 0:
        st.error("Os preços devem ser maiores que zero.")
        return
    save_prices(conn, rm, tc, rx)
    save_goal(conn, year_month, goal)
    st.session_state.pop("historical_cache", None)
    st.session_state.prices = {"rm": rm, "tc": tc, "rx": rx}
    st.session_state.goal = goal
    st.toast("✅ Configurações salvas! Recarregue para aplicar.")


@st.fragment
def _render_danger_zone(conn: Any) -> None:
    """Fragment: isolated rerun scope. Uses on_click to avoid double-click bug."""
    st.subheader("⚠️ Zona de Perigo")

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if not st.session_state.confirm_delete:
        st.button(
            "🗑️ Limpar todos os dados", type="secondary",
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
                "✅ Sim, limpar tudo", type="primary",
                on_click=lambda: _execute_delete(conn),
            )
        with col2:
            st.button(
                "❌ Cancelar",
                on_click=lambda: st.session_state.update(confirm_delete=False),
            )


def _execute_delete(conn: Any) -> None:
    """Delete all data and reset session state."""
    _delete_all_data(conn)
    st.session_state.update(
        confirm_delete=False,
        prices=dict(DEFAULT_PRICES),
        goal=DEFAULT_GOAL,
    )
    st.session_state.pop("historical_cache", None)
    st.cache_data.clear()
    st.toast("🗑️ Todos os dados foram removidos.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _delete_all_data(conn: Any) -> None:
    """Delete all rows from all 3 tables within a single transaction."""
    import sqlite3
    raw = sqlite3.connect("data/telerrad.db")
    raw.execute("DELETE FROM daily_production")
    raw.execute("DELETE FROM exam_prices")
    raw.execute("DELETE FROM monthly_goals")
    raw.commit()
    raw.close()
