"""
Plotly chart factory functions for radtracker.

Every function accepts data as parameters (DataFrame or scalars)
and returns a plotly.graph_objects.Figure. No database access here.
"""

import pandas as pd
import plotly.graph_objects as go

from src.chart_colors import CHART_COLORS


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
        Plotly Figure with hole=0.4, modality colors, Portuguese labels.

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
                hole=0.4,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textfont=dict(size=14),
                sort=False,  # Preserve RM → TC → RX order
            )
        ]
    )

    fig.update_layout(
        title=dict(
            text="Distribuição por Modalidade — Hoje",
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

    # Derive fill color from primary hex with 10% opacity (computed once)
    primary_hex = CHART_COLORS["primary"].lstrip("#")
    r, g, b = int(primary_hex[0:2], 16), int(primary_hex[2:4], 16), int(primary_hex[4:6], 16)
    fill_rgba = f"rgba({r}, {g}, {b}, 0.1)"

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
            gridcolor="#E2E8F0",
        ),
    )

    return fig
