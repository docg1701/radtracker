"""
Analysis-tab chart factory functions — Sprint 4.

Moving averages, week-over-week comparison, and modality mix evolution.
Every function returns a plotly.graph_objects.Figure. No database access.
"""

import calendar

import pandas as pd
import plotly.graph_objects as go

from src.chart_colors import CHART_COLORS, get_chart_text_color, hex_to_rgba
from src.formatting import MONTHS_PT

# ---------------------------------------------------------------------------
# Moving averages line chart (MA7 + MA30)
# ---------------------------------------------------------------------------

def build_moving_averages_chart(
    df: pd.DataFrame, year_month: str
) -> go.Figure:
    """
    Line chart with MA7 (teal solid fill) and MA30 (gray dashed) for one month.

    Args:
        df: DataFrame with 'date', 'ma7', 'ma30' columns.
        year_month: "YYYY-MM" string.
    """
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

    fill_rgba = hex_to_rgba(CHART_COLORS["primary"], 0.1)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=merged["day_number"], y=merged["ma7"],
        mode="lines",
        name="MA7",
        line=dict(color=CHART_COLORS["primary"], width=2),
        fill="tozeroy",
        fillcolor=fill_rgba,
        hovertemplate="MA7 dia %{x}: R$ %{y:,.2f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=merged["day_number"], y=merged["ma30"],
        mode="lines",
        name="MA30",
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
            title=None,
            tickvals=list(range(1, days_in_month + 1)),
            showgrid=False,
            fixedrange=True,
        ),
        yaxis=dict(
            title=None,
            tickprefix="R$ ",
            showgrid=True,
            gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Week-over-week grouped bar chart
# ---------------------------------------------------------------------------

def build_wow_comparison_chart(
    weekly_data: list[dict], prices: dict[str, float]
) -> go.Figure:
    """
    Grouped bar chart: Semana Anterior vs Semana Atual, 3 bars each (RM/TC/RX).

    Revenue = count × price. Previous week bars at 50% opacity.
    Handles single-week edge case gracefully.
    """
    if len(weekly_data) < 2:
        week = weekly_data[0] if weekly_data else {}
        rm_rev = week.get("rm_count", 0) * prices["rm"]
        tc_rev = week.get("tc_count", 0) * prices["tc"]
        rx_rev = week.get("rx_count", 0) * prices["rx"]

        fig = go.Figure(data=[
            go.Bar(
                x=["RM", "TC", "RX"],
                y=[rm_rev, tc_rev, rx_rev],
                marker_color=[CHART_COLORS["rm"], CHART_COLORS["tc"], CHART_COLORS["rx"]],
                name=week.get("week_label", "Semana"),
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

    prev, curr = weekly_data[0], weekly_data[1]

    def _rev(week: dict, mod: str) -> float:
        return float(week.get(f"{mod}_count", 0)) * prices[mod]

    modalities = ["rm", "tc", "rx"]
    labels = ["RM", "TC", "RX"]
    full_colors = [CHART_COLORS[m] for m in modalities]

    prev_colors = [hex_to_rgba(c, 0.5) for c in full_colors]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=[_rev(prev, m) for m in modalities],
        name="Semana Anterior",
        marker_color=prev_colors,
        hovertemplate="%{x}: R$ %{y:,.2f}<extra>Semana Anterior</extra>",
    ))

    fig.add_trace(go.Bar(
        x=labels,
        y=[_rev(curr, m) for m in modalities],
        name="Semana Atual",
        marker_color=full_colors,
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
        yaxis=dict(title=None, tickprefix="R$ ", showgrid=True, gridcolor=CHART_COLORS["track"]),
    )

    return fig


# ---------------------------------------------------------------------------
# Modality mix evolution (stacked area)
# ---------------------------------------------------------------------------

def build_modality_mix_evolution(
    mix_history: dict[str, dict[str, float]]
) -> go.Figure:
    """
    Stacked area chart showing RM/TC/RX revenue share evolution over months.
    Single-month edge case renders a stacked bar instead.
    """
    months_sorted = sorted(mix_history.keys())

    month_labels: list[str] = []
    for ym in months_sorted:
        y, m = int(ym[:4]), int(ym[5:7])
        abbr = MONTHS_PT.get(m, f"M{m}")[:3]
        month_labels.append(f"{abbr}/{y % 100:02d}")

    rm_vals = [mix_history[ym]["rm"] for ym in months_sorted]
    tc_vals = [mix_history[ym]["tc"] for ym in months_sorted]
    rx_vals = [mix_history[ym]["rx"] for ym in months_sorted]

    fig = go.Figure()

    if len(months_sorted) == 1:
        # Single month → vertical stacked bar
        fig.add_trace(go.Bar(
            x=[month_labels[0]], y=[rm_vals[0]],
            name="RM", marker_color=CHART_COLORS["rm"],
        ))
        fig.add_trace(go.Bar(
            x=[month_labels[0]], y=[tc_vals[0]],
            name="TC", marker_color=CHART_COLORS["tc"],
        ))
        fig.add_trace(go.Bar(
            x=[month_labels[0]], y=[rx_vals[0]],
            name="RX", marker_color=CHART_COLORS["rx"],
        ))
        fig.update_layout(barmode="stack")
    else:
        fig.add_trace(go.Scatter(
            x=month_labels, y=rm_vals,
            mode="lines",
            name="RM",
            line=dict(color=CHART_COLORS["rm"], width=1),
            stackgroup="one",
            fillcolor=hex_to_rgba(CHART_COLORS["rm"], 0.7),
            hovertemplate="RM: %{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=month_labels, y=tc_vals,
            mode="lines",
            name="TC",
            line=dict(color=CHART_COLORS["tc"], width=1),
            stackgroup="one",
            fillcolor=hex_to_rgba(CHART_COLORS["tc"], 0.7),
            hovertemplate="TC: %{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=month_labels, y=rx_vals,
            mode="lines",
            name="RX",
            line=dict(color=CHART_COLORS["rx"], width=1),
            stackgroup="one",
            fillcolor=hex_to_rgba(CHART_COLORS["rx"], 0.7),
            hovertemplate="RX: %{y:.1f}%<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="", font=dict(size=16)),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
        xaxis=dict(title=None),
        yaxis=dict(
            title=None,
            ticksuffix="%",
            range=[0, 100],
            showgrid=True,
            gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Monthly earnings bar chart (year overview)
# ---------------------------------------------------------------------------

def build_ytd_earnings_chart(
    df: pd.DataFrame, year_month: str, goal: float, prices: dict[str, float]
) -> go.Figure:
    """
    Bar chart: earnings per month across the entire year to date.

    Each bar = sum of daily earnings for that month.
    Current month highlighted in primary teal, past months in muted.
    Goal line as dashed horizontal reference.
    """
    if df.empty:
        return go.Figure()

    # Aggregate earnings by month
    df = df.copy()
    df["ym"] = df["date"].str[:7]
    monthly = df.groupby("ym", sort=False).agg(
        total_earnings=("earnings", "sum"),
    ).reset_index()
    monthly = monthly.sort_values("ym")

    month_labels: list[str] = []
    for ym in monthly["ym"]:
        y, m = int(ym[:4]), int(ym[5:7])
        abbr = MONTHS_PT.get(m, f"M{m}")[:3]
        month_labels.append(f"{abbr}/{y % 100:02d}")

    colors: list[str] = []
    for ym in monthly["ym"]:
        if ym == year_month:
            colors.append(CHART_COLORS["primary"])
        else:
            colors.append(hex_to_rgba(CHART_COLORS["primary"], 0.35))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=month_labels,
        y=monthly["total_earnings"],
        marker_color=colors,
        hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
        text=[f"R$ {v:,.0f}".replace(",", ".") for v in monthly["total_earnings"]],
        textposition="outside",
        textfont=dict(size=11),
    ))

    # Goal line
    fig.add_hline(
        y=goal, line_dash="dash", line_color=CHART_COLORS["progress_danger"],
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
        yaxis=dict(title=None, tickprefix="R$ ", showgrid=True, gridcolor=CHART_COLORS["track"]),
    )

    return fig
