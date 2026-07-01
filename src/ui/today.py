"""
Today tab — KPI cards, modality donut, and sparkline.

v2: dynamic modalities from st.session_state.active_modalities.
"""

from datetime import date
from typing import Any, Literal

import pandas as pd
import streamlit as st
from streamlit_extras.stoggle import stoggle

from src.calculations import (
    _compute_daily_earnings_from_items,
    compute_daily_stats,
    compute_monthly_stats,
)
from src.charts import build_daily_sparkline, build_modality_bar
from src.db import load_month_items
from src.formatting import fmt_brl, md_escape
from src.ui.settings import ensure_settings


def render_today_tab(conn: Any) -> None:
    """Render the complete "Hoje" tab."""
    today = date.today()
    today_str = today.isoformat()
    year_month = today_str[:7]

    ensure_settings(conn)
    active_mods = st.session_state.active_modalities
    goal = st.session_state.goal

    if not active_mods:
        _render_empty_state("Nenhuma modalidade ativa. Configure na aba Configuração.")
        return

    stats = compute_daily_stats(conn, today_str, active_mods)

    if not stats["has_data"]:
        _render_empty_state(
            "Comece registrando sua produção de hoje na **barra lateral**."
        )
        return

    # ── KPI Row ──
    _render_kpi_row(stats, goal, conn, year_month, active_mods)

    # ── Donut + Sparkline ──
    spark = _build_sparkline_figure(conn, year_month, active_mods)

    st.subheader(":material/dashboard: Visão geral")
    col_left, col_right = st.columns(2)
    with col_left:
        bar_chart = build_modality_bar(
            stats["modality_counts"], stats["modality_labels"],
            modalities=st.session_state.active_modalities,
        )
        st.plotly_chart(bar_chart, width="stretch")
    with col_right:
        if spark is not None:
            st.plotly_chart(spark, width="stretch")

    # ── Raw data toggle ──
    raw_lines = [f"Data: {today_str}"]
    for slug, count in stats["modality_counts"].items():
        label = stats["modality_labels"].get(slug, slug)
        raw_lines.append(f"{label}: {count}")
    raw_lines.append(f"Faturamento: {fmt_brl(stats['earnings_today'])}")
    raw_lines.append(f"Horas: {stats['estimated_hours']:.1f}h")
    stoggle("Ver dados brutos", "\n".join(raw_lines))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _render_empty_state(message: str) -> None:
    """Render the friendly empty-state card."""
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(":material/content_paste:", text_alignment="center")
            st.subheader("Nenhum registro ainda")
            st.markdown(message)
            st.caption("Os dados aparecerão aqui assim que você salvar.")


def _render_kpi_row(
    stats: dict[str, Any],
    goal: float,
    conn: Any,
    year_month: str,
    active_mods: list[dict[str, Any]],
) -> None:
    """Render the 4 KPI metric cards."""
    k1, k2, k3, k4 = st.columns(4, vertical_alignment="center")

    # ── Card 1: Faturamento Hoje ──
    with k1:
        with st.container(border=True, height="stretch"):
            earnings = stats["earnings_today"]
            if stats["delta_pct"] is not None:
                delta_str = f"{stats['delta_pct']:+.1f}% vs ontem"
            else:
                delta_str = "— sem dados de ontem"

            st.metric(
                label=":material/payments: Faturamento hoje",
                value=fmt_brl(earnings),
                delta=delta_str,
                delta_color="normal" if stats["delta_pct"] is not None else "off",
            )

    # ── Card 2: Exames Hoje ──
    with k2:
        with st.container(border=True, height="stretch"):
            total = stats["exam_count_today"]
            parts = []
            for slug, count in sorted(stats["modality_counts"].items()):
                label = stats["modality_labels"].get(slug, slug)
                parts.append(f"{label} {count}")
            pills = "  ·  ".join(parts) if parts else "—"

            st.metric(
                label=":material/content_paste: Exames hoje",
                value=str(total),
                delta=pills,
                delta_color="off",
            )

    # ── Card 3: Horas Estimadas ──
    with k3:
        with st.container(border=True, height="stretch"):
            hours = stats["estimated_hours"]
            st.metric(
                label=":material/timer: Horas estimadas",
                value=f"{hours:.1f}h",
            )

    # ── Card 4: Meta Mensal ──
    with k4:
        with st.container(border=True, height="stretch"):
            month_stats = compute_monthly_stats(conn, year_month, goal, active_mods)
            mtd = month_stats["mtd_earnings"]
            pct = (mtd / goal * 100) if goal > 0 else 0.0
            badge_color: Literal["green", "orange"] = (
                "green" if pct >= 50 else "orange"
            )
            st.metric(
                label=":material/target: Meta mensal",
                value=f"{pct:.0f}%",
                delta=md_escape(f"{fmt_brl(mtd)} / {fmt_brl(goal)}"),
                delta_color="off",
            )
            st.badge(
                "No ritmo" if pct >= 50 else "Atenção",
                icon=":material/target:",
                color=badge_color,
            )


def _build_sparkline_figure(
    conn: Any, year_month: str, active_mods: list[dict[str, Any]],
):
    """Load recent 7 days of earnings and build sparkline."""

    current_items = load_month_items(conn, year_month)

    # Compute daily earnings from items
    if current_items.empty:
        return None

    daily = _compute_daily_earnings_from_items(conn, current_items)
    if daily.empty:
        return None

    # If <7 days in current month, pull from previous month
    if len(daily) < 7:
        y, m = int(year_month[:4]), int(year_month[5:7])
        if m == 1:
            prev_ym = f"{y - 1}-12"
        else:
            prev_ym = f"{y}-{m - 1:02d}"
        prev_items = load_month_items(conn, prev_ym)
        if not prev_items.empty:
            prev_daily = _compute_daily_earnings_from_items(conn, prev_items)
            daily = pd.concat([prev_daily, daily], ignore_index=True)

    daily = daily.sort_values("date").tail(7)

    if len(daily) >= 1:
        return build_daily_sparkline(daily)
    return None


