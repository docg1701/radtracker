# Implementation Plan — Sprint 3: "Mês Atual" Tab

## Goal
Build the "Mês Atual" tab with monthly KPI cards, 4-segment progress gauge, daily earnings line chart, monthly modality revenue donut, and behind-pace rhythm alerts.

---

## Tasks

### 3.1: Add `compute_monthly_stats()` to `src/calculations.py`
- **File**: `src/calculations.py` (append to end, before any `_private` helpers or after existing code)
- **Changes**: Add a new public function after `_yesterday_str`.
- **Signature**: `def compute_monthly_stats(conn: Any, year_month: str, goal: float, prices: dict[str, float]) -> dict[str, Any]`
- **Logic**:
  1. Call `load_month(conn, year_month)` to get the month's DataFrame.
  2. Compute `mtd_earnings` via the existing `compute_mtd_earnings(month_df, prices)`.
  3. Compute `pct_goal = (mtd_earnings / goal * 100) if goal > 0 else 0.0`.
  4. Compute `days_worked` = number of rows in `month_df` (i.e., `len(month_df)`).
  5. Compute `total_work_days`: number of Mon–Sat days in the year_month.
     - Parse `year_month` into year and month integers.
     - Compute last day of month with `calendar.monthrange(year, month)[1]`.
     - Build a `pandas.DatetimeIndex` from `pd.bdate_range(start=f"{year_month}-01", end=f"{year_month}-{last_day:02d}", freq='C', weekmask='Mon Tue Wed Thu Fri Sat')`. `len()` gives total.
  6. Compute `remaining_work_days`: Mon–Sat days from today (inclusive) to end of month.
     - If year_month is not the current month, remaining_work_days = 0.
     - Otherwise, `pd.bdate_range(date.today(), end_of_month, freq='C', weekmask='Mon Tue Wed Thu Fri Sat')`.
  7. Compute `daily_avg = mtd_earnings / days_worked if days_worked > 0 else 0.0`.
  8. Compute `daily_target_needed = (goal - mtd_earnings) / remaining_work_days if remaining_work_days > 0 else 0.0`.
  9. Compute `projection_month_end = mtd_earnings + (daily_avg * remaining_work_days)`.
  10. Return dict with all keys: `mtd_earnings`, `pct_goal`, `days_worked`, `total_work_days`, `remaining_work_days`, `daily_avg`, `daily_target_needed`, `projection_month_end`, `working_days_left` (alias for `remaining_work_days`).
- **Edge cases**:
  - Empty month (no data): mtd_earnings=0, pct_goal=0, days_worked=0, daily_avg=0.
  - Past months: remaining_work_days=0, daily_target_needed=0.
  - Goal is 0: pct_goal=0 to avoid division by zero.
- **Imports needed**: `from datetime import date` (already imported), `import calendar`, `import pandas as pd` (already imported), `from src.db import load_month`.
- **Acceptance**: Call with a known year_month and goal, verify returned dict values are correct. Test edge cases manually.

### 3.2: Add `compute_daily_target()` to `src/calculations.py`
- **File**: `src/calculations.py` (append in the "Pure functions" section, after `add_earnings_column`)
- **Changes**: Add a pure helper function.
- **Signature**: `def compute_daily_target(monthly_goal: float, total_working_days: int) -> float`
- **Logic**: `return monthly_goal / total_working_days if total_working_days > 0 else 0.0`
- **Acceptance**: `compute_daily_target(45000.0, 26)` returns `~1730.77`.

### 3.3: Add `build_progress_gauge()` to `src/charts.py`
- **File**: `src/charts.py` (append after existing functions)
- **Changes**: Add a new chart factory function.
- **Signature**: `def build_progress_gauge(pct_goal: float) -> go.Figure`
- **Design per DESIGN_SPEC §4.2**: Horizontal stacked bar with 4 milestone segments + marker.
- **Implementation approach**:
  - Create a horizontal bar chart (`go.Bar`, `orientation='h'`).
  - Use 5 traces, each with `width=0.3` and a single category on y-axis:
    1. **Segment 1 (0–25%)**: `value = min(25.0, pct_goal)`, color = `CHART_COLORS["progress_danger"]` (#DC2626)
    2. **Segment 2 (25–50%)**: `value = max(0.0, min(25.0, pct_goal - 25.0))`, color = `CHART_COLORS["progress_warning"]` (#CA8A04)
    3. **Segment 3 (50–75%)**: `value = max(0.0, min(25.0, pct_goal - 50.0))`, color = `CHART_COLORS["progress_on_track"]` (#0D9488)
    4. **Segment 4 (75–100%)**: `value = max(0.0, pct_goal - 75.0)`, color = `CHART_COLORS["progress_achieved"]` (#16A34A)
    5. **Unfilled remainder**: `value = max(0.0, 100.0 - pct_goal)`, color = `CHART_COLORS["track"]` (the bar track background — add `"track": "#E2E8F0"` to `CHART_COLORS`)
    - Use `base` parameter for stacking: segment 2's base = cumulative of segment 1, etc. Or use Plotly's built-in stacking with `barmode='stack'`.
  - Add a marker (diamond or circle `go.Scatter`) at x=`pct_goal`, y=0, with color matching the segment it falls in.
  - Add annotation showing the percentage: `f"{pct_goal:.0f}%"`.
  - Layout:
    - `title="Progresso da Meta Mensal"` (font size 16)
    - `xaxis`: range=[0, 100], tick suffix="%", showgrid=False, tickvals=[0, 25, 50, 75, 100]
    - `yaxis`: fixedrange=True, showticklabels=False (single bar, no y-axis needed)
    - `height=100`
    - `paper_bgcolor="rgba(0,0,0,0)"`, `plot_bgcolor="rgba(0,0,0,0)"`
    - `margin=dict(l=20, r=20, t=40, b=20)`
    - `legend`: hidden (not needed — segments are self-explanatory)
    - `barmode='stack'`, `bargap=0`
  - **Alternative approach**: Use `go.Figure` with horizontal stacked bars. Use `go.Bar(x=[...], y=["Meta"], orientation='h', marker_color=...)` for each segment.
- **Note**: The 4 colored bars + 1 gray bar should be rendered as a single horizontal stacked bar. The easiest way: one `go.Bar` per segment, each with `y=[""]` (single category), using `barmode='stack'`.
- **Edge case**: pct_goal > 100 → clamp to 100 for display (all 4 segments filled, no gray remainder).
- **Acceptance**: Call `build_progress_gauge(41.0)`. Verify chart has 5 bar traces with correct colors and a marker near x=41. Verify `build_progress_gauge(0.0)` shows all gray. Verify `build_progress_gauge(100.0)` shows all colored segments.

### 3.4: Add `build_monthly_earnings_chart()` to `src/charts.py`
- **File**: `src/charts.py` (append after progress gauge)
- **Changes**: Add new chart function.
- **Signature**: `def build_monthly_earnings_chart(df: pd.DataFrame, daily_target: float, year_month: str) -> go.Figure`
- **Input**: `df` has columns `date` (str ISO) and `earnings` (float). Will typically be the output of `add_earnings_column(month_df, prices)`. Days without data will be missing from the DataFrame.
- **Logic**:
  1. `year_month` is passed explicitly (e.g., `"2026-04"`) because an empty DataFrame provides no date to infer from.
  2. Build a complete list of all dates in the month: `pd.date_range(start=f"{year_month}-01", periods=days_in_month, freq='D')`.
  3. Merge with actual data: create a DataFrame with all dates, left-join the earnings data. Fill missing earnings with 0.0.
  4. X-axis labels: day numbers 1, 2, 3, …, 28/29/30/31 (extracted from date).
  5. Y-axis: earnings in R$.
  6. **Traces**:
     - Main line: `go.Scatter` with `mode='lines+markers'`, teal color (`CHART_COLORS["primary"]`), width 2.
     - Daily target line: `go.Scatter` with `mode='lines'`, dashed (`dash='dash'`), muted color (`CHART_COLORS["muted"]`), constant y=`daily_target` across all x positions.
     - Today marker: `go.Scatter` with a single point at today's date (x=day_number, y=that_day's_earnings) — use a larger marker and a vertical dashed line annotation.
  7. **Layout**:
     - `title="Faturamento Diário — Abril 2026"` (dynamic month name in Portuguese, e.g., "Abril", "Maio" — map month number to name).
     - `height=400`
     - `xaxis`: title=None, tickvals=day numbers, showgrid=False
     - `yaxis`: title=None, tickprefix="R$ ", showgrid=True, gridcolor=CHART_COLORS["track"]
     - `hovermode='x unified'`
     - `paper_bgcolor="rgba(0,0,0,0)"`, `plot_bgcolor="rgba(0,0,0,0)"`
     - `margin=dict(l=20, r=20, t=50, b=20)`
  - **Edge cases**:
  - Empty DataFrame → show all days with zero earnings and the target line.
  - If `year_month` is not the current month, omit the today marker and vertical line (they would fall outside the axis range).
- **Acceptance**: Build with 5 days of sample data. Verify teal line connects all points, dashed target line visible, today marker present.

### 3.5: Add `build_monthly_modality_donut()` to `src/charts.py`
- **File**: `src/charts.py` (append after monthly earnings chart)
- **Changes**: Add new chart function.
- **Signature**: `def build_monthly_modality_donut(df: pd.DataFrame, prices: dict[str, float]) -> go.Figure`
- **Input**: `df` has columns `rm_count`, `tc_count`, `rx_count` (raw counts for the month).
- **Logic**:
  1. Sum each modality count: `total_rm = df["rm_count"].sum()`, `total_tc = df["tc_count"].sum()`, `total_rx = df["rx_count"].sum()`.
  2. Compute revenue per modality:
     - `rm_revenue = total_rm * prices["rm"]`
     - `tc_revenue = total_tc * prices["tc"]`
     - `rx_revenue = total_rx * prices["rx"]`
  3. Build donut chart (similar to `build_modality_donut` but using revenue values instead of counts):
     - `labels = ["RM", "TC", "RX"]`
     - `values = [rm_revenue, tc_revenue, rx_revenue]`
     - Same colors: RM=#2563EB, TC=#D97706, RX=#0891B2
     - Same `hole=0.4`, `textinfo="label+percent"`, `sort=False`
     - Title: `"Receita por Modalidade — {month_name}"` (dynamic month)
  4. Layout identical to `build_modality_donut` but with different title.
- **Edge case**: All zeros → donut renders empty ring (Plotly handles gracefully).
- **Acceptance**: Build with sample data. Verify slices represent revenue share, not count share. E.g., 1 RM (R$35) + 10 RX (R$45) → RM = 43.75%, RX = 56.25%.

### 3.6: Create `src/ui/month.py`
- **File**: `src/ui/month.py` (new file)
- **Changes**: Create the complete "Mês Atual" tab renderer.
- **Structure**:
  ```python
  """Month tab — monthly KPI row, progress gauge, daily earnings line, modality donut."""
  from datetime import date
  from typing import Any
  import pandas as pd
  import streamlit as st
  from src.calculations import (
      compute_monthly_stats,
      compute_daily_target,
      add_earnings_column,
  )
  from src.charts import (
      build_progress_gauge,
      build_monthly_earnings_chart,
      build_monthly_modality_donut,
  )
  from src.chart_colors import CHART_COLORS
  from src.db import load_month, load_prices, load_goal

  def render_month_tab(conn: Any) -> None:
      ...
  ```
- **`render_month_tab` logic**:
  1. Get current month: `today = date.today()`, `year_month = today.isoformat()[:7]`.
  2. Load prices, goal: `prices = load_prices(conn)`, `goal = load_goal(conn, year_month)`.
  3. Compute stats: `stats = compute_monthly_stats(conn, year_month, goal, prices)`.
  4. Load month data: `month_df = load_month(conn, year_month)`.
  5. Compute daily target: `daily_target = compute_daily_target(goal, stats["total_work_days"])`.
  6. **Render KPI row** (4 `st.columns`):
     - Card 1: "💰 Faturamento MTD" — `_fmt_brl(stats["mtd_earnings"])`, delta: `f"{_fmt_brl(stats['projection_month_end'])} projetado"` (or similar)
     - Card 2: "🎯 % da Meta" — `f"{stats['pct_goal']:.0f}%"`, delta: `f"{_fmt_brl(stats['mtd_earnings'])} / {_fmt_brl(goal)}"`
     - Card 3: "📅 Dias Trabalhados" — `f"{stats['days_worked']} de {stats['total_work_days']}"`, delta: `f"{stats['remaining_work_days']} restantes"`
     - Card 4: "📊 Média Diária" — `_fmt_brl(stats["daily_avg"])`, delta: `f"Alvo: {_fmt_brl(daily_target)}/dia"` (if below target, show amber warning)
  7. **Render progress gauge**: `gauge = build_progress_gauge(stats["pct_goal"])`, `st.plotly_chart(gauge, use_container_width=True)`.
  8. **Render chart row** (2 `st.columns`):
     - Left: `st.subheader("📈 Faturamento Diário")`, then `earnings_df = add_earnings_column(month_df, prices)`, `line_chart = build_monthly_earnings_chart(earnings_df, daily_target, year_month)`, `st.plotly_chart(line_chart, use_container_width=True)`.
     - Right: `st.subheader("🍩 Receita por Modalidade")`, then `donut = build_monthly_modality_donut(month_df, prices)`, `st.plotly_chart(donut, use_container_width=True)`.
  9. **Render rhythm alert**: Call `_render_rhythm_alert(stats)`.
- **`_render_rhythm_alert(stats)`** helper:
  - Guard against `total_work_days == 0` (theoretically impossible for any real month, but defensively bail out).
  - Check if behind pace: `pct_goal < (days_worked / total_work_days * 100)` when `total_work_days > 0`.
  - If behind pace:
    - Compute missing: `goal - mtd_earnings`, daily needed: `daily_target_needed`.
    - Show `st.warning(f"⚠️ **Atenção ao ritmo**\n\nGalvani, você está atrás do ritmo para bater a meta de {_fmt_brl(goal)}.\n\nFaltam {_fmt_brl(missing)} em {remaining_work_days} dias úteis — você precisa de **{_fmt_brl(daily_target_needed)}/dia** daqui pra frente.\n\nSua média atual: {_fmt_brl(daily_avg)}/dia.")`.
  - If on track or ahead:
    - `st.success(...)` or no alert (just a neutral `st.info(...)` or nothing). Per DESIGN_SPEC, only the warning state triggers a visible alert. The success state is evident from the green gauge.
- **`_fmt_brl` helper**: Copy the same formatter from `src/ui/today.py`. **Decision**: since this is duplicated, extract it to a shared utility later (Sprint 6 refactor). For Sprint 3, define it privately within `month.py` as `_fmt_brl`. Add a comment: `# TODO: extract to src/formatting.py in Sprint 6`.
- **Empty state**: If `stats["days_worked"] == 0`, show `st.info("Nenhum dado registrado neste mês. Comece registrando sua produção na aba **📊 Hoje**.")` instead of all charts.
- **Acceptance**: Tab renders without errors. KPI cards show correct values. Gauge reflects percentage. Line chart plots all days. Donut shows revenue share. Alert shows when behind pace.

### 3.7: Integrate into `app.py`
- **File**: `app.py`
- **Changes**:
  1. Add import: `from src.ui.month import render_month_tab` (alongside other imports at lines 10-12).
  2. Replace lines ~36-38 (the `tab_mes` stub: `st.header("📅 Mês Atual")` + `st.info("Em breve...")`) with a single call: `render_month_tab(conn)`.
- **Acceptance**: `grep "render_month_tab" app.py` shows the import AND the call. The old placeholder text is gone.

### 3.8: Manual Smoke Test
- **Process**:
  1. Start app: `streamlit run app.py`.
  2. Ensure data exists for the current month (insert 5–10 varied days via sidebar — different counts each day).
  3. Navigate to "📅 Mês Atual" tab.
  4. **Verify KPI row**: earnings MTD matches sum of daily earnings, % goal matches calculation, days worked matches count of distinct dates in DB, daily avg = MTD / days worked.
  5. **Verify progress gauge**: correct % shown, correct segments colored, marker at correct position.
  6. **Verify daily earnings line**: all days appear on x-axis (1..N), data points at correct values, target line visible, today marker present.
  7. **Verify modality donut**: slices add up to 100%, proportions match revenue, not counts.
  8. **Verify rhythm alert**: If pct_goal < expected pace, yellow warning appears with specific numbers.
  9. **Edge case — empty month**: Delete all current-month data. Tab should show friendly empty state message.
  10. **Edge case — past month**: Modify date in sidebar to a past month, save data. Switch to Mês Atual — it only shows current month (the tab always uses `date.today()`). **Note**: This sprint targets only the *current* month. Past month navigation is Sprint 4+ scope.
  11. **Theme toggle**: Switch to dark mode. Verify all 3 charts (gauge, line, donut) are legible on dark background.

---

## Files to Modify

| File | Changes |
|---|---|
| `src/calculations.py` | Add `compute_monthly_stats()` (DB-dependent, ~40 lines) and `compute_daily_target()` (pure, ~6 lines). Total addition: ~46 lines. |
| `src/charts.py` | Add `build_progress_gauge()` (~35 lines), `build_monthly_earnings_chart()` (~55 lines), `build_monthly_modality_donut()` (~30 lines). Total addition: ~120 lines. |
| `src/chart_colors.py` | Add `"track": "#E2E8F0"` for progress-gauge background. +1 line. |
| `app.py` | Replace `tab_mes` placeholder with `render_month_tab(conn)` call. Add import. ~3 lines changed. |

## New Files

| File | Purpose |
|---|---|
| `src/ui/month.py` | `render_month_tab(conn)` — renders the complete Mês Atual tab. ~120 lines. |

---

## Dependencies

```
3.1 (compute_monthly_stats) ── independent (uses existing load_month)
3.2 (compute_daily_target)   ── independent (pure function)
3.3 (build_progress_gauge)   ── independent (uses CHART_COLORS)
3.4 (build_monthly_earnings) ── independent (uses CHART_COLORS)
3.5 (build_monthly_mod_donut)── independent (uses CHART_COLORS)
3.6 (ui/month.py)            ── depends on 3.1, 3.2, 3.3, 3.4, 3.5
3.7 (app.py integration)     ── depends on 3.6
3.8 (smoke test)             ── depends on 3.7
```

Tasks 3.1–3.5 can be done in any order or parallelized. Task 3.6 requires all of them. Task 3.7 is a one-line change after 3.6.

---

## Risks

### R1: Business day calculation fragility
- **Issue**: `pd.bdate_range` with `weekmask` may behave differently across pandas versions. Christmas/holidays are not excluded (acceptable — this is a personal tool, not payroll).
- **Mitigation**: Use `pd.bdate_range(start, end, freq='C', weekmask='Mon Tue Wed Thu Fri Sat')` which is a documented pandas API. The `freq='C'` (CustomBusinessDay) is **required** whenever `weekmask` is passed; omitting it raises `ValueError: a custom frequency string is required when holidays or weekmask are passed`.
- **Verification**: Unit-test with April 2026: 30 calendar days, 4 Sundays (5, 12, 19, 26) → 26 working days. May 2026: 31 calendar days, 5 Sundays → 26 working days.

### R2: Duplicated `_fmt_brl` between `today.py` and `month.py`
- **Issue**: Copy-paste of the formatting function creates technical debt.
- **Mitigation**: Accept the duplication for Sprint 3. Add `# TODO: extract to src/formatting.py in Sprint 6` comments. This is intentional — the formatting function is small (8 lines) and shared utilities belong in a refactoring sprint.

### R3: `build_monthly_earnings_chart` needs year_month parameter
- **Issue**: The task spec says the function takes `(df, daily_target)`, but the function needs to know which month to generate the full day range. If `df` is empty, there's no date to infer from.
- **Resolution**: Add a `year_month: str` parameter. Signature: `def build_monthly_earnings_chart(df: pd.DataFrame, daily_target: float, year_month: str) -> go.Figure`. This is a slight deviation from the task spec that is necessary for correctness.

### R4: Streamlit metric delta color limitation
- **Issue**: `st.metric` only supports `"normal"` (green/red auto), `"inverse"` (red/green auto), or `"off"`. There's no amber/warning option.
- **Mitigation**: Use `delta_color="off"` for all monthly KPI cards and render delta text manually. The delta field can still be used — it just won't auto-color.
- **Alternative**: If the delta text needs amber coloring, we can render a separate `st.markdown` with inline CSS. But for Sprint 3, `delta_color="off"` is sufficient.

### R5: 3.2 (`load_month` + `add_earnings_column`) already exists
- **Issue**: The task description says "3.2: Add load_month_daily to db.py" but `load_month` already exists in `db.py` and `add_earnings_column` already exists in `calculations.py`. This task is already done from Sprint 2.
- **Resolution**: Skip any new DB functions. Use `load_month(conn, year_month)` followed by `add_earnings_column(df, prices)` wherever needed. The plan's task numbering (3.1–3.7) accounts for this.

### R6: `paper_bgcolor` value for Plotly
- **Issue**: The existing charts use `paper_bgcolor="rgba(0,0,0,0)"` (no space in `rgba`). The task description shows `paper_bgcolor='rgba(0,0,0,0)'`. The existing `build_modality_donut` uses `paper_bgcolor="rgba(0,0,0,0)"`.
- **Resolution**: Use the same format as existing code: `paper_bgcolor="rgba(0,0,0,0)"` and `plot_bgcolor="rgba(0,0,0,0)"`.

---

## Implementation Order

1. **`src/calculations.py`** — append `compute_daily_target()` (pure, simple) then `compute_monthly_stats()` (DB-dependent, more complex).
2. **`src/charts.py`** — append `build_progress_gauge()`, `build_monthly_earnings_chart()`, `build_monthly_modality_donut()` (order: simplest first).
3. **`src/ui/month.py`** — create the complete file with `render_month_tab()` and `_render_rhythm_alert()`.
4. **`app.py`** — add import, replace placeholder.
5. **Smoke test** — insert varied data, verify all elements.

---

## Chart Design Details (for implementor)

### Progress Gauge (`build_progress_gauge`)

```
Layout: single horizontal bar, 100px height, no legend

[████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 41%
│← 0-25% red →│← 25-50% amber →│← 50-75% teal →│← 75-100% green →│← unfilled gray →│
                                                     ↑ marker at 41%
```

Use `go.Bar` with `barmode='stack'`:
- `go.Bar(x=[seg1_width], y=[""], orientation='h', marker_color=CHART_COLORS["progress_danger"])`
- `go.Bar(x=[seg2_width], y=[""], orientation='h', marker_color=CHART_COLORS["progress_warning"])`
- `go.Bar(x=[seg3_width], y=[""], orientation='h', marker_color=CHART_COLORS["progress_on_track"])`
- `go.Bar(x=[seg4_width], y=[""], orientation='h', marker_color=CHART_COLORS["progress_achieved"])`
- `go.Bar(x=[unfilled_width], y=[""], orientation='h', marker_color=CHART_COLORS["track"])`
- `go.Scatter(x=[pct_goal], y=[""], mode='markers+text', marker=dict(symbol='triangle-down', size=14, ...), text=[f"{pct_goal:.0f}%"], textposition='top center')`

Set `barmode='stack'` in layout.

Clamp `pct_goal` to max 100 for display:
```python
display_pct = min(pct_goal, 100.0)
seg1 = min(25.0, display_pct)
seg2 = max(0.0, min(25.0, display_pct - 25.0))
seg3 = max(0.0, min(25.0, display_pct - 50.0))
seg4 = max(0.0, display_pct - 75.0)
unfilled = max(0.0, 100.0 - display_pct)
```

### Monthly Earnings Line (`build_monthly_earnings_chart`)

Use `pd.date_range` + merge to ensure all days present:
```python
import calendar
year, month = int(year_month[:4]), int(year_month[5:7])
days_in_month = calendar.monthrange(year, month)[1]
all_dates = pd.date_range(start=f"{year_month}-01", periods=days_in_month, freq='D')
full = pd.DataFrame({"date": all_dates.strftime("%Y-%m-%d")})
full["day_number"] = range(1, days_in_month + 1)
merged = full.merge(df, on="date", how="left")
merged["earnings"] = merged["earnings"].fillna(0.0)
```

Then plot:
- Main line: `go.Scatter(x=merged["day_number"], y=merged["earnings"], mode='lines+markers', ...)`
- Target line: `go.Scatter(x=[1, days_in_month], y=[daily_target, daily_target], mode='lines', line=dict(dash='dash', color=CHART_COLORS["muted"]))`
- Today marker: vertical line via `fig.add_vline(x=today_day_number, line_dash="dot", line_color=CHART_COLORS["neutral"])` plus annotation.

### Monthly Modality Donut (`build_monthly_modality_donut`)

Share code structure with `build_modality_donut`. Key difference: compute revenue, not count:
```python
rm_rev = float(df["rm_count"].sum()) * prices["rm"]
tc_rev = float(df["tc_count"].sum()) * prices["tc"]
rx_rev = float(df["rx_count"].sum()) * prices["rx"]
```

Portuguese month names:
```python
MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}
```

---

## Verification Checklist (Post-Implementation)

- [ ] `streamlit run app.py` starts without import errors
- [ ] "📅 Mês Atual" tab shows content (not placeholder)
- [ ] KPI row: 4 cards with correct values
  - `compute_monthly_stats` returns correct dict for known data
- [ ] Progress gauge: 4 colored segments + gray unfilled + marker
- [ ] Daily earnings line chart: all days on x-axis, teal line, dashed target, today marker
- [ ] Modality donut: revenue-based (not count-based), correct proportions
- [ ] Rhythm alert: yellow warning when behind pace, with specific numbers
- [ ] Empty state: friendly message when no data in month
- [ ] Dark mode: all charts legible
- [ ] `compute_daily_target(45000, 26)` returns `1730.769...`
- [ ] `build_progress_gauge(0)` renders cleanly (all gray)
- [ ] `build_progress_gauge(100)` renders cleanly (all color)
- [ ] File lengths: `calculations.py` under 500 lines, `charts.py` under 500 lines, `month.py` under 500 lines
- [ ] All functions have type hints
- [ ] No hardcoded hex colors (all via `CHART_COLORS`)
- [ ] `paper_bgcolor="rgba(0,0,0,0)"`, `plot_bgcolor="rgba(0,0,0,0)"` on all figures
- [ ] Portuguese UI text, English code
