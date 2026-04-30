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
    """Render the complete Settings tab: prices, monthly goal, danger zone.

    Layout:
      - 3 number_inputs for RM/TC/RX prices (format="%.2f", prefix in label)
      - 1 number_input for monthly goal
      - Save button → persists to DB + updates st.session_state
      - Danger zone with double-confirmation delete
    """
    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    prices = st.session_state.prices
    current_goal = st.session_state.goal

    st.header("⚙️ Configurações")

    # ── Preços dos Exames ──
    st.subheader("Preços dos Exames")
    st.caption("Valores em reais (R$) por exame. Alterações entram em vigor imediatamente.")

    col_rm, col_tc, col_rx = st.columns(3)
    with col_rm:
        rm = st.number_input(
            "RM (R$)", min_value=0.01, step=0.01,
            format="%.2f", value=prices["rm"],
        )
    with col_tc:
        tc = st.number_input(
            "TC (R$)", min_value=0.01, step=0.01,
            format="%.2f", value=prices["tc"],
        )
    with col_rx:
        rx = st.number_input(
            "RX (R$)", min_value=0.01, step=0.01,
            format="%.2f", value=prices["rx"],
        )

    # ── Meta Mensal ──
    st.subheader("Meta Mensal")
    goal = st.number_input(
        "Meta mensal (R$)", min_value=0.0, step=100.0,
        value=current_goal,
    )

    # ── Botão Salvar ──
    if st.button("💾 Salvar configurações", type="primary"):
        if rm <= 0 or tc <= 0 or rx <= 0:
            st.error("Os preços devem ser maiores que zero.")
        else:
            save_prices(conn, rm, tc, rx)
            save_goal(conn, year_month, goal)
            # Sync session_state immediately so all tabs reflect the change
            st.session_state.prices = {"rm": rm, "tc": tc, "rx": rx}
            st.session_state.goal = goal
            st.toast("✅ Configurações salvas!")

    # ── Zona de Perigo ──
    st.divider()
    st.subheader("⚠️ Zona de Perigo")

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if not st.session_state.confirm_delete:
        if st.button("🗑️ Limpar todos os dados", type="secondary"):
            st.session_state.confirm_delete = True
            st.rerun()
    else:
        st.warning(
            "Tem certeza? **Esta ação não pode ser desfeita.** "
            "Todos os dados de produção, preços e metas serão removidos. "
            "Os valores padrão serão restaurados "
            "(RM=R$35, TC=R$25, RX=R$4,50, meta=R$45.000)."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Sim, limpar tudo", type="primary"):
                _delete_all_data(conn)
                st.session_state.confirm_delete = False
                # Reset session_state to defaults
                st.session_state.prices = dict(DEFAULT_PRICES)
                st.session_state.goal = DEFAULT_GOAL
                st.toast("🗑️ Todos os dados foram removidos.")
                st.rerun()
        with col2:
            if st.button("❌ Cancelar"):
                st.session_state.confirm_delete = False
                st.rerun()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _delete_all_data(conn: Any) -> None:
    """Delete all rows from all 3 tables within a single transaction."""
    with conn.connect() as db_conn:
        db_conn.execute(sa.text("DELETE FROM daily_production"))
        db_conn.execute(sa.text("DELETE FROM exam_prices"))
        db_conn.execute(sa.text("DELETE FROM monthly_goals"))
        db_conn.commit()
