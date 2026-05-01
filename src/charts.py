"""
Plotly chart factory functions for radtracker.

Every function accepts data as parameters (DataFrame or scalars)
and returns a plotly.graph_objects.Figure. No database access here.
"""

import calendar
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from src.chart_colors import CHART_COLORS, get_chart_text_color, hex_to_rgba
from src.formatting import MONTHS_PT

# ---------------------------------------------------------------------------
# Modality donut chart
# ---------------------------------------------------------------------------

def build_modality_donut(rm: int, tc: int, rx: int) -> go.Figure:
    """
    Build a donut chart showing exam count breakdown by modality.

    Args:
        rm: RM exam count.
        tc: TC exam count.
        rx: RX exam count.

    Returns:
        Plotly Figure with hole=0.5, modality colors, Portuguese labels.

    Edge case: if all counts are zero, renders a donut with 3 zero slices
    (Plotly handles this gracefully — shows an empty ring).
    """
    labels = ["RM", "TC", "RX"]
    values = [rm, tc, rx]
    colors = [CHART_COLORS["rm"], CHART_COLORS["tc"], CHART_COLORS["rx"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textfont=dict(size=14),
                sort=False,  # Preserve RM → TC → RX order
            )
        ]
    )

    fig.update_layout(
        title=dict(
            text="Distribuição por Modalidade",
            font=dict(size=16),
        ),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Daily earnings sparkline (mini trend)
# ---------------------------------------------------------------------------

def build_daily_sparkline(df: pd.DataFrame) -> go.Figure:
    """
    Build a compact line chart showing recent daily earnings.

    Args:
        df: DataFrame with columns 'date' (str, ISO format) and 'earnings' (float).
            Must be sorted by date ascending. Should contain 1–7 rows.

    Returns:
        Plotly Figure — 250px tall, minimal chrome, teal line.

    Edge case: a single-row DataFrame shows a single marker (no line).
    An empty DataFrame returns an empty Figure (no traces).
    """
    if df.empty:
        return go.Figure()

    fill_rgba = hex_to_rgba(CHART_COLORS["primary"], 0.1)

    # Build display labels (DD/MM)
    labels = []
    for d in df["date"]:
        try:
            labels.append(f"{d[8:10]}/{d[5:7]}")  # "DD/MM"
        except (IndexError, TypeError):
            labels.append(str(d))

    fig = go.Figure(
        data=[
            go.Scatter(
                x=labels,
                y=df["earnings"],
                mode="lines+markers",
                line=dict(color=CHART_COLORS["primary"], width=2),
                marker=dict(size=6, color=CHART_COLORS["primary"]),
                fill="tozeroy",
                fillcolor=fill_rgba,
                hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title=dict(
            text="Faturamento — Últimos 7 Dias",
            font=dict(size=14),
        ),
        height=250,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(
            title=None,
            tickfont=dict(size=11),
            showgrid=False,
        ),
        yaxis=dict(
            title=None,
            tickprefix="R$ ",
            tickfont=dict(size=11),
            showgrid=True,
            gridcolor=CHART_COLORS["track"],
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Progress gauge (monthly goal)
# ---------------------------------------------------------------------------

def build_progress_gauge(pct_goal: float) -> go.Figure:
    """
    Build a sleek horizontal progress bar showing monthly goal progress.

    4 milestone segments (red → amber → teal → green) + gray track.
    Current-position indicator as a vertical rule with percentage badge.
    """
    display_pct = min(pct_goal, 100.0)

    seg1 = min(25.0, display_pct)
    seg2 = max(0.0, min(25.0, display_pct - 25.0))
    seg3 = max(0.0, min(25.0, display_pct - 50.0))
    seg4 = max(0.0, display_pct - 75.0)
    unfilled = max(0.0, 100.0 - display_pct)

    bar_y = ["Meta"]

    fig = go.Figure()

    segments = [
        (seg1, CHART_COLORS["progress_danger"],   "0–25%"),
        (seg2, CHART_COLORS["progress_warning"],   "25–50%"),
        (seg3, CHART_COLORS["progress_on_track"],  "50–75%"),
        (seg4, CHART_COLORS["progress_achieved"],  "75–100%"),
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

    # Vertical marker line (primary teal — contrasts with gradient bar)
    marker_color = CHART_COLORS["primary"]
    fig.add_vline(
        x=display_pct, line_width=3,
        line_color=marker_color,
        line_dash="solid",
    )

    # Percentage text inside the bar, just right of the marker (3px)
    fig.add_annotation(
        x=display_pct, y=0,
        text=f"<b>{pct_goal:.0f}%</b>",
        showarrow=False,
        font=dict(size=16, color=get_chart_text_color()),
        xanchor="left",
        xshift=5,
    )

    fig.update_layout(
        barmode="stack",
        bargap=0.25,
        height=130,
        title=dict(
            text="Progresso da Meta Mensal",
            font=dict(size=16),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=50),
        xaxis=dict(
            range=[0, 100],
            ticksuffix="%",
            tickvals=[0, 25, 50, 75, 100],
            showgrid=False,
            fixedrange=True,
        ),
        yaxis=dict(
            showticklabels=False,
            fixedrange=True,
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# Monthly earnings line chart
# ---------------------------------------------------------------------------

def build_monthly_earnings_chart(
    df: pd.DataFrame, daily_target: float, year_month: str
) -> go.Figure:
    """
    Build a daily earnings line chart for a given month.

    Fills missing days with zero earnings. Includes a dashed daily-target
    line and a today vertical marker (current month only).

    Args:
        df: DataFrame with 'date' (ISO str) and 'earnings' (float) columns.
        daily_target: Daily earnings target in R$.
        year_month: "YYYY-MM" string identifying the month.
    """
    year, month = int(year_month[:4]), int(year_month[5:7])
    days_in_month = calendar.monthrange(year, month)[1]

    # Build full date range for the month
    all_dates = pd.date_range(
        start=f"{year_month}-01",
        periods=days_in_month,
        freq="D",
    )
    full = pd.DataFrame({
        "date": all_dates.strftime("%Y-%m-%d"),
        "day_number": range(1, days_in_month + 1),
    })

    # Left-join actual data
    merged = full.merge(df[["date", "earnings"]], on="date", how="left")
    merged["earnings"] = merged["earnings"].fillna(0.0)

    fig = go.Figure()

    # Main earnings line
    fig.add_trace(go.Scatter(
        x=merged["day_number"],
        y=merged["earnings"],
        mode="lines+markers",
        line=dict(color=CHART_COLORS["primary"], width=2),
        marker=dict(size=6, color=CHART_COLORS["primary"]),
        name="Faturamento",
        hovertemplate="Dia %{x}: R$ %{y:,.2f}<extra></extra>",
    ))

    # Daily target line
    fig.add_trace(go.Scatter(
        x=[1, days_in_month],
        y=[daily_target, daily_target],
        mode="lines",
        line=dict(dash="dash", color=CHART_COLORS["muted"], width=1.5),
        name="Alvo diário",
        hovertemplate="Alvo: R$ %{y:,.2f}<extra></extra>",
    ))

    # Today marker (current month only)
    today = date.today()
    current_ym = today.isoformat()[:7]
    if year_month == current_ym:
        today_day = today.day
        today_row = merged.loc[merged["day_number"] == today_day, "earnings"]
        today_val = float(today_row.iloc[0]) if len(today_row) > 0 else 0.0

        fig.add_vline(
            x=today_day,
            line_dash="dot",
            line_color=CHART_COLORS["neutral"],
            line_width=1.5,
        )
        fig.add_annotation(
            x=today_day,
            y=today_val,
            text="Hoje",
            showarrow=True,
            arrowhead=1,
            ax=20,
            ay=-30,
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
# Monthly modality revenue donut
# ---------------------------------------------------------------------------

def build_monthly_modality_donut(
    df: pd.DataFrame, prices: dict[str, float]
) -> go.Figure:
    """
    Build a donut chart showing monthly revenue share by modality.

    Revenue = sum(count) * price per modality, not raw exam counts.
    """
    rm_rev = float(df["rm_count"].sum()) * prices["rm"]
    tc_rev = float(df["tc_count"].sum()) * prices["tc"]
    rx_rev = float(df["rx_count"].sum()) * prices["rx"]

    labels = ["RM", "TC", "RX"]
    values = [rm_rev, tc_rev, rx_rev]
    colors = [CHART_COLORS["rm"], CHART_COLORS["tc"], CHART_COLORS["rx"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textfont=dict(size=14),
                sort=False,
            )
        ]
    )

    # Derive month name from first row's date, or use "Mês" as fallback
    month_name = "Mês"
    if not df.empty and "date" in df.columns:
        _m = int(str(df["date"].iloc[0])[5:7])
        month_name = MONTHS_PT.get(_m, "Mês")
    # Extract year from the date
    chart_year = str(df["date"].iloc[0])[:4] if not df.empty and "date" in df.columns else "2026"

    fig.update_layout(
        title=dict(
            text=f"{month_name}, {chart_year}",
            font=dict(size=16),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
    )

    return fig

