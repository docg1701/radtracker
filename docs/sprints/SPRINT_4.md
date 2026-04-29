# Sprint 4 Implementation Plan — radtracker

**Created**: 2026-04-29
**Status**: Ready for implementation
**Full plan**: [docs/sprints/SPRINT_4.md](docs/sprints/SPRINT_4.md)

---

## Goal

Build the "📈 Análise & Insights" tab with rule-based insights, moving averages (MA7/MA30), week-over-week comparisons, and modality mix evolution charts.

---

## Tasks (ordered)

| # | Task | File(s) | Depends on |
|---|---|---|---|
| 4.1 | **Add `compute_historical_stats()`** — loads all historical data, computes MA7, MA30, WoW, MoM, modality mix, consecutive-below-target | `src/calculations.py` | Existing `load_month`, `add_earnings_column` |
| 4.2 | **Create `src/insights_rules.py`** — pure function `generate_rule_insights(stats) -> str` with 4 tone levels (success/on-track/warning/danger) | `src/insights_rules.py` (new) | None (zero deps) |
| 4.3 | **Add `build_moving_averages_chart()`** — teal MA7 solid + gray MA30 dashed line chart | `src/charts.py` | 4.1 (shape of stats dict) |
| 4.4 | **Add `build_wow_comparison_chart()`** — grouped bar chart: current vs previous week per modality | `src/charts.py` | 4.1 |
| 4.5 | **Add `build_modality_mix_evolution()`** — stacked area chart: RM/TC/RX % over months | `src/charts.py` | 4.1 |
| 4.6 | **Create `src/ui/analysis.py`** — renders insight card + 3 charts, handles empty/loading states | `src/ui/analysis.py` (new) | 4.1–4.5 |
| 4.7 | **Integrate into `app.py`** — replace "Análise" tab placeholder | `app.py` | 4.6 |

---

## Parallelization

- **4.1** and **4.2** can be done in parallel (insights_rules.py has zero dependencies)
- **4.3, 4.4, 4.5** can be done in parallel once 4.1 is complete
- **4.6** requires all of 4.1–4.5
- **4.7** is a one-line change after 4.6

---

## Key Design Decisions

1. **`compute_historical_stats` loads ALL months** via `SELECT DISTINCT substr(date,1,7) FROM daily_production`, then `load_month` per month. MA7/MA30 computed with `min_periods=1` so early months have meaningful values.

2. **Week grouping**: ISO calendar weeks (Monday–Sunday) via `date_dt.dt.isocalendar().week`. WoW chart shows "Semana Atual" (possibly incomplete current week) vs "Semana Anterior" (full previous week).

3. **Modality mix percentages**: Revenue-based (count × price), not raw counts. Guard against `0/0 → NaN` by setting percentages to `0.0` when total revenue is zero.

4. **Chart colors**: All via `CHART_COLORS` dict — no inline hex. Transparent backgrounds (`rgba(0,0,0,0)`) for theme compatibility.

5. **`_fmt_brl` duplicated** in `analysis.py` with `# TODO: extract to src/formatting.py in Sprint 6` — accepted technical debt.

---

## Risk Summary

| Risk | Severity | Mitigation |
|---|---|---|
| `compute_historical_stats` slow with large datasets | Low — personal tool, ~1800 rows/year max | `min_periods=1` ensures fast rolling; pandas handles it in milliseconds |
| ISO week numbering at year boundaries | Low | Sort by (iso_year, iso_week) tuple, not week alone |
| `modality_mix_historical` NaN for zero-count months | Medium — breaks stacked area chart | Guard: if `total_rev == 0`, set all three `pct` to `0.0` |
| `charts.py` approaching 500-line limit (~490 lines after additions) | Medium | If exceeded, extract analysis charts to `src/charts_analysis.py` |

---

## Verification

After implementation, run:

```bash
streamlit run app.py
# Navigate to "📈 Análise" tab
# Verify: insight card, 3 charts, empty state for <2 days data
```
