"""
Analysis-tab chart factory functions — v2 dynamic modalities.

Moving averages, week-over-week comparison, modality mix evolution.
Every function returns a plotly.graph_objects.Figure. No database access.
"""

import calendar
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
# Moving averages line chart (MA7 + MA30)
# ---------------------------------------------------------------------------

def build_moving_averages_chart(
    df: pd.DataFrame, year_month: str
) -> go.Figure:
    """Line chart with MA7 and MA30 for one month."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    days_in_month = calendar.monthrange(year, month)[1]

    all_dates = pd.date_range(
        start=f"{year_month}-01", periods=days_in_month, freq="D"
    )
    full = pd.DataFrame({
        "date": all_dates.strftime("%Y-%m-%d"),
        "day_number": range(1, days_in_month + 1),
    })
    month_data = df[df["date"].str[:7] == year_month]
    merged = full.merge(
        month_data[["date", "ma7", "ma30"]], on="date", how="left"
    )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=merged["day_number"], y=merged["ma7"],
        mode="lines", name="MA7",
        line=dict(color=CHART_COLORS["primary"], width=2),
        fill="tozeroy",
        fillcolor=hex_to_rgba(CHART_COLORS["primary"], 0.1),
        hovertemplate="MA7 dia %{x}: R$ %{y:,.2f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=merged["day_number"], y=merged["ma30"],
        mode="lines", name="MA30",
        line=dict(color=CHART_COLORS["muted"], width=1.5, dash="dash"),
        hovertemplate="MA30 dia %{x}: R$ %{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="", font=dict(size=16)),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
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
# Week-over-week grouped bar chart (dynamic)
# ---------------------------------------------------------------------------

def build_wow_comparison_chart(
    weekly_data: list[dict],
    df: pd.DataFrame,
    active_modalities: list[dict[str, Any]],
) -> go.Figure:
    """
    Grouped bar chart: Semana Anterior vs Semana Atual, per modality revenue.

    Revenue is computed from the full df since weekly_data from
    compute_historical_stats v2 only has total_earnings.
    """
    if len(weekly_data) < 2:
        # Single week: show current week per modality
        if weekly_data:
            return _single_week_chart(df, active_modalities)
        return go.Figure()

    # Build date ranges for each week
    labels: list[str] = []
    prev_revs: list[float] = []
    curr_revs: list[float] = []
    mod_colors: list[str] = []

    for m in active_modalities:
        slug = m["slug"]
        labels.append(m["label"])
        mod_colors.append(color_for_modality(slug))
        price = float(m["price"])

        # Revenue for this modality in previous week and current week
        prev_rev = _weekly_modality_revenue(df, slug, price, -2)
        curr_rev = _weekly_modality_revenue(df, slug, price, -1)
        prev_revs.append(prev_rev)
        curr_revs.append(curr_rev)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels, y=prev_revs, name="Semana Anterior",
        marker_color=[hex_to_rgba(c, 0.5) for c in mod_colors],
        hovertemplate="%{x}: R$ %{y:,.2f}<extra>Semana Anterior</extra>",
    ))

    fig.add_trace(go.Bar(
        x=labels, y=curr_revs, name="Semana Atual",
        marker_color=mod_colors,
        hovertemplate="%{x}: R$ %{y:,.2f}<extra>Semana Atual</extra>",
    ))

    fig.update_layout(
        title=dict(text="", font=dict(size=16)),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        barmode="group",
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
        xaxis=dict(title=None),
        yaxis=dict(
            title=None, tickprefix="R$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


def _weekly_modality_revenue(
    df: pd.DataFrame, slug: str, price: float, week_offset: int,
) -> float:
    """Sum revenue for a modality in the N-th last complete week.

    week_offset: -1 = most recent complete week, -2 = week before that.
    Falls back to all data for current partial week if not enough weeks.
    """
    if df.empty or "date_dt" not in df.columns:
        return 0.0

    # Get week boundaries
    today = pd.Timestamp.now().normalize()
    # Last complete week: Monday to Sunday before this week
    current_weekday = today.dayofweek  # Monday=0
    last_sunday = today - pd.Timedelta(days=current_weekday + 1)
    last_monday = last_sunday - pd.Timedelta(days=6)

    # Shift back by week_offset
    start = last_monday + pd.Timedelta(weeks=week_offset)
    end = start + pd.Timedelta(days=6)

    week_df = df[
        (df["date_dt"] >= pd.Timestamp(start))
        & (df["date_dt"] <= pd.Timestamp(end))
    ]

    count_col = slug
    if count_col in week_df.columns:
        return float(week_df[count_col].sum()) * price
    return 0.0


def _single_week_chart(
    df: pd.DataFrame,
    active_modalities: list[dict[str, Any]],
) -> go.Figure:
    """Single-week bar chart per modality."""
    labels: list[str] = []
    revs: list[float] = []
    mod_colors: list[str] = []

    for m in active_modalities:
        slug = m["slug"]
        price = float(m["price"])
        labels.append(m["label"])
        mod_colors.append(color_for_modality(slug))

        count_col = slug
        if count_col in df.columns:
            revs.append(float(df[count_col].sum()) * price)
        else:
            revs.append(0.0)

    fig = go.Figure(data=[
        go.Bar(
            x=labels, y=revs, marker_color=mod_colors,
            name="Semana Atual",
            hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
        )
    ])
    fig.update_layout(
        title=dict(text="", font=dict(size=14)),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        yaxis=dict(
            title=None, tickprefix="R$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
        xaxis=dict(title=None),
    )
    return fig


# ---------------------------------------------------------------------------
# Modality mix evolution (stacked area - dynamic)
# ---------------------------------------------------------------------------

def build_modality_mix_evolution(
    mix_history: dict[str, dict[str, float]],
    active_modalities: list[dict[str, Any]],
) -> go.Figure:
    """
    Stacked area chart showing modality revenue share evolution over months.

    Args:
        mix_history: dict month→(slug→pct).
        active_modalities: list of active modality dicts with slug, label.
    """
    months_sorted = sorted(mix_history.keys())

    month_labels: list[str] = []
    for ym in months_sorted:
        y, month_num = int(ym[:4]), int(ym[5:7])
        abbr = MONTHS_PT.get(month_num, f"M{month_num}")[:3]
        month_labels.append(f"{abbr}/{y % 100:02d}")

    fig = go.Figure()

    if len(months_sorted) == 1:
        # Single month → stacked bar
        ym = months_sorted[0]
        for m in active_modalities:
            slug = m["slug"]
            val = mix_history[ym].get(slug, 0.0)
            fig.add_trace(go.Bar(
                x=[month_labels[0]], y=[val],
                name=m["label"], marker_color=color_for_modality(slug),
            ))
        fig.update_layout(barmode="stack")
    else:
        for m in active_modalities:
            slug = m["slug"]
            vals = [mix_history[ym].get(slug, 0.0) for ym in months_sorted]
            fig.add_trace(go.Scatter(
                x=month_labels, y=vals,
                mode="lines",
                name=m["label"],
                line=dict(color=color_for_modality(slug), width=1),
                stackgroup="one",
                fillcolor=hex_to_rgba(color_for_modality(slug), 0.7),
                hovertemplate=f"{m['label']}: %{{y:.1f}}%<extra></extra>",
            ))

    fig.update_layout(
        title=dict(text="", font=dict(size=16)),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=50),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
        xaxis=dict(title=None),
        yaxis=dict(
            title=None, ticksuffix="%", range=[0, 100],
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Monthly earnings bar chart (year overview - unchanged)
# ---------------------------------------------------------------------------

def build_ytd_earnings_chart(
    df: pd.DataFrame, year_month: str, goal: float
) -> go.Figure:
    """Bar chart: earnings per month across the year to date."""
    if df.empty:
        return go.Figure()

    df = df.copy()
    df["ym"] = df["date"].str[:7]
    monthly = df.groupby("ym", sort=False).agg(
        total_earnings=("earnings", "sum"),
    ).reset_index()
    monthly = monthly.sort_values("ym")

    month_labels: list[str] = []
    for ym in monthly["ym"]:
        y, month_num = int(ym[:4]), int(ym[5:7])
        abbr = MONTHS_PT.get(month_num, f"M{month_num}")[:3]
        month_labels.append(f"{abbr}/{y % 100:02d}")

    colors: list[str] = []
    for ym in monthly["ym"]:
        if ym == year_month:
            colors.append(CHART_COLORS["primary"])
        else:
            colors.append(hex_to_rgba(CHART_COLORS["primary"], 0.35))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=month_labels, y=monthly["total_earnings"],
        marker_color=colors,
        hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
        text=[f"R$ {v:,.0f}".replace(",", ".") for v in monthly["total_earnings"]],
        textposition="outside",
        textfont=dict(size=11),
    ))

    fig.add_hline(
        y=goal, line_dash="dash", line_color=CHART_COLORS["neutral"],
        line_width=1.5,
        annotation=dict(
            text=f"Meta: R$ {goal:,.0f}".replace(",", "."),
            font=dict(size=11, color=get_chart_text_color()),
        ),
    )

    fig.update_layout(
        title=dict(text="", font=dict(size=16)),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(
            title=None, tickprefix="R$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig
