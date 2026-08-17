"""
Analysis-tab chart factory functions — v2 dynamic modalities.

Moving averages, week-over-week comparison, modality mix evolution.
Every function returns a plotly.graph_objects.Figure. No database access.
"""

import calendar
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from src.calculations import revenue_by_slug
from src.chart_colors import (
    CHART_COLORS,
    color_for_modality,
    get_chart_text_color,
    hex_to_rgba,
)
from src.formatting import month_abbr
from src.i18n import translate

# ---------------------------------------------------------------------------
# Moving averages line chart (MA7 + MA30)
# ---------------------------------------------------------------------------

def build_moving_averages_chart(
    df: pd.DataFrame, year_month: str, lang: str = "en",
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
        hovertemplate=translate("web.charts.ma7_hover", lang),
    ))

    fig.add_trace(go.Scatter(
        x=merged["day_number"], y=merged["ma30"],
        mode="lines", name="MA30",
        line=dict(color=CHART_COLORS["muted"], width=1.5, dash="dash"),
        hovertemplate=translate("web.charts.ma30_hover", lang),
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
            title=None, tickprefix="$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Week-over-week grouped bar chart (dynamic)
# ---------------------------------------------------------------------------

def build_wow_comparison_chart(
    items_df: pd.DataFrame,
    active_modalities: list[dict[str, Any]],
    lang: str = "en",
) -> go.Figure:
    """
    Grouped bar chart: current partial week vs last complete week, per modality.

    Shows price-vigent revenue comparison so the user sees real-time progress
    against the previous week. Week labels use actual date ranges.
    """
    today = pd.Timestamp.now().normalize()

    # Current week: Monday .. today (partial)
    current_monday = today - pd.Timedelta(days=today.dayofweek)
    curr_start = current_monday
    curr_end = today

    # Previous complete week: last Monday .. last Sunday
    prev_monday = current_monday - pd.Timedelta(weeks=1)
    prev_sunday = current_monday - pd.Timedelta(days=1)

    prev_by_slug = revenue_by_slug(
        items_df,
        start=prev_monday.strftime("%Y-%m-%d"),
        end=prev_sunday.strftime("%Y-%m-%d"),
    )
    curr_by_slug = revenue_by_slug(
        items_df,
        start=curr_start.strftime("%Y-%m-%d"),
        end=curr_end.strftime("%Y-%m-%d"),
    )

    labels: list[str] = []
    prev_revs: list[float] = []
    curr_revs: list[float] = []
    mod_colors: list[str] = []

    for m in active_modalities:
        slug = m["slug"]
        labels.append(m["label"])
        mod_colors.append(color_for_modality(slug, active_modalities))
        prev_revs.append(prev_by_slug.get(slug, 0.0))
        curr_revs.append(curr_by_slug.get(slug, 0.0))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels, y=prev_revs,
        marker_color=[hex_to_rgba(c, 0.5) for c in mod_colors],
        hovertemplate="%{x}: $ %{y:,.2f}<extra>"
        + translate("web.charts.wow_extra_last", lang)
        + "</extra>",
    ))

    fig.add_trace(go.Bar(
        x=labels, y=curr_revs,
        marker_color=mod_colors,
        hovertemplate="%{x}: $ %{y:,.2f}<extra>"
        + translate("web.charts.wow_extra_this", lang)
        + "</extra>",
    ))

    fig.update_layout(
        title=dict(text="", font=dict(size=16)),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        barmode="group",
        showlegend=False,
        xaxis=dict(title=None),
        yaxis=dict(
            title=None, tickprefix="$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig



# ---------------------------------------------------------------------------
# Modality mix evolution (stacked area - dynamic)
# ---------------------------------------------------------------------------

def build_modality_mix_evolution(
    mix_history: dict[str, dict[str, float]],
    active_modalities: list[dict[str, Any]],
    lang: str = "en",
) -> go.Figure:
    """
    Stacked area chart showing modality revenue share evolution over months.

    Args:
        mix_history: dict month→(slug→pct).
        active_modalities: list of active modality dicts with slug, label.
    """
    months_sorted = sorted(mix_history.keys())

    month_labels = [month_abbr(ym, lang) for ym in months_sorted]

    fig = go.Figure()

    if len(months_sorted) == 1:
        # Single month → stacked bar
        ym = months_sorted[0]
        for m in active_modalities:
            slug = m["slug"]
            val = mix_history[ym].get(slug, 0.0)
            fig.add_trace(go.Bar(
                x=[month_labels[0]], y=[val],
                name=m["label"], marker_color=color_for_modality(slug, active_modalities),
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
                line=dict(color=color_for_modality(slug, active_modalities), width=1),
                stackgroup="one",
                fillcolor=hex_to_rgba(color_for_modality(slug, active_modalities), 0.7),
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
    df: pd.DataFrame, year_month: str, goal: float, lang: str = "en",
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

    month_labels = [month_abbr(ym, lang) for ym in monthly["ym"]]

    colors: list[str] = []
    for ym in monthly["ym"]:
        if ym == year_month:
            colors.append(CHART_COLORS["primary"])
        else:
            colors.append(hex_to_rgba(CHART_COLORS["primary"], 0.35))

    fig = go.Figure()

    bar_text = [f"$ {v:,.0f}" for v in monthly["total_earnings"]]
    if lang == "pt":
        bar_text = [s.replace(",", ".") for s in bar_text]

    goal_text = translate("web.charts.ytd_goal", lang) + f"{goal:,.0f}"
    if lang == "pt":
        goal_text = goal_text.replace(",", ".")

    fig.add_trace(go.Bar(
        x=month_labels, y=monthly["total_earnings"],
        marker_color=colors,
        hovertemplate="%{x}: $ %{y:,.2f}<extra></extra>",
        text=bar_text,
        textposition="outside",
        textfont=dict(size=11),
    ))

    fig.add_hline(
        y=goal, line_dash="dash", line_color=CHART_COLORS["neutral"],
        line_width=1.5,
        annotation=dict(
            text=goal_text,
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
            title=None, tickprefix="$ ",
            showgrid=True, gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig
