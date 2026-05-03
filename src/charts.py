"""
Plotly chart factory functions for radtracker — v2 dynamic modalities.

Every function accepts data as parameters and returns a plotly Figure.
No database access here.
"""

import calendar
from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from src.chart_colors import (
    CHART_COLORS,
    color_for_modality,
    get_chart_text_color,
    hex_to_rgba,
)
from src.formatting import MONTHS_PT

# ---------------------------------------------------------------------------
# Modality bar chart (dynamic)
# ---------------------------------------------------------------------------


def build_modality_bar(
    counts: dict[str, int],
    labels_lookup: dict[str, str],
    modalities: list[dict[str, Any]] | None = None,
) -> go.Figure:
    """
    Build a horizontal bar chart showing exam count by modality.

    Args:
        counts: dict slug→count (only positive counts).
        labels_lookup: dict slug→display label.

    Returns:
        Plotly Figure — horizontal bars, per-modality colors, Portuguese labels.

    Example:
        >>> fig = build_modality_bar({"tc_geral": 5, "radiografia": 20}, labels)
    """
    display_labels: list[str] = []
    values: list[int] = []
    bar_colors: list[str] = []

    for slug, count in counts.items():
        if count > 0:
            display_labels.append(labels_lookup.get(slug, slug))
            values.append(count)
            bar_colors.append(color_for_modality(slug, modalities))

    if not values:
        display_labels = ["—"]
        values = [0]
        bar_colors = [CHART_COLORS["muted"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=values,
                y=display_labels,
                orientation="h",
                marker=dict(color=bar_colors),
                text=values,
                textposition="outside",
                textfont=dict(size=13),
                hovertemplate="%{y}: %{x} exames<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title=dict(text="Distribuição por Modalidade", font=dict(size=16)),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=30, t=40, b=10),
        xaxis=dict(
            title=None,
            showgrid=True,
            gridcolor=CHART_COLORS["track"],
            fixedrange=True,
        ),
        yaxis=dict(
            title=None,
            categoryorder="total ascending",
            fixedrange=True,
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Modality donut chart (dynamic) — kept for backward compatibility
# ---------------------------------------------------------------------------


def build_modality_donut(
    counts: dict[str, int],
    labels_lookup: dict[str, str],
    modalities: list[dict[str, Any]] | None = None,
) -> go.Figure:
    """
    Build a donut chart showing exam count by modality.

    Args:
        counts: dict slug→count (only positive counts).
        labels_lookup: dict slug→display label.

    Returns:
        Plotly Figure — hole=0.5, per-modality colors, Portuguese labels.
    """
    slugs: list[str] = []
    values: list[int] = []
    display_labels: list[str] = []
    slice_colors: list[str] = []

    for slug, count in counts.items():
        if count > 0:
            slugs.append(slug)
            values.append(count)
            display_labels.append(labels_lookup.get(slug, slug))
            slice_colors.append(color_for_modality(slug, modalities))

    if not values:
        values = [0]
        display_labels = ["—"]
        slice_colors = [CHART_COLORS["muted"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=display_labels,
                values=values,
                hole=0.5,
                marker=dict(colors=slice_colors),
                textinfo="label+percent",
                textfont=dict(size=14),
                sort=False,
            )
        ]
    )

    fig.update_layout(
        title=dict(text="Distribuição por Modalidade", font=dict(size=16)),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.2,
            xanchor="center", x=0.5, font=dict(size=12),
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Daily earnings sparkline (unchanged — works on earnings column)
# ---------------------------------------------------------------------------

def build_daily_sparkline(df: pd.DataFrame) -> go.Figure:
    """
    Build a compact line chart of recent daily earnings.

    Args:
        df: DataFrame with 'date' (ISO str) and 'earnings' (float). Last 1–7 rows.
    """
    if df.empty:
        return go.Figure()

    fill_rgba = hex_to_rgba(CHART_COLORS["primary"], 0.1)

    labels = []
    for d in df["date"]:
        try:
            labels.append(f"{d[8:10]}/{d[5:7]}")
        except (IndexError, TypeError):
            labels.append(str(d))

    fig = go.Figure(
        data=[
            go.Scatter(
                x=labels, y=df["earnings"],
                mode="lines+markers",
                line=dict(color=CHART_COLORS["primary"], width=2),
                marker=dict(size=6, color=CHART_COLORS["primary"]),
                fill="tozeroy", fillcolor=fill_rgba,
                hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title=dict(text="Faturamento — Últimos 7 Dias", font=dict(size=14)),
        height=250,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(title=None, tickfont=dict(size=11), showgrid=False),
        yaxis=dict(
            title=None, tickprefix="R$ ", tickfont=dict(size=11),
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Progress gauge (unchanged)
# ---------------------------------------------------------------------------

def build_progress_gauge(pct_goal: float) -> go.Figure:
    """Build a horizontal progress bar showing monthly goal progress (0–100%)."""
    display_pct = min(pct_goal, 100.0)

    seg1 = min(25.0, display_pct)
    seg2 = max(0.0, min(25.0, display_pct - 25.0))
    seg3 = max(0.0, min(25.0, display_pct - 50.0))
    seg4 = max(0.0, display_pct - 75.0)
    unfilled = max(0.0, 100.0 - display_pct)

    bar_y = ["Meta"]

    fig = go.Figure()

    segments = [
        (seg1, CHART_COLORS["progress_danger"], "0–25%"),
        (seg2, CHART_COLORS["progress_warning"], "25–50%"),
        (seg3, CHART_COLORS["progress_on_track"], "50–75%"),
        (seg4, CHART_COLORS["progress_achieved"], "75–100%"),
    ]
    for val, color, name in segments:
        fig.add_trace(go.Bar(
            x=[val], y=bar_y, orientation="h",
            marker=dict(color=color, line=dict(width=0)),
            name=name, showlegend=False,
            hovertemplate=f"{name}: %{{x:.0f}}%<extra></extra>",
        ))

    fig.add_trace(go.Bar(
        x=[unfilled], y=bar_y, orientation="h",
        marker=dict(color=CHART_COLORS["track"], line=dict(width=0)),
        name="restante", showlegend=False,
    ))

    fig.add_vline(
        x=display_pct, line_width=3,
        line_color=CHART_COLORS["primary"], line_dash="solid",
    )

    fig.add_annotation(
        x=display_pct, y=0,
        text=f"<b>{pct_goal:.0f}%</b>",
        showarrow=False,
        font=dict(size=16, color=get_chart_text_color()),
        xanchor="left", xshift=5,
    )

    fig.update_layout(
        barmode="stack", bargap=0.25, height=130,
        title=dict(text="Progresso da Meta Mensal", font=dict(size=16)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=50),
        xaxis=dict(
            range=[0, 100], ticksuffix="%", tickvals=[0, 25, 50, 75, 100],
            showgrid=False, fixedrange=True,
        ),
        yaxis=dict(showticklabels=False, fixedrange=True),
    )

    return fig


# ---------------------------------------------------------------------------
# Monthly earnings line chart (unchanged)
# ---------------------------------------------------------------------------

def build_monthly_earnings_chart(
    df: pd.DataFrame, daily_target: float, year_month: str
) -> go.Figure:
    """Build a daily earnings line chart for a given month with target line."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    days_in_month = calendar.monthrange(year, month)[1]

    all_dates = pd.date_range(
        start=f"{year_month}-01", periods=days_in_month, freq="D",
    )
    full = pd.DataFrame({
        "date": all_dates.strftime("%Y-%m-%d"),
        "day_number": range(1, days_in_month + 1),
    })

    merged = full.merge(df[["date", "earnings"]], on="date", how="left")
    merged["earnings"] = merged["earnings"].fillna(0.0)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=merged["day_number"], y=merged["earnings"],
        mode="lines+markers",
        line=dict(color=CHART_COLORS["primary"], width=2),
        marker=dict(size=6, color=CHART_COLORS["primary"]),
        name="Faturamento",
        hovertemplate="Dia %{x}: R$ %{y:,.2f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=[1, days_in_month],
        y=[daily_target, daily_target],
        mode="lines",
        line=dict(dash="dash", color=CHART_COLORS["muted"], width=1.5),
        name="Alvo diário",
        hovertemplate="Alvo: R$ %{y:,.2f}<extra></extra>",
    ))

    today = date.today()
    current_ym = today.isoformat()[:7]
    if year_month == current_ym:
        today_day = today.day
        today_row = merged.loc[merged["day_number"] == today_day, "earnings"]
        today_val = float(today_row.iloc[0]) if len(today_row) > 0 else 0.0

        fig.add_vline(
            x=today_day, line_dash="dot",
            line_color=CHART_COLORS["neutral"], line_width=1.5,
        )
        fig.add_annotation(
            x=today_day, y=today_val,
            text="Hoje", showarrow=True, arrowhead=1, ax=20, ay=-30,
            font=dict(size=11, color=get_chart_text_color()),
        )

    fig.update_layout(
        title=dict(
            text=f"{MONTHS_PT.get(month, str(month))}, {year}",
            font=dict(size=16),
        ),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        hovermode="x unified",
        xaxis=dict(
            title=None, tickvals=list(range(1, days_in_month + 1)),
            showgrid=False, fixedrange=True,
        ),
        yaxis=dict(
            title=None, tickprefix="R$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Monthly modality revenue donut (dynamic)
# ---------------------------------------------------------------------------

def build_monthly_modality_donut(
    df: pd.DataFrame,
    active_modalities: list[dict[str, Any]],
) -> go.Figure:
    """
    Build a donut chart showing monthly revenue share by modality.

    Args:
        df: DataFrame from load_month_items() with columns:
            date, modality_slug, count.
        active_modalities: List of active modality dicts with slug, label, price.
    """
    prices = {m["slug"]: float(m["price"]) for m in active_modalities}
    labels_lookup = {m["slug"]: m["label"] for m in active_modalities}

    # Compute revenue per modality
    rev: dict[str, float] = {}
    if not df.empty:
        for _, row in df.iterrows():
            slug = str(row["modality_slug"])
            if slug in prices:
                rev[slug] = rev.get(slug, 0.0) + int(row["count"]) * prices[slug]

    slugs: list[str] = []
    values: list[float] = []
    display_labels: list[str] = []
    slice_colors: list[str] = []

    for m in active_modalities:
        slug = m["slug"]
        val = rev.get(slug, 0.0)
        if val > 0:
            slugs.append(slug)
            values.append(val)
            display_labels.append(labels_lookup.get(slug, slug))
            slice_colors.append(color_for_modality(slug, active_modalities))

    if not values:
        values = [0]
        display_labels = ["—"]
        slice_colors = [CHART_COLORS["muted"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=display_labels, values=values,
                hole=0.4,
                marker=dict(colors=slice_colors),
                textinfo="label+percent",
                textfont=dict(size=14),
                sort=False,
            )
        ]
    )

    if not df.empty and "date" in df.columns:
        _m = int(str(df["date"].iloc[0])[5:7])
        month_name = MONTHS_PT.get(_m, "Mês")
        chart_year = str(df["date"].iloc[0])[:4]
    else:
        month_name = "Mês"
        chart_year = str(date.today().year)

    fig.update_layout(
        title=dict(text=f"{month_name}, {chart_year}", font=dict(size=16)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.2,
            xanchor="center", x=0.5, font=dict(size=12),
        ),
    )

    return fig
