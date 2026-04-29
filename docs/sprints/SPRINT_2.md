# Sprint 2 — "Hoje" Tab

**Sprint**: 2 of 6
**Goal**: Today's KPI cards, modality breakdown, estimated hours. The core dashboard comes alive.
**Estimated duration**: 3–4 hours
**Depends on**: Sprint 1 (app starts, sidebar saves data, 3 SQLite tables exist)
**Source documents**: [BRIEF.md](../BRIEF.md), [DESIGN_SPEC.md](../DESIGN_SPEC.md), [PLAN.md](../PLAN.md)

---

## Current State (End of Sprint 1)

The following files exist and must NOT be broken:

| File | Contents | Sprint 2 Relevance |
|---|---|---|
| `app.py` | Entry point. `st.set_page_config`, `init_db`, `render_sidebar`, 4 placeholder tabs | Will replace `tab_hoje` stub at line ~32 |
| `src/db.py` | 9 functions: `get_connection`, `init_db`, `upsert_daily`, `load_daily`, `load_month`, `load_prices`, `save_prices`, `load_goal`, `save_goal` | Will add `load_settings()` convenience; all others used as-is |
| `src/chart_colors.py` | `CHART_COLORS` dict with 13 entries | Imported by new `src/charts.py` |
| `src/ui/sidebar.py` | `render_sidebar(conn)` — date picker, 3 inputs, save button, toast | Unchanged; provides data that Hoje tab reads |
| `.streamlit/config.toml` | Light + dark theme | Unchanged |

Key facts about existing functions:
- `load_daily(conn, date_str)` returns `dict | None`. The dict has keys: `date`, `rm_count`, `tc_count`, `rx_count`, `created_at`, `updated_at`.
- `load_month(conn, year_month)` returns `pd.DataFrame` with same columns.
- `load_prices(conn)` returns `{"rm": 35.0, "tc": 25.0, "rx": 4.5}` (falls back to defaults).
- `load_goal(conn, year_month)` returns `float` (falls back to 45000.0).
- The database module uses both `conn.query()` (for SELECTs) and `conn.connect()` with `sa.text()` (for INSERT/UPDATE/DELETE). **Important**: the `conn.query()` call returns a DataFrame via Streamlit's SQLConnection API — SQLAlchemy is used in `init_db` for DDL but the query path is Streamlit-native.

---

## 1. Pre-flight Checklist

Verify Sprint 1 is complete before starting:

```bash
# 1. App starts without errors
cd /home/galvani/dev/radtracker
source venv/bin/activate
streamlit run app.py --server.headless true &
# Wait 3 seconds, then:
curl -s http://localhost:8501 | head -20
# Kill the server after verification

# 2. Verify data persistence works
sqlite3 data/telerrad.db ".tables"
# Expected: daily_production  exam_prices  monthly_goals

# 3. Verify module imports
python -c "
from src.db import get_connection, init_db, upsert_daily, load_daily, load_month, load_prices, load_goal
from src.chart_colors import CHART_COLORS
print('All imports OK')
print(f'CHART_COLORS has {len(CHART_COLORS)} entries')
"

# 4. Verify the Hoje tab stub exists in app.py
grep "tab_hoje" app.py
# Expected: matches for tab_hoje and the stub content

# 5. If you have existing data, note it
sqlite3 data/telerrad.db "SELECT date, rm_count, tc_count, rx_count FROM daily_production ORDER BY date DESC LIMIT 5;"
```

---

## 2. Task-by-Task Breakdown

Execute in order. After each task, run the verification command before moving on.

---

### Task 2.1 — Create `src/calculations.py` (40 min)

This file contains pure computation functions and database-dependent stats functions. It is the business-logic heart of the app.

Create `/home/galvani/dev/radtracker/src/calculations.py`:

```python
"""
Business-logic calculations for radtracker.

Pure functions for earnings, hours, projections, and moving averages.
DB-dependent functions accept a Streamlit connection as first parameter.

Business rules (from BRIEF.md):
  - RM pays R$35.00/exam, TC pays R$25.00/exam, RX pays R$4.50/exam
  - Productivity midpoints: RM 7.5/h, TC 7.5/h, RX 75/h
  - Work days: Monday–Saturday
  - Monthly goal default: R$45,000
"""

import math
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.db import load_daily

# Productivity midpoints (exams/hour) — used for hour estimation
PRODUCTIVITY: dict[str, float] = {
    "rm": 7.5,
    "tc": 7.5,
    "rx": 75.0,
}

# Default work start time for time-range display
WORK_START_HOUR: int = 8
WORK_START_MINUTE: int = 0


# ---------------------------------------------------------------------------
# Pure functions (no DB access)
# ---------------------------------------------------------------------------

def compute_earnings(
    rm: int, tc: int, rx: int, prices: dict[str, float]
) -> float:
    """
    Calculate total earnings from exam counts and prices.

    Example:
        >>> compute_earnings(8, 6, 35, {"rm": 35.0, "tc": 25.0, "rx": 4.5})
        587.5
    """
    return float(rm * prices["rm"] + tc * prices["tc"] + rx * prices["rx"])


def estimate_hours(rm: int, tc: int, rx: int) -> float:
    """
    Estimate work hours based on productivity midpoints.

    RM midpoint = 7.5 exams/h, TC = 7.5 exams/h, RX = 75 exams/h.

    Example:
        >>> estimate_hours(15, 15, 150)
        6.0
    """
    hours = 0.0
    for modality, count in [("rm", rm), ("tc", tc), ("rx", rx)]:
        if PRODUCTIVITY[modality] > 0:
            hours += count / PRODUCTIVITY[modality]
    return round(hours, 2)


def format_time_range(hours: float) -> str:
    """
    Return a human-readable time range string assuming work starts at 08:00.

    Example:
        >>> format_time_range(5.2)
        '~08:00 – 13:12'
        >>> format_time_range(0.0)
        '~08:00 – 08:00'
    """
    start_minutes = WORK_START_HOUR * 60 + WORK_START_MINUTE
    end_minutes = start_minutes + round(hours * 60)
    end_h = (end_minutes // 60) % 24
    end_m = end_minutes % 60
    return f"~08:00 – {end_h:02d}:{end_m:02d}"


def compute_delta_pct(today: float, yesterday: float | None) -> float | None:
    """
    Compute percentage change vs yesterday.

    Returns None if yesterday is None or zero (avoids division by zero).
    Positive = today is higher.

    Example:
        >>> compute_delta_pct(600.0, 500.0)
        20.0
        >>> compute_delta_pct(400.0, 500.0)
        -20.0
        >>> compute_delta_pct(600.0, None) is None
        True
        >>> compute_delta_pct(600.0, 0.0) is None
        True
    """
    if yesterday is None or yesterday == 0.0:
        return None
    return round(((today - yesterday) / yesterday) * 100, 1)


def compute_mtd_earnings(
    month_df: pd.DataFrame, prices: dict[str, float]
) -> float:
    """
    Sum earnings across all rows in a month DataFrame.

    The DataFrame must have columns: rm_count, tc_count, rx_count.
    Returns 0.0 for an empty DataFrame.

    Example:
        >>> df = pd.DataFrame([{"rm_count": 1, "tc_count": 0, "rx_count": 0}])
        >>> compute_mtd_earnings(df, {"rm": 35.0, "tc": 25.0, "rx": 4.5})
        35.0
    """
    if month_df.empty:
        return 0.0
    return float(
        month_df["rm_count"].sum() * prices["rm"]
        + month_df["tc_count"].sum() * prices["tc"]
        + month_df["rx_count"].sum() * prices["rx"]
    )


def add_earnings_column(
    df: pd.DataFrame, prices: dict[str, float]
) -> pd.DataFrame:
    """
    Return a copy of the DataFrame with an 'earnings' column added.

    Each row: earnings = rm_count*rm_price + tc_count*tc_price + rx_count*rx_price.

    Example:
        >>> df = pd.DataFrame([{"rm_count": 2, "tc_count": 0, "rx_count": 0, "date": "2026-04-29"}])
        >>> add_earnings_column(df, {"rm": 35.0, "tc": 25.0, "rx": 4.5})["earnings"].iloc[0]
        70.0
    """
    df = df.copy()
    df["earnings"] = (
        df["rm_count"] * prices["rm"]
        + df["tc_count"] * prices["tc"]
        + df["rx_count"] * prices["rx"]
    )
    return df


# ---------------------------------------------------------------------------
# DB-dependent stats functions
# ---------------------------------------------------------------------------

def compute_daily_stats(
    conn: Any, date_str: str, prices: dict[str, float]
) -> dict[str, Any]:
    """
    Compute all statistics needed for the "Hoje" tab.

    Args:
        conn: Streamlit SQL connection.
        date_str: ISO-format date string (e.g. "2026-04-29").
        prices: Dict with keys "rm", "tc", "rx" and float values.

    Returns:
        dict with keys:
          - earnings_today: float — total R$ for the day
          - exam_count_today: int — total exams (RM+TC+RX)
          - rm_count: int
          - tc_count: int
          - rx_count: int
          - estimated_hours: float — decimal hours
          - estimated_time_range: str — "~08:00 – HH:MM"
          - yesterday_earnings: float | None — yesterday's earnings (None if no data)
          - delta_pct: float | None — % change vs yesterday (None if no basis)

    If no data exists for the given date_str, returns a dict with all
    counts and earnings set to zero, hours set to 0.0, and delta_pct=None.
    """
    today_data = load_daily(conn, date_str)

    if today_data is None:
        return {
            "earnings_today": 0.0,
            "exam_count_today": 0,
            "rm_count": 0,
            "tc_count": 0,
            "rx_count": 0,
            "estimated_hours": 0.0,
            "estimated_time_range": format_time_range(0.0),
            "yesterday_earnings": None,
            "delta_pct": None,
        }

    rm = int(today_data["rm_count"])
    tc = int(today_data["tc_count"])
    rx = int(today_data["rx_count"])

    earnings_today = compute_earnings(rm, tc, rx, prices)
    hours = estimate_hours(rm, tc, rx)
    time_range = format_time_range(hours)

    # Yesterday's earnings
    yesterday_str = _yesterday_str(date_str)
    yesterday_data = load_daily(conn, yesterday_str)
    yesterday_earnings: float | None = None
    if yesterday_data is not None:
        yesterday_earnings = compute_earnings(
            int(yesterday_data["rm_count"]),
            int(yesterday_data["tc_count"]),
            int(yesterday_data["rx_count"]),
            prices,
        )

    delta_pct = compute_delta_pct(earnings_today, yesterday_earnings)

    return {
        "earnings_today": earnings_today,
        "exam_count_today": rm + tc + rx,
        "rm_count": rm,
        "tc_count": tc,
        "rx_count": rx,
        "estimated_hours": hours,
        "estimated_time_range": time_range,
        "yesterday_earnings": yesterday_earnings,
        "delta_pct": delta_pct,
    }


def _yesterday_str(date_str: str) -> str:
    """Return ISO string for the day before date_str."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
```

**Design decisions explained**:
1. `compute_daily_stats` calls `load_daily` internally — this is intentional for Sprint 2. In later sprints we may refactor to pass DataFrames if testing demands it, but the signature `(conn, date_str, prices)` is what PLAN.md specifies.
2. `compute_earnings`, `estimate_hours`, `format_time_range`, `compute_delta_pct`, `compute_mtd_earnings`, `add_earnings_column` are all pure functions — easy to unit test.
3. When there is no data for today, `compute_daily_stats` returns zeros rather than None — this allows the UI to show zero-state KPIs instead of crashing.
4. `_yesterday_str` is a private helper. Keep it simple — literal calendar yesterday. Sunday/weekend awareness is a Phase 3+ refinement.

#### Verification (Task 2.1)

```bash
# Syntax check
python -c "import ast; ast.parse(open('src/calculations.py').read()); print('Syntax OK')"

# Pure function smoke tests
python -c "
from src.calculations import compute_earnings, estimate_hours, format_time_range, compute_delta_pct
assert compute_earnings(8, 6, 35, {'rm':35,'tc':25,'rx':4.5}) == 587.5
assert estimate_hours(15, 15, 150) == 6.0
assert '13:12' in format_time_range(5.2)
assert compute_delta_pct(600, 500) == 20.0
assert compute_delta_pct(400, 500) == -20.0
assert compute_delta_pct(600, None) is None
assert compute_delta_pct(600, 0.0) is None
print('All pure function tests passed')
"

# Verify all expected functions exist
grep "^def " src/calculations.py
# Must show: compute_earnings, estimate_hours, format_time_range, compute_delta_pct,
#            compute_mtd_earnings, add_earnings_column, compute_daily_stats
```

---

### Task 2.2 — Add `load_settings()` to `src/db.py` (10 min)

Add a convenience function that bundles `load_prices` and `load_goal` into one call. This reduces boilerplate in UI modules.

Open `/home/galvani/dev/radtracker/src/db.py` and add this function **after the existing `save_goal` function** (at the end of the file):

```python
def load_settings(conn: Any, year_month: str) -> dict:
    """Return current prices and monthly goal as a convenience dict.

    Calls load_prices() and load_goal() internally.
    Use this in UI modules that need both at once.

    Args:
        conn: Streamlit SQL connection.
        year_month: e.g. "2026-04".

    Returns:
        dict with keys:
          - prices: {"rm": float, "tc": float, "rx": float}
          - monthly_goal: float
    """
    return {
        "prices": load_prices(conn),
        "monthly_goal": load_goal(conn, year_month),
    }
```

**Important**: Add this function at the end of the file — after `save_goal`. Do NOT modify any existing functions.

#### Verification (Task 2.2)

```bash
# Check the function exists
grep "def load_settings" src/db.py
# Expected: 1 match

# Verify existing functions are unchanged
grep "^def " src/db.py
# Expected: get_connection, init_db, upsert_daily, load_daily, load_month,
#           load_prices, save_prices, load_goal, save_goal, load_settings

# Syntax check
python -c "import ast; ast.parse(open('src/db.py').read()); print('Syntax OK')"

# Import check
python -c "from src.db import load_settings; print('Import OK')"
```

---

### Task 2.3 — Update `calculations.py` to Use Actual Prices (5 min)

**No code changes needed.** Task 2.1 already accepts `prices` as a parameter — it uses the prices dict passed by the caller. This satisfies the PLAN.md requirement that `calculations.py` uses actual prices from the database.

The caller (`today.py`) is responsible for loading prices via `load_prices()` or `load_settings()` and passing them to `compute_daily_stats()`.

If the `exam_prices` table is empty, `load_prices()` returns defaults (RM=35, TC=25, RX=4.5) — so the app works even without configured prices.

#### Verification (Task 2.3)

```bash
# Verify compute_daily_stats accepts prices parameter
grep "def compute_daily_stats" src/calculations.py
# Must show: def compute_daily_stats(conn: Any, date_str: str, prices: dict[str, float]) -> dict[str, Any]:
```

---

### Task 2.4 — Create `src/charts.py` — Modality Donut Chart (25 min)

Create `/home/galvani/dev/radtracker/src/charts.py`:

```python
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
                textfont=dict(size=14, color=CHART_COLORS["neutral"]),
                sort=False,  # Preserve RM → TC → RX order
            )
        ]
    )

    fig.update_layout(
        title=dict(
            text="Distribuição por Modalidade — Hoje",
            font=dict(size=16, color="#0F172A"),
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
```

**Design notes**:
- `hole=0.4` per DESIGN_SPEC §4.5.
- `sort=False` preserves the RM→TC→RX order (important — Plotly sorts alphabetically by default, which would put "RM", "RX", "TC").
- `paper_bgcolor="rgba(0,0,0,0)"` ensures theme compatibility (transparent background).
- Legend moved below chart to avoid overlap with slices.

#### Verification (Task 2.4)

```bash
# Syntax check
python -c "import ast; ast.parse(open('src/charts.py').read()); print('Syntax OK')"

# Build a test figure
python -c "
from src.charts import build_modality_donut
fig = build_modality_donut(8, 6, 35)
assert fig is not None
assert len(fig.data) == 1
assert fig.data[0].hole == 0.4
print('Donut chart created OK')
"

# Zero-state test
python -c "
from src.charts import build_modality_donut
fig = build_modality_donut(0, 0, 0)
print('Zero-state donut OK')
"
```

---

### Task 2.5 — Create `src/charts.py` — Daily Sparkline (20 min)

Append this function to the **end** of the existing `/home/galvani/dev/radtracker/src/charts.py` (after `build_modality_donut`):

```python
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
    Empty DataFrame is not expected — caller must guard.
    """
    if df.empty:
        df = pd.DataFrame([{"date": "—", "earnings": 0.0}])

    # Build display labels (DD/MM)
    labels = []
    for d in df["date"]:
        try:
            labels.append(f"{d[8:10]}/{d[5:7]}")  # "DD/MM"
        except (IndexError, TypeError):
            labels.append(str(d))

        # Derive fill color from primary hex with 10% opacity
        primary_hex = CHART_COLORS["primary"].lstrip("#")
        r, g, b = int(primary_hex[0:2], 16), int(primary_hex[2:4], 16), int(primary_hex[4:6], 16)
        fill_rgba = f"rgba({r}, {g}, {b}, 0.1)"

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
            font=dict(size=14, color="#0F172A"),
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
```

**Design notes**:
- Height 250px — compact "sparkline" style per DESIGN_SPEC §4.5.
- `fill="tozeroy"` at 10% primary opacity gives a subtle area effect.
- X-axis uses DD/MM labels (short, readable).
- `hovertemplate` shows formatted currency on hover.

#### Verification (Task 2.5)

```bash
# Syntax check
python -c "import ast; ast.parse(open('src/charts.py').read()); print('Syntax OK')"

# Build a test sparkline
python -c "
import pandas as pd
from src.charts import build_daily_sparkline
df = pd.DataFrame([
    {'date': '2026-04-23', 'earnings': 500.0},
    {'date': '2026-04-24', 'earnings': 600.0},
    {'date': '2026-04-25', 'earnings': 550.0},
])
fig = build_daily_sparkline(df)
assert fig is not None
assert fig.layout.height == 250
print('Sparkline chart created OK')
"

# Verify both functions are in charts.py
grep "^def " src/charts.py
# Expected: build_modality_donut, build_daily_sparkline
```

---

### Task 2.6 — Create `src/ui/today.py` (50 min)

This is the main UI module for Sprint 2. It renders the Hoje tab with 4 KPI cards, the modality donut, the sparkline, and an empty state.

Create `/home/galvani/dev/radtracker/src/ui/today.py`:

```python
"""
Today tab — KPI cards, modality donut, and sparkline.

Renders the "Hoje" tab per DESIGN_SPEC §4.1, §4.1a, §4.5, §4.6.
"""

import math
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from src.calculations import (
    compute_daily_stats,
    compute_mtd_earnings,
    add_earnings_column,
)
from src.charts import build_modality_donut, build_daily_sparkline
from src.chart_colors import CHART_COLORS
from src.db import load_month, load_prices, load_goal


def render_today_tab(conn: Any) -> None:
    """
    Render the complete "Hoje" tab: KPI row, donut chart, sparkline.

    Displays an empty-state card when no data exists for today.
    """
    today = date.today()
    today_str = today.isoformat()
    year_month = today_str[:7]  # "2026-04"

    # Load settings
    prices = load_prices(conn)
    monthly_goal = load_goal(conn, year_month)

    # Compute daily stats
    stats = compute_daily_stats(conn, today_str, prices)

    # Empty state: no data for today AND all counts are zero
    if stats["exam_count_today"] == 0:
        _render_empty_state()
        return

    # ── KPI Row ──
    _render_kpi_row(stats, prices, monthly_goal, conn, year_month)

    # ── Modality Donut ──
    donut = build_modality_donut(
        stats["rm_count"], stats["tc_count"], stats["rx_count"]
    )
    st.plotly_chart(donut, use_container_width=True)

    # ── Sparkline (7-day trend) ──
    _render_sparkline(conn, prices, today_str, year_month)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _render_empty_state() -> None:
    """Render the friendly empty-state card per DESIGN_SPEC §4.6."""
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown(
                '<div style="text-align:center;font-size:64px;">📋</div>',
                unsafe_allow_html=True,
            )
            st.subheader("Nenhum registro ainda")
            st.markdown(
                "Comece registrando sua produção de hoje "
                "na **barra lateral** →"
            )
            st.caption("Os dados aparecerão aqui assim que você salvar.")


def _render_kpi_row(
    stats: dict,
    prices: dict[str, float],
    monthly_goal: float,
    conn,
    year_month: str,
) -> None:
    """Render the 4 KPI metric cards in st.columns(4)."""
    k1, k2, k3, k4 = st.columns(4)

    # ── Card 1: Faturamento Hoje ──
    with k1:
        earnings = stats["earnings_today"]
        if stats["delta_pct"] is not None:
            delta_str = f"{stats['delta_pct']:+.1f}% vs ontem"
            delta_color = "normal"  # green for positive, red for negative
        else:
            delta_str = "— sem dados de ontem"
            delta_color = "off"

        st.metric(
            label="💰 Faturamento hoje",
            value=_fmt_brl(earnings),
            delta=delta_str,
            delta_color=delta_color,
        )

    # ── Card 2: Exames Hoje ──
    with k2:
        total = stats["exam_count_today"]
        pills = _build_pill_indicators(
            stats["rm_count"], stats["tc_count"], stats["rx_count"]
        )
        st.metric(
            label="📋 Exames hoje",
            value=str(total),
            delta=pills,
            delta_color="off",
        )

    # ── Card 3: Horas Estimadas ──
    with k3:
        hours = stats["estimated_hours"]
        time_range = stats["estimated_time_range"]
        st.metric(
            label="⏱️ Horas estimadas",
            value=f"{hours:.1f}h",
            delta=time_range,
            delta_color="off",
        )

    # ── Card 4: Meta Mensal ──
    with k4:
        month_df = load_month(conn, year_month)
        mtd = compute_mtd_earnings(month_df, prices)
        pct = (mtd / monthly_goal * 100) if monthly_goal > 0 else 0.0
        st.metric(
            label="🎯 Meta mensal",
            value=f"{pct:.0f}%",
            delta=f"{_fmt_brl(mtd)} / {_fmt_brl(monthly_goal)}",
            delta_color="off",
        )


def _render_sparkline(
    conn, prices: dict[str, float], today_str: str, year_month: str
) -> None:
    """Load recent 7 days and render the sparkline chart."""
    current_df = load_month(conn, year_month)

    # If early in the month (<7 days), pull from previous month too
    if len(current_df) < 7:
        y, m = int(year_month[:4]), int(year_month[5:7])
        if m == 1:
            prev_ym = f"{y - 1}-12"
        else:
            prev_ym = f"{y}-{m - 1:02d}"
        prev_df = load_month(conn, prev_ym)
        all_days = pd.concat([prev_df, current_df], ignore_index=True)
    else:
        all_days = current_df

    if all_days.empty:
        return

    # Compute earnings per day, keep last 7
    all_days = add_earnings_column(all_days, prices)
    all_days = all_days.sort_values("date").tail(7)

    if len(all_days) >= 2:
        spark = build_daily_sparkline(all_days)
        st.plotly_chart(spark, use_container_width=True)


def _build_pill_indicators(rm: int, tc: int, rx: int) -> str:
    """
    Build modality-colored pill indicators as an HTML string.

    Per DESIGN_SPEC §4.1a: "RM ● 8 · TC ● 10 · RX ● 6"
    Each dot is colored with the modality's chart color.

    Returns a string usable as st.metric's delta (rendered as markdown).
    """
    rm_color = CHART_COLORS["rm"]
    tc_color = CHART_COLORS["tc"]
    rx_color = CHART_COLORS["rx"]

    return (
        f'<span style="color:{rm_color}">●</span> RM {rm}'
        f' &nbsp;·&nbsp; '
        f'<span style="color:{tc_color}">●</span> TC {tc}'
        f' &nbsp;·&nbsp; '
        f'<span style="color:{rx_color}">●</span> RX {rx}'
    )


def _fmt_brl(value: float) -> str:
    """
    Format a float as Brazilian Real currency.

    Example:
        >>> _fmt_brl(1250.0)
        'R$ 1.250,00'
        >>> _fmt_brl(0.0)
        'R$ 0,00'
    """
    if value >= 0:
        # Brazilian locale: thousands=".", decimal=","
        integer_part = math.floor(abs(value))
        decimal_part = round((abs(value) - integer_part) * 100)
        # Format integer part with dots every 3 digits
        int_str = f"{integer_part:,}".replace(",", ".")
        return f"R$ {int_str},{decimal_part:02d}"
    else:
        return f"-{_fmt_brl(abs(value))}"
```

**Key design decisions**:
1. `_fmt_brl` is a custom formatter — Python's `locale` module requires OS-level locale installation and is fragile. This pure-function approach works everywhere.
2. The empty state is triggered when `exam_count_today == 0`. This covers both "no row in DB" and "row exists with all zeros".
3. `_build_pill_indicators` returns HTML. `st.metric` renders its `delta` parameter as markdown, so inline HTML with `<span>` tags works.
4. The Meta Mensal card loads `load_month` to compute MTD inside the KPI row — a small tradeoff (one extra query) for keeping the card self-contained.
5. The sparkline handler crosses month boundaries gracefully. If today is April 3 and we only have 3 days, it loads March data too.

#### Verification (Task 2.6)

```bash
# Syntax check
python -c "import ast; ast.parse(open('src/ui/today.py').read()); print('Syntax OK')"

# Verify all imports resolve
python -c "
from src.ui.today import render_today_tab
print('render_today_tab imported OK')
"

# Verify helper functions exist
grep "^def " src/ui/today.py
# Expected: render_today_tab, _render_empty_state, _render_kpi_row,
#           _render_sparkline, _build_pill_indicators, _fmt_brl

# Quick unit test of _fmt_brl (import it directly)
python -c "
from src.ui.today import _fmt_brl
assert _fmt_brl(1250.0) == 'R\\$ 1.250,00'
assert _fmt_brl(0.0) == 'R\\$ 0,00'
assert _fmt_brl(1000000.0) == 'R\\$ 1.000.000,00'
print('_fmt_brl tests passed')
"
```

---

### Task 2.7 — Integrate into `app.py` (5 min)

Replace the Hoje tab stub in `app.py`.

Open `/home/galvani/dev/radtracker/app.py`. Find the lines:

```python
with tab_hoje:
    st.header("📊 Hoje")
    st.info("Em breve — dados de hoje (Sprint 2)")
```

Replace them with:

```python
with tab_hoje:
    render_today_tab(conn)
```

The full `app.py` should now look like:

```python
"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprint 1: sidebar + SQLite + 4 placeholder tabs.
Sprint 2: Hoje tab with KPI cards, donut chart, sparkline.
"""

import streamlit as st

from src.db import get_connection, init_db
from src.ui.sidebar import render_sidebar
from src.ui.today import render_today_tab

# Page config — MUST be first Streamlit command
st.set_page_config(
    page_title="radtracker",
    page_icon="📊",
    layout="wide",
)

# Database initialization (idempotent)
conn = get_connection()
init_db(conn)

# Sidebar
render_sidebar(conn)

# Tabs
tab_hoje, tab_mes, tab_analise, tab_config = st.tabs([
    "📊 Hoje",
    "📅 Mês Atual",
    "📈 Análise",
    "⚙️ Config",
])

with tab_hoje:
    render_today_tab(conn)

with tab_mes:
    st.header("📅 Mês Atual")
    st.info("Em breve — visão mensal (Sprint 3)")

with tab_analise:
    st.header("📈 Análise")
    st.info("Em breve — análises e insights (Sprint 4)")

with tab_config:
    st.header("⚙️ Configurações")
    st.info("Em breve — preços e meta (Sprint 5)")
```

**Why import at the top of the file?** This keeps all imports visible in one place, matching the Sprint 1 convention. The import is only executed once per script run (Python caches modules), so there is no performance penalty.

#### Verification (Task 2.7)

```bash
# Verify the app.py syntax
python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"

# Verify the import line exists
grep "render_today_tab" app.py
# Expected: at least one match

# Verify the old stub is gone
grep "Em breve — dados de hoje" app.py
# Expected: NO OUTPUT (stub should be removed)
```

---

### Task 2.8 — Manual Smoke Test (30 min)

Start the app and verify every element.

```bash
cd /home/galvani/dev/radtracker
source venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501. Go through each test case below.

#### Test A: Empty State (first visit or no data for today)

1. If you already have data for today, select a future date or a date you haven't entered data for.
2. **Expected**: The Hoje tab shows the empty-state card:
   - 📋 icon centered
   - "Nenhum registro ainda" heading
   - "Comece registrando sua produção de hoje na barra lateral →" body text
   - No KPI cards, no chart
3. ✅ Pass if the empty state renders without errors.

#### Test B: First Data Entry — KPI Cards

1. In the sidebar, select today's date.
2. Enter: RM=8, TC=6, RX=35 → click "💾 Salvar produção".
3. **Expected on Hoje tab**:
   - **💰 Faturamento hoje**: `R$ 587,50` (8×35 + 6×25 + 35×4.5 = 280 + 150 + 157.50)
   - Delta: "— sem dados de ontem" (no yesterday data)
   - **📋 Exames hoje**: `49` total, with pills: `● RM 8 · ● TC 6 · ● RX 35` in modality colors
   - **⏱️ Horas estimadas**: `2.3h` (8/7.5 + 6/7.5 + 35/75 = 1.07 + 0.80 + 0.47 ≈ 2.33h)
   - Time range: `~08:00 – 10:20` (2.33h after 08:00)
   - **🎯 Meta mensal**: `1%` (R$ 587,50 / R$ 45.000)
4. ✅ Pass if all 4 cards render with numerically correct values.

#### Test C: Delta vs Yesterday

1. Save data for yesterday (if not already present). Example: RM=5, TC=4, RX=20.
   - Yesterday earnings: 5×35 + 4×25 + 20×4.5 = 175 + 100 + 90 = R$ 365.00
2. Save today's data: RM=8, TC=6, RX=35 (R$ 587.50).
3. **Expected**: Delta shows `+61.0% vs ontem` in **green**.
   - (587.50 - 365.00) / 365.00 × 100 = 60.96% → rounds to 61.0%
4. Now edit today to be lower: RM=2, TC=2, RX=5 → R$ 142.50.
5. **Expected**: Delta shows `-61.0% vs ontem` in **red**.
   - (142.50 - 365.00) / 365.00 × 100 = -60.96%
6. ✅ Pass if delta color and direction are correct.

#### Test D: Modality Donut Chart

1. Enter data: RM=8, TC=6, RX=35.
2. **Expected**: A donut chart below the KPI row:
   - 3 slices: RM (blue #2563EB), TC (amber #D97706), RX (cyan #0891B2)
   - Percentages: RM ~16.3%, TC ~12.2%, RX ~71.4% (8/49, 6/49, 35/49)
   - Labels: "RM", "TC", "RX" with percentages
   - Hole in center (donut, not pie)
   - Legend below chart (horizontal)
3. Zero-test: Enter RM=0, TC=0, RX=0. Chart should render without error (empty ring).
4. ✅ Pass if donut renders with correct colors and approximate proportions.

#### Test E: Sparkline

1. Enter data for 4+ different days (including today). Use different values.
2. **Expected**: A compact line chart below the donut:
   - Title: "Faturamento — Últimos 7 Dias"
   - Teal line connecting daily earnings
   - Light teal fill below the line
   - X-axis labels in DD/MM format
   - Y-axis with "R$ " prefix
   - Hover shows exact value
3. ✅ Pass if sparkline renders and values match entered data.

#### Test F: UPSERT Refresh

1. View the Hoje tab with existing data.
2. Change a value in the sidebar (e.g., increase RM from 8 to 12) and save.
3. **Expected**: KPI cards update immediately, donut proportions change, sparkline updates.
4. ✅ Pass if refresh is instantaneous after save.

#### Test G: Month Boundary Sparkline

1. If today is April 1 or 2, save data for March 29, 30, 31 and April 1, 2.
2. **Expected**: Sparkline shows a continuous line crossing the month boundary.
3. ✅ Pass (or skip if not near a month boundary).

#### Test H: Theme Toggle

1. ☰ → Settings → Theme → Dark.
2. **Expected**: All charts remain legible (transparent backgrounds adapt), KPI cards readable.
3. Toggle back to Light.
4. ✅ Pass if both themes work.

---

## 3. Sprint 2 Definition of Done

All items must be ✅ before Sprint 2 is complete:

- [ ] `streamlit run app.py` starts without errors
- [ ] Hoje tab shows empty-state card when no data for today (📋 icon, friendly message, arrow to sidebar)
- [ ] **💰 Faturamento hoje**: R$ formatted value correct to the centavo
- [ ] Faturamento delta: green ↑ for positive, red ↓ for negative, "— sem dados de ontem" when no yesterday data
- [ ] **📋 Exames hoje**: total count correct, modality pill indicators in correct colors (RM=#2563EB ●, TC=#D97706 ●, RX=#0891B2 ●)
- [ ] **⏱️ Horas estimadas**: decimal hours match midpoint formula (RM/7.5 + TC/7.5 + RX/75), time range format "~08:00 – HH:MM"
- [ ] **🎯 Meta mensal**: percentage correct (MTD/meta × 100), "R$ X / R$ GOAL" subtitle
- [ ] Modality donut chart renders with 3 slices in correct colors, hole=0.4, Portuguese labels
- [ ] Sparkline renders with 2+ days of data, teal line, DD/MM x-axis labels
- [ ] UPSERT works: editing today's values and re-saving updates all cards and charts
- [ ] Currency formatting uses Brazilian conventions: "R$ 1.250,00" (dot thousands, comma decimals)
- [ ] Empty donut (all zeros) renders without errors
- [ ] App does not crash when `exam_prices` table is empty (uses defaults)
- [ ] App does not crash when `monthly_goals` table is empty (uses R$ 45.000 default)
- [ ] All 4 files created/modified: `src/calculations.py` (new), `src/db.py` (modified), `src/charts.py` (new), `src/ui/today.py` (new), `app.py` (modified)
- [ ] No hardcoded secrets in any file
- [ ] All functions have type hints on public signatures

---

## 4. Common Pitfalls & Debugging

### Pitfall 1: `AttributeError: 'SQLConnection' object has no attribute 'connect'`

If the Streamlit version uses a different internal API:
- The read path (`conn.query()`) is normally stable.
- The write path (`upsert_daily`, `save_prices`, `save_goal`) uses `conn.connect()`. If this fails, it was already handled in Sprint 1.
- Sprint 2 only reads data — no new write paths. This should not be an issue.

### Pitfall 2: ImportError when loading `src/ui/today.py`

If `app.py` fails with an import error at the `from src.ui.today import render_today_tab` line:
- Check that `src/ui/__init__.py` exists (created in Sprint 1).
- Check that `src/calculations.py` and `src/charts.py` exist and have no syntax errors.
- Run `python -c "from src.ui.today import render_today_tab"` to isolate the error.

### Pitfall 3: `st.metric` delta rendering HTML incorrectly

The `_build_pill_indicators` function returns HTML with `<span>` tags. Older Streamlit versions may not render HTML in `delta`. If the pills show raw HTML:
- **Fix**: Streamlit 1.54+ supports markdown in `delta`. If pills don't render, wrap the metric in a `st.container` and use `st.markdown` separately for the pills.

### Pitfall 4: Date string format mismatch

SQLite stores dates as `YYYY-MM-DD` (ISO format). `date.today().isoformat()` produces this format. But verify:
```python
from datetime import date
print(date.today().isoformat())  # Must be "2026-04-29" not "2026-4-29"
```
Python's `isoformat()` always zero-pads — this is reliable.

### Pitfall 5: `_fmt_brl` negative number handling

`_fmt_brl` handles negative numbers via recursion. For very small negative amounts (-0.001), ensure `math.floor` behaves correctly. The function is used for KPI display where values are non-negative; the negative path is defensive.

### Pitfall 6: `eval` or f-string injection in pill indicators

The `_build_pill_indicators` function uses string concatenation, not f-strings, for the modality counts. The inputs `rm`, `tc`, `rx` are integers from the database — they cannot contain HTML. This is safe.

### Pitfall 7: Sparkline with 1 data point

If the user has only entered data for 1 day, `build_daily_sparkline` is not called (the guard `len(all_days) >= 2` prevents it). This is correct behavior — a sparkline with a single point conveys no trend.

### Pitfall 8: Plotly `sort=False` not working as expected

In some Plotly versions, `sort=False` on `go.Pie` may not preserve order. If slices appear in the wrong order (RM, RX, TC instead of RM, TC, RX):
- **Fix**: Pass the data as a list of `go.Pie` traces (one per slice) or use `textinfo='label+percent'` and check the `direction` parameter.

### Pitfall 9: `conn.query()` with `ttl=0` not refreshing

The existing `load_daily` uses `ttl=0` (no caching). After UPSERT, `st.rerun()` is called, which re-executes the entire script. This should always give fresh data. If stale data appears:
- Verify `ttl=0` (or omit `ttl` entirely, as in some `load_*` functions).
- Clear Streamlit cache: `streamlit cache clear` or Ctrl+C and restart.

### Pitfall 10: Modality colors not visible in dark mode

The donut chart uses `paper_bgcolor="rgba(0,0,0,0)"` — transparent background. In dark mode, the chart should inherit the dark canvas. If text is hard to read:
- The `textfont` color uses `CHART_COLORS["neutral"]` (#64748B) — this may be too dark on a dark background.
- **Fix**: Use `textfont=dict(size=14)` without specifying color, letting Plotly auto-choose based on the theme; or detect Streamlit's theme and adjust.

---

## 5. Files Modified / Created

### New Files (3)

| File | Lines (approx.) | Purpose |
|---|---|---|
| `src/calculations.py` | ~140 | Business logic: earnings, hours, MTD, daily stats |
| `src/charts.py` | ~100 | Plotly factory: donut and sparkline |
| `src/ui/today.py` | ~130 | Hoje tab UI: KPI row, empty state, chart rendering |

### Modified Files (2)

| File | Change | Lines (+/-) |
|---|---|---|
| `src/db.py` | Add `load_settings()` convenience function | +18 |
| `app.py` | Replace Hoje tab stub with `render_today_tab(conn)` | +2 / -2 |

### Unchanged Files

- `src/chart_colors.py` — imported as-is
- `src/ui/sidebar.py` — unchanged (provides input data)
- `.streamlit/config.toml` — unchanged
- `.env.example`, `.gitignore`, `requirements.txt`, `README.md` — unchanged

---

## 6. Quick Reference: Data Flow

```
User saves data in sidebar
  → upsert_daily(conn, date, rm, tc, rx)  [db.py]
  → st.rerun()
    → app.py re-executes
      → render_today_tab(conn)
        → load_prices(conn)               [db.py]
        → load_goal(conn, year_month)      [db.py]
        → compute_daily_stats(conn, ...)   [calculations.py]
          → load_daily(conn, today)        [db.py]
          → load_daily(conn, yesterday)    [db.py]
          → compute_earnings()             [calculations.py]
          → estimate_hours()               [calculations.py]
        → load_month(conn, year_month)     [db.py]
        → compute_mtd_earnings()           [calculations.py]
        → build_modality_donut(rm, tc, rx) [charts.py]
        → build_daily_sparkline(df)        [charts.py]
```

---

## 7. Next Sprint (Sprint 3) Preview

After Sprint 2 is complete and verified, Sprint 3 will add the "Mês Atual" tab:
- Monthly KPI row (MTD earnings, % goal, days worked/remaining)
- Monthly progress gauge (4-segment colored bar)
- Daily earnings line chart for all days in the month
- Monthly modality donut
- Rhythm alerts (behind-pace warnings)

No sprint-3 code should be written until Sprint 2 passes Definition of Done.
