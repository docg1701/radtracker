# Implementation Plan — radtracker

**Date**: 2026-04-29
**Status**: Planning complete. Implementation pending.
**Source docs**: [BRIEF.md](./BRIEF.md), [DESIGN_SPEC.md](./DESIGN_SPEC.md), [RESEARCH.md](./RESEARCH.md)

---

## Sprint Tracking

Cada sprint passa por **execução** (desenvolvimento) e em seguida por uma ou mais rodadas de **revisão** (review) até que os critérios de Definition of Done sejam atingidos. A sprint seguinte só inicia após aprovação da sprint atual.

| Sprint | Status | Execução | Revisão #1 | Revisão #2 | Revisão #3 | DoD | Notas |
|--------|--------|----------|------------|------------|------------|-----|-------|
| **S1** — Foundation & Data Entry | ✅ Concluído | 2026-04-29 | ✅ Aprovado | — | — | ☑ | 12 files, 3 tables, UPSERT, app starts clean |
| **S2** — "Hoje" Tab | ⬜ Pendente | — | — | — | — | ☐ | KPI cards, donut chart, empty state |
| **S3** — "Mês Atual" Tab | ⬜ Pendente | — | — | — | — | ☐ | Progress gauge, daily trend, alerts |
| **S4** — "Análise & Insights" Tab | ⬜ Pendente | — | — | — | — | ☐ | Rule insights, MA7/MA30, WoW, mix evolution |
| **S5** — LLM & Settings | ⬜ Pendente | — | — | — | — | ☐ | Ollama Cloud, theme toggle, config tab |
| **S6** — Testing & Release | ⬜ Pendente | — | — | — | — | ☐ | ≥80% coverage, README, git tag v1.0.0 |

**Legenda**: ⬜ Pendente · 🔄 Em execução · 🔁 Em revisão · ✅ Concluído · ❌ Bloqueado

---

## Goal

Deliver a local, offline-first Streamlit dashboard that lets a teleradiologist (Galvani) log daily exam counts (RM/TC/RX), see real-time earnings projections, and receive actionable insights — all from a single `streamlit run app.py` command.

---

## 1. Architecture Overview

### 1.1 Module Interaction Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                          app.py                                  │
│  Entry point. Creates tabs: Hoje / Mês / Análise / Config.      │
│  Orchestrates ui/* modules. No business logic.                   │
└──────────┬──────────┬──────────┬──────────┬──────────────────────┘
           │          │          │          │
    ┌──────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌───▼──────┐
    │ ui/     │ │ ui/     │ │ ui/    │ │ ui/      │
    │ sidebar │ │ today   │ │ month  │ │ analysis │  ui/settings
    │ .py     │ │ .py     │ │ .py    │ │ .py      │
    └──┬───┬──┘ └───┬─────┘ └──┬─────┘ └──┬───┬───┘
       │   │        │          │          │   │
       │   │        └──────────┼──────────┘   │
       │   │                   │              │
       ▼   ▼                   ▼              ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│    db.py     │    │  calculations   │    │ llm_client   │
│              │    │      .py        │    │    .py       │
│ SQLite CRUD  │    │                 │    │              │
│ UPSERT       │    │ projections     │    │ Ollama Cloud │
│ queries      │    │ moving averages │    │ DeepSeek V4  │
│ read/write   │    │ WoW / MoM deltas│    │ fallback     │
└──────┬───────┘    └───────┬─────────┘    └──────┬───────┘
       │                    │                     │
       │                    ▼                     │
       │           ┌───────────────┐              │
       │           │ charts.py     │              │
       │           │ Plotly factory│              │
       │           │               │              │
       │           │ line, bar     │              │
       │           │ donut, gauge  │              │
       │           └───────┬───────┘              │
       │                   │                     │
       │                   ▼                     │
       │           ┌───────────────┐              │
       │           │ chart_colors  │              │
       │           │    .py        │              │
       │           │ shared palette│              │
       │           └───────────────┘              │
       │                                          │
       ▼                                          ▼
┌──────────────────────────────────────────────────────┐
│               insights_rules.py                      │
│   Rule-based fallback when LLM unavailable.          │
│   Pure functions: threshold checks, trend detection. │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│                  data/telerrad.db                     │
│   SQLite file. 3 tables: daily_production,           │
│   exam_prices, monthly_goals.                        │
└──────────────────────────────────────────────────────┘
```

### 1.2 Data Flow (Read Path)

```
User opens tab
  → ui/*.py calls calculations.py functions
    → calculations.py reads from db.py (load_* functions)
      → db.py queries data/telerrad.db via st.connection
    → calculations.py returns dict of stats
  → ui/*.py passes stats to charts.py factory functions
    → charts.py uses chart_colors.py palette
    → returns plotly Figure objects
  → ui/*.py renders with st.plotly_chart() + st.metric()

If on "Análise" tab:
  → ui/analysis.py passes stats dict to llm_client.py
    → llm_client.py sends prompt to Ollama Cloud
    → on success: returns LLM insight text
    → on failure/timeout: returns insights_rules.py fallback
  → ui/analysis.py renders insight card
```

### 1.3 Data Flow (Write Path)

```
User fills sidebar form, clicks "Salvar"
  → ui/sidebar.py validates inputs (>= 0, date valid)
  → calls db.upsert_daily(date, rm, tc, rx)
    → db.py executes UPSERT on daily_production table
  → st.toast("✅ Produção salva!")
  → st.rerun() triggers full dashboard refresh
```

### 1.4 Module Responsibility Boundaries

| Module | Responsibility | Must NOT do |
|---|---|---|
| `db.py` | SQLite schema init, CRUD, UPSERT, `st.connection` setup | No calculations, no UI, no formatting |
| `calculations.py` | Projections, moving averages, % goal, daily targets, WoW/MoM | No DB access (receives DataFrames), no charts |
| `charts.py` | Plotly figure factory functions | No data loading, no business logic |
| `chart_colors.py` | Single `CHART_COLORS` dict — the design palette | Nothing else |
| `llm_client.py` | Ollama Cloud HTTP call, timeout, error handling | No UI rendering, no data processing |
| `insights_rules.py` | Threshold-based text generation in Portuguese | No DB, no charts, no API calls |
| `ui/sidebar.py` | Input form, save button, date picker | No calculations, no chart building |
| `ui/today.py` | Today tab: KPI row, modality breakdown, today insight | No month-level aggregation |
| `ui/month.py` | Month tab: progress gauge, daily earnings trend, donut | No WoW/MoM comparisons (those are analysis) |
| `ui/analysis.py` | Analysis tab: LLM insight, moving averages, WoW/MoM, mix evolution | No data entry |
| `ui/settings.py` | Config tab: price inputs, goal input, danger zone | No business logic |
| `app.py` | Tab orchestration, session state init, theme, page config | No business logic, no raw queries |

---

## 2. Sprint Breakdown

### Phase 1 — Foundation & Data Entry (2–3 days)

**Goal**: Running app with sidebar input that persists to SQLite. Empty state visible.

| # | Task | File(s) | Details | Est. | Depends |
|---|---|---|---|---|---|
| 1.1 | Create project skeleton | `.streamlit/config.toml`, `.env.example`, `.gitignore`, `requirements.txt`, `README.md` | Copy config.toml from DESIGN_SPEC §7.3. Write .gitignore for .env, data/*.db, __pycache__, .streamlit/secrets.toml. Write requirements.txt from RESEARCH §8. | 0.5h | — |
| 1.2 | Install dependencies | Terminal | `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` | 0.25h | 1.1 |
| 1.3 | Create `src/db.py` — schema, connection, UPSERT | `src/db.py` | `create_tables(conn)` — 3 tables from RESEARCH §5.1. `get_connection()` — returns `st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")`. `upsert_daily(conn, date, rm, tc, rx)`. `load_daily(conn, date)`. `load_month(conn, year_month_str)`. `load_prices(conn)`. `save_prices(conn, rm, tc, rx)`. `load_goal(conn, year_month)`. `save_goal(conn, year_month, goal)`. | 3h | 1.2 |
| 1.4 | Create `src/__init__.py` and `src/ui/__init__.py` | Both files | Empty init files for package imports. | 0.1h | 1.3 |
| 1.5 | Create `src/chart_colors.py` | `src/chart_colors.py` | Copy the `CHART_COLORS` dict verbatim from DESIGN_SPEC §9. | 0.25h | — |
| 1.6 | Create `src/ui/sidebar.py` | `src/ui/sidebar.py` | `render_sidebar()` function. Layout per DESIGN_SPEC §4.4: app title, personal greeting ("Olá, Galvani 👋"), date input (DD/MM/YYYY format), 3 number_inputs in `st.columns(3)`, save button with `type="primary"`, divider, version caption. Button writes to `st.session_state` then calls `db.upsert_daily()`. Toast on save per DESIGN_SPEC §8.5. | 2h | 1.3 |
| 1.7 | Create `app.py` — shell with tabs | `app.py` | `st.set_page_config(page_title="radtracker", page_icon="📊", layout="wide")`. Init `st.connection`. Create 4 tabs per DESIGN_SPEC §5.1. Each tab imports and calls its `render_*()` stub (just `st.write("Em breve")`). Call `render_sidebar()`. | 1h | 1.6 |
| 1.8 | Smoke test | Terminal | `streamlit run app.py`. Verify: sidebar visible, date defaults to today, can enter numbers and click save, toast appears, tabs render, no import errors. | 0.5h | 1.7 |

**Phase 1 Definition of Done**:
- [ ] `streamlit run app.py` starts without errors
- [ ] Sidebar renders with date picker, 3 number inputs, save button
- [ ] Clicking "Salvar" inserts/updates a row in `data/telerrad.db`
- [ ] Toast notification confirms save
- [ ] Four tabs visible (all show placeholder)
- [ ] `.env.example` and `.gitignore` exist and are correct

---

### Phase 2 — "Hoje" Tab (1–2 days)

**Goal**: Today's KPI cards, modality breakdown, estimated hours. The core dashboard comes alive.

| # | Task | File(s) | Details | Est. | Depends |
|---|---|---|---|---|---|
| 2.1 | Create `src/calculations.py` — daily stats | `src/calculations.py` | `compute_daily_stats(conn, date)` → dict with: `{earnings_today, exam_count, rm_count, tc_count, rx_count, estimated_hours, estimated_time_range, yesterday_earnings, delta_pct}`. Computes earnings = RM*35 + TC*25 + RX*4.5 (default prices). Hours = RM/7.5 + TC/7.5 + RX/75 (midpoints). Time range string. | 3h | 1.3 |
| 2.2 | Add `load_settings()` to `src/db.py` | `src/db.py` | Returns dict `{rm_price, tc_price, rx_price, monthly_goal}`. Falls back to defaults if table empty (DESIGN_SPEC §4.7). | 0.5h | 1.3 |
| 2.3 | Update `calculations.py` to use actual prices | `src/calculations.py` | Accept prices dict as parameter. `compute_daily_stats(conn, date, prices)`. | 0.5h | 2.2 |
| 2.4 | Create `src/charts.py` — modality donut | `src/charts.py` | `build_modality_donut(rm, tc, rx)` — Plotly pie with `hole=0.4`, modality colors from `CHART_COLORS`, labels in Portuguese ("RM", "TC", "RX"). Design spec §4.5. | 1h | 1.5 |
| 2.5 | Create `src/charts.py` — daily earnings trend (sparkline) | `src/charts.py` | `build_daily_sparkline(df)` — 7-day mini line chart (height=250px), primary teal color, minimal margins. For reference on the Today tab. | 0.5h | 2.4 |
| 2.6 | Create `src/ui/today.py` | `src/ui/today.py` | `render_today_tab(conn)`. Layout per DESIGN_SPEC §4.1: 4 KPI cards in `st.columns(4)` using `st.metric`. Empty state per DESIGN_SPEC §4.6 (when no data for today). Modality pill indicators per §4.1a. Modality donut chart below KPI row. Insight card area (placeholder for Phase 4/5). | 3h | 2.1, 2.4, 2.5 |
| 2.7 | Integrate into `app.py` | `app.py` | Replace "Hoje" tab stub with `render_today_tab(conn)`. | 0.25h | 2.6 |
| 2.8 | Manual test with real data entry | Browser | Enter RM=8, TC=6, RX=35, save. Verify: KPI cards show correct earnings (8×35 + 6×25 + 35×4.5 = R$ 587.50), exam count = 49, hours ≈ 3.2h, donut shows 3 slices with correct proportions. | 0.5h | 2.7 |

**Phase 2 Definition of Done**:
- [ ] 4 KPI cards render with correct values after data entry
- [ ] Faturamento card shows R$ formatted value + delta vs yesterday
- [ ] Exames card shows total + modality-colored pill indicators
- [ ] Horas Estimadas card shows decimal hours + time range
- [ ] Meta Mensal card shows percentage + "R$ X / R$ 45.000"
- [ ] Modality donut chart renders with correct colors and proportions
- [ ] Empty state shows when no data for today
- [ ] Delta color: green for positive, red for negative

---

### Phase 3 — "Mês Atual" Tab (2–3 days)

**Goal**: Monthly progress gauge, daily earnings trend line, modality distribution for the month.

| # | Task | File(s) | Details | Est. | Depends |
|---|---|---|---|---|---|
| 3.1 | Extend `src/calculations.py` — monthly stats | `src/calculations.py` | `compute_monthly_stats(conn, year_month, goal)` → dict with: `{mtd_earnings, pct_goal, days_worked, total_work_days, remaining_work_days, daily_avg, daily_target_needed, projection_month_end, working_days_left}`. Uses `CustomBusinessDay(weekmask='Mon Tue Wed Thu Fri Sat')` from RESEARCH §4.2. | 2h | 2.1 |
| 3.2 | Add `load_month_daily(conn, year_month)` to `src/db.py` | `src/db.py` | Returns DataFrame of all daily rows for the month, date as index, with computed `earnings` column. Used by charts. | 0.5h | 1.3 |
| 3.3 | Create `src/charts.py` — monthly progress gauge | `src/charts.py` | `build_progress_gauge(pct_goal)` — Plotly horizontal stacked bar with 4 milestone segments per DESIGN_SPEC §4.2. Segments: 0–25% danger red, 25–50% warning amber, 50–75% on-track teal, 75–100% achieved green. Marker at current position. | 1.5h | 1.5, 3.1 |
| 3.4 | Create `src/charts.py` — daily earnings trend | `src/charts.py` | `build_monthly_earnings_chart(df)` — Plotly line chart for all days in month. Teal (#0D9488) line for actual earnings. Dashed horizontal line for daily target. Vertical dashed line for "today". Height 400px. | 1h | 3.2 |
| 3.5 | Create `src/charts.py` — monthly modality donut | `src/charts.py` | `build_monthly_modality_donut(df)` — Pie with `hole=0.4` using modality colors, showing RM/TC/RX revenue share for the month. | 0.5h | 3.2 |
| 3.6 | Add `compute_daily_target(monthly_goal, working_days)` to `src/calculations.py` | `src/calculations.py` | Helper function: daily target = monthly_goal / total_working_days_in_month. | 0.25h | 3.1 |
| 3.7 | Create `src/ui/month.py` | `src/ui/month.py` | `render_month_tab(conn)`. Layout per DESIGN_SPEC §5.1: KPI row (monthly earnings, % goal, days worked, daily avg), progress gauge, two-column chart row (daily earnings line + modality donut). Rhythm alerts: warning banner if behind pace (DESIGN_SPEC §6.2 warning tone). Empty state if month has no data. | 3h | 3.1, 3.3, 3.4, 3.5 |
| 3.8 | Integrate into `app.py` | `app.py` | Replace "Mês Atual" tab stub with `render_month_tab(conn)`. | 0.25h | 3.7 |
| 3.9 | Test with multi-day data | Manual + script | Insert 10–15 days of varied data. Verify: progress gauge shows correct % and correct color segment, daily earnings line plots all points, donut splits correctly, remaining days calculation is right, daily target line shows. | 1h | 3.8 |

**Phase 3 Definition of Done**:
- [ ] Monthly KPI row: earnings MTD, % goal, days worked/remaining, daily average
- [ ] Progress gauge with 4 color segments, correct position marker
- [ ] Daily earnings line chart with today marker and target line
- [ ] Modality donut for the month
- [ ] Behind-pace warning banner when applicable
- [ ] Works for any month in 2026 (not just current)

---

### Phase 4 — "Análise & Insights" Tab (2–3 days)

**Goal**: Moving averages, WoW/MoM comparisons, rule-based insights, historical trends.

| # | Task | File(s) | Details | Est. | Depends |
|---|---|---|---|---|---|
| 4.1 | Create `src/insights_rules.py` | `src/insights_rules.py` | `generate_rule_insights(stats: dict) -> str`. Music-based (DESIGN_SPEC §6.3). Checks: pct_goal against thresholds (≥75% success, 50-75% on-track, 25-50% warning, <25% danger), WoW trend direction, modality mix shift >10%, consecutive below-target days. Returns Portuguese text blocks with emoji indicators. Template strings, not concatenated. | 3h | — |
| 4.2 | Extend `src/calculations.py` — historical stats | `src/calculations.py` | `compute_historical_stats(conn)` → dict: `{ma7, ma30, wow_change_pct, mom_change_pct, weekly_totals_last_4, modality_mix_current, modality_mix_historical, consecutive_below_target}`. Rolling averages with `min_periods=1`. | 2h | 3.1 |
| 4.3 | Create `src/charts.py` — moving averages chart | `src/charts.py` | `build_moving_averages_chart(df)` — two lines: MA7 (teal, solid, fill-to-zero at 10% opacity) + MA30 (muted gray, dashed). Height 400px. | 1h | 1.5 |
| 4.4 | Create `src/charts.py` — WoW comparison chart | `src/charts.py` | `build_wow_comparison_chart(weekly_data)` — grouped bar chart: current week in modality colors, previous week in lighter/muted variants. Side-by-side per modality. | 1h | 1.5 |
| 4.5 | Create `src/charts.py` — modality mix evolution | `src/charts.py` | `build_modality_mix_evolution(monthly_mix_history)` — stacked area chart showing RM/TC/RX % over months. Modality colors. Height 350px. | 1h | 1.5 |
| 4.6 | Create `src/ui/analysis.py` | `src/ui/analysis.py` | `render_analysis_tab(conn)`. Layout per DESIGN_SPEC §5.1: Insight card at top (rule-based for now — Phase 5 adds LLM). Below: two-column chart row (moving averages + WoW comparison). Third row: modality mix evolution chart. Insight card styled per DESIGN_SPEC §4.3 (light gray card, teal left border, 💡 icon). | 3h | 4.1, 4.2, 4.3, 4.4, 4.5 |
| 4.7 | Integrate into `app.py` | `app.py` | Replace "Análise" tab stub with `render_analysis_tab(conn)`. | 0.25h | 4.6 |
| 4.8 | Test with 2+ months of synthetic data | Manual | Generate data across 8 weeks. Verify: MA7 responds faster than MA30, WoW bars compare correctly, modality mix evolution trends are visible, rule insight text changes based on actual data state (test below-target, on-target, above-target). | 1h | 4.7 |

**Phase 4 Definition of Done**:
- [ ] Moving averages chart with MA7 (teal) and MA30 (gray dashed)
- [ ] WoW grouped bar chart comparing current vs previous week per modality
- [ ] Modality mix evolution stacked area chart
- [ ] Rule-based insight card renders in Portuguese with actionable text
- [ ] Insight changes tone based on actual data (success/warning/danger)
- [ ] Insight mentions Galvani by name
- [ ] Empty/historical data edge cases handled (e.g., <7 days of data → MA7 = available mean)

---

### Phase 5 — LLM Integration & Settings (1–2 days)

**Goal**: Optional LLM insights via Ollama Cloud, settings tab for prices and goals, light/dark theme.

| # | Task | File(s) | Details | Est. | Depends |
|---|---|---|---|---|---|
| 5.1 | Create `src/llm_client.py` | `src/llm_client.py` | `generate_llm_insights(stats: dict) -> str`. RESEARCH §6.3 pattern. Reads `OLLAMA_API_KEY` from env (via `python-dotenv`). 15s timeout. Prompt template from RESEARCH §6.5. Model: `deepseek-v4-flash:cloud`. Returns insight text or raises `LLMUnavailableError`. | 2h | 4.1 |
| 5.2 | Implement LLM fallback logic | `src/ui/analysis.py` | Try `generate_llm_insights()`. On success: render with "🤖 Gerado por DeepSeek V4" caption. On `LLMUnavailableError` or timeout: render rule-based insights with `st.info("🤖 Insight automático (LLM indisponível)")` banner per DESIGN_SPEC §8.3. Wrap in `st.spinner("🧠 Gerando insights com DeepSeek V4...")`. | 1h | 5.1 |
| 5.3 | Create `src/ui/settings.py` | `src/ui/settings.py` | `render_settings_tab(conn)`. Layout per DESIGN_SPEC §4.7: Three `st.number_input` for prices (RM/TC/RX, R$ format, step 0.01). One `st.number_input` for monthly goal (R$). Save button → `db.save_prices()` + `db.save_goal()`. Danger zone: delete all data button with confirmation (st.warning + second click). | 2h | 1.3 |
| 5.4 | Wire settings changes to calculations | `src/calculations.py`, `app.py` | Ensure `load_settings()` is called once at app start, stored in `st.session_state.settings`. All `compute_*` functions read from session_state. Settings tab updates both DB and session_state on save. | 1h | 5.3 |
| 5.5 | Verify `.streamlit/config.toml` | `.streamlit/config.toml` | Ensure file matches DESIGN_SPEC §7.3 exactly. Light theme default, dark theme block. Test theme switch via Streamlit Settings menu (☰ → Settings → Theme). | 0.5h | 1.1 |
| 5.6 | Add theme-aware chart colors | `src/chart_colors.py`, `src/charts.py` | Ensure Plotly charts use `paper_bgcolor='rgba(0,0,0,0)'` (transparent) so they inherit Streamlit's theme. No hardcoded white/dark backgrounds in Plotly figures. | 0.5h | 5.5 |
| 5.7 | End-to-end test of full app | Manual | Full workflow: open app, enter data, check all tabs, change prices, verify calculations update, toggle theme, check chart visibility, simulate LLM key missing → verify fallback, simulate LLM key present → verify real insight. | 1h | All above |

**Phase 5 Definition of Done**:
- [ ] Settings tab saves prices and goal to DB, session_state updates immediately
- [ ] Changing RM price from R$35 to R$40 updates all earnings calculations on next save
- [ ] LLM insights appear with spinner when `OLLAMA_API_KEY` is set
- [ ] Fallback rule insights appear when key is absent or API fails
- [ ] Dark theme toggle works and charts remain legible
- [ ] "Limpar todos os dados" requires confirmation and actually deletes all rows

---

### Phase 6 — Testing, Polish & Release (1–2 days)

**Goal**: Test suite, README, final validation, GitHub push.

| # | Task | File(s) | Details | Est. | Depends |
|---|---|---|---|---|---|
| 6.1 | Create `tests/conftest.py` | `tests/conftest.py` | Fixtures: `in_memory_db()` — creates SQLite :memory: with full schema, yields connection. `sample_daily_data()` — inserts 30 days of varied production data. `sample_prices()` — inserts default prices. `sample_stats_dict()` — returns a dict matching `compute_monthly_stats` output for insight tests. | 1h | 1.3 |
| 6.2 | Create `tests/test_db.py` | `tests/test_db.py` | Tests: `test_create_tables` (all 3 tables exist), `test_upsert_insert` (new row), `test_upsert_update` (overwrites existing), `test_upsert_preserves_created_at` (created_at unchanged on update, updated_at changes), `test_load_daily_nonexistent` (returns empty), `test_load_month` (correct date range), `test_save_and_load_prices`, `test_save_and_load_goal`. Use in-memory SQLite, direct `sqlite3` (not st.connection — unit tests don't need Streamlit). | 2h | 6.1 |
| 6.3 | Create `tests/test_calculations.py` | `tests/test_calculations.py` | Tests: `test_daily_stats_with_known_data` (RM=10,TC=10,RX=10 = R$645), `test_daily_stats_empty` (zeros), `test_daily_stats_delta_positive`, `test_daily_stats_delta_negative`, `test_estimated_hours` (midpoint formula), `test_monthly_stats_pct_goal`, `test_remaining_work_days` (excludes Sundays), `test_daily_target`, `test_projection`, `test_ma7_first_7_days`, `test_ma30_insufficient_data`, `test_wow_change`, `test_modality_mix`. Use `sample_daily_data` fixture. | 3h | 6.1, 2.1, 3.1, 4.2 |
| 6.4 | Create `tests/test_insights.py` | `tests/test_insights.py` | Tests: `test_rule_insights_above_target` (≥75% → success tone), `test_rule_insights_on_track` (50–75% → teal/normal tone), `test_rule_insights_warning` (25–50% → warning tone), `test_rule_insights_danger` (<25% → danger tone), `test_rule_insights_contains_galvani_name`, `test_rule_insights_has_actionable_suggestion`, `test_rule_insights_empty_data`. | 1.5h | 6.1, 4.1 |
| 6.5 | Create `tests/__init__.py` | `tests/__init__.py` | Empty init file. | 0.05h | — |
| 6.6 | Run full test suite | Terminal | `python -m pytest tests/ -v`. Ensure ≥80% coverage on calculations.py, db.py, insights_rules.py. Fix any failures. | 1h | 6.2, 6.3, 6.4 |
| 6.7 | Write `README.md` | `README.md` | Sections: What is radtracker, features, prerequisites (Python 3.12+), quick start (clone, venv, pip install, cp .env.example .env, streamlit run app.py), optional LLM setup, project structure, tech stack, license (MIT). Portuguese UI note, English code note. | 1h | All |
| 6.8 | Final `.gitignore` audit | `.gitignore` | Ensure: `.env`, `data/*.db`, `__pycache__/`, `*.pyc`, `.streamlit/secrets.toml`, `venv/`. Verify with `git status` that no secrets or generated files are tracked. | 0.25h | 6.7 |
| 6.9 | Tag v1.0.0 and push to GitHub | Terminal | `git tag v1.0.0 -m "Initial release: dashboard de produtividade para telerradiologia"`. Push with tags. | 0.25h | 6.8 |

**Phase 6 Definition of Done**:
- [ ] `pytest` passes all tests with ≥80% coverage on core logic modules
- [ ] `README.md` exists with clear setup instructions
- [ ] `.gitignore` prevents secrets and generated files from being tracked
- [ ] No hardcoded secrets in any committed file
- [ ] Git tag v1.0.0 pushed to remote
- [ ] Full user workflow verified: install → configure → enter data → see insights

---

## 3. Implementation Order

### 3.1 Sequential Dependency Chain

```
Phase 1 (Foundation)
  → Phase 2 (Today tab)
    → Phase 3 (Month tab)
      → Phase 4 (Analysis tab)
        → Phase 5 (LLM + Settings)
          → Phase 6 (Tests + Release)
```

Each phase builds on the previous. Phase 1's `db.py` is the foundation for everything.

### 3.2 Parallelizable Work

Within each phase, these tasks can run in parallel:

**Phase 1**: 1.5 (chart_colors.py) is independent and can be done alongside 1.3 (db.py).

**Phase 2**: 2.4 and 2.5 (chart factory functions) can run parallel to 2.1 and 2.2 (calculations), since charts receive data as parameters — they don't need the calculations module to exist first.

**Phase 4**: 4.1 (insights_rules.py) has zero dependencies and can be built in parallel with 4.2 (historical calculations). Charts 4.3–4.5 can run in parallel once 4.2 is done.

**Phase 5**: 5.1 (llm_client.py) and 5.3 (settings.py) are completely independent of each other.

**Phase 6**: All test files (6.2, 6.3, 6.4) can be written in parallel after conftest (6.1) is done.

### 3.3 What Blocks What

| Blocked | Blocked By | Reason |
|---|---|---|
| `ui/today.py` | `db.py`, `calculations.py`, `charts.py` | Needs data loading, stats computation, chart figures |
| `ui/month.py` | `db.py` (load_month), `calculations.py` (monthly_stats), `charts.py` (gauge, line, donut) | Needs monthly aggregation and multi-chart rendering |
| `ui/analysis.py` | `insights_rules.py`, `calculations.py` (historical), `charts.py` (MA, WoW, mix evolution) | Needs historical stats, rule insights, complex charts |
| LLM insight rendering | `llm_client.py`, `insights_rules.py` (fallback) | Both must exist for graceful degradation |
| Settings affecting calculations | `db.py` (load_settings, save_settings), `ui/settings.py` | Prices/goal must be savable and loadable before they can affect calculations |
| All tests | Respective source modules | Tests validate the module; module must exist first |

### 3.4 Critical Path

```
db.py → calculations.py → ui/today.py → ui/month.py → ui/analysis.py → llm_client.py → tests
                                                                         → settings.py
```

Total critical path: **~10–15 days** (single developer, factoring in testing and integration).

---

## 4. Testing Strategy

### 4.1 Philosophy

- **Behavior only**: Test what the function does, not how it does it.
- **No Streamlit in unit tests**: `db.py`, `calculations.py`, `insights_rules.py`, and `llm_client.py` are tested with pure Python. Streamlit UI modules (`ui/*.py`) are tested manually (dashboard visual verification) since they're thin wrappers around tested logic.
- **In-memory SQLite**: All database tests use `sqlite3.connect(":memory:")` — fast, isolated, no file cleanup needed.
- **Named fake classes**: Mock the Ollama client with a `FakeOllamaClient` class, not inline stubs.

### 4.2 Per-Module Test Plan

#### `tests/test_db.py`

| Test | What it verifies | Technique |
|---|---|---|
| `test_create_tables` | All 3 tables exist after `create_tables()` | Query `sqlite_master` |
| `test_upsert_insert` | First save creates a row | Count before/after, verify values |
| `test_upsert_update` | Second save on same date overwrites values | Insert, then upsert, verify new values, verify row count = 1 |
| `test_upsert_preserves_created_at` | `created_at` doesn't change on update, `updated_at` does | Compare timestamps before/after update |
| `test_load_daily_exists` | Returns correct row for a given date | Insert known data, load, assert dict equality |
| `test_load_daily_nonexistent` | Returns None or empty for missing date | Load non-existent date, assert empty |
| `test_load_month_returns_correct_rows` | Only rows matching year-month pattern | Insert rows across 2 months, load one, assert count |
| `test_save_and_load_prices` | Round-trip: save prices, load them back | Save, load, assert dict equality |
| `test_load_prices_defaults` | Returns defaults when table is empty | Load from fresh DB, assert default prices |
| `test_save_and_load_goal` | Round-trip: save goal, load it back | Save, load, assert equality |

**Test DB**: In-memory SQLite. Each test gets a fresh connection with tables created via `create_tables()`.

#### `tests/test_calculations.py`

| Test | What it verifies | Technique |
|---|---|---|
| `test_daily_earnings_calculation` | RM×35 + TC×25 + RX×4.5 | Known inputs → known output |
| `test_daily_earnings_with_custom_prices` | Uses prices dict, not hardcoded defaults | Pass custom prices, verify calculation |
| `test_estimated_hours_midpoint` | Hours = RM/7.5 + TC/7.5 + RX/75 | Known counts → known hours |
| `test_estimated_time_range` | Returns "~HH:MM – HH:MM" string | Fixed start time (08:00), verify end time |
| `test_delta_positive` | Delta string when today > yesterday | Insert higher today, lower yesterday |
| `test_delta_negative` | Delta string when today < yesterday | Insert lower today, higher yesterday |
| `test_delta_zero` | Delta when no yesterday data | No yesterday row → delta shows "—" |
| `test_monthly_pct_goal` | MTD / goal × 100 | Known MTD and goal → known % |
| `test_remaining_work_days_includes_saturday` | Saturdays count as work days | April 2026 has 26 work days (Mon–Sat) |
| `test_remaining_work_days_excludes_sunday` | Sundays excluded | Verify no Sunday in date_range output |
| `test_daily_target` | Monthly goal ÷ working days | 45000 ÷ 26 ≈ 1730.77 |
| `test_projection` | (avg_daily × remaining_days) + mtd | Known values → known projection |
| `test_ma7_first_7_days` | MA7 with <7 data points uses available mean | 3 days → MA7 = mean of those 3 |
| `test_ma7_rolling` | MA7 after 10 days has 10 values | Verify length, verify last value is mean of days 4-10 |
| `test_ma30_insufficient_data` | MA30 with <30 points uses available mean | 5 days → MA30 = mean of 5 |
| `test_wow_change_positive` | Positive WoW % | This week higher than last → positive % |
| `test_wow_change_negative` | Negative WoW % | This week lower → negative % |
| `test_modality_mix` | RM% + TC% + RX% = 100% | Known counts → known percentages |
| `test_modality_mix_single_modality` | One modality = 100% | Only RM data → RM=100% |

**Test DB**: Use `conftest.py` fixtures that pre-populate in-memory SQLite with known data.

#### `tests/test_insights.py`

| Test | What it verifies | Technique |
|---|---|---|
| `test_success_tone` | pct_goal ≥ 75 → "acima da meta" or similar | Pass stats with 80% goal |
| `test_warning_tone` | 25 ≤ pct_goal < 50 → "atenção" or "abaixo" | Pass stats with 35% goal |
| `test_danger_tone` | pct_goal < 25 → "crítico" or "alerta" | Pass stats with 15% goal |
| `test_contains_galvani` | Output includes "Galvani" | Assert substring |
| `test_has_specific_numbers` | Output includes actual numbers from stats | Pass R$ 18.450, assert it appears in output |
| `test_actionable_suggestion` | Output contains a recommendation ("faça", "considere", "sugestão") | Assert one of the directive words |
| `test_insight_with_empty_data` | Handles null/zero gracefully | Pass all-zero stats, assert no crash |
| `test_insight_language` | Output is in Portuguese | Assert no English words ("you", "goal", "target") in output |

**No DB needed**: `generate_rule_insights()` takes a dict, returns a string. Pure function.

#### Manual Tests (UI Verification)

These are checked manually — not automated:

| Tab | What to verify |
|---|---|
| Sidebar | Date picker defaults to today, numbers accept 0+, save button triggers toast, re-saving overwrites |
| Hoje | KPI cards show correct values, donut proportions match inputs, empty state when no data |
| Mês | Progress gauge segments at correct %, daily earnings line plots all days, donut matches month totals |
| Análise | MA7 and MA30 lines render, WoW bars compare correctly, insight text changes with data |
| Config | Price inputs save and reload, goal saves and reloads, danger zone delete works with confirmation |
| Theme | Light ↔ dark toggle works, charts remain legible, text contrast adequate |

### 4.3 Test Execution

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
pip install pytest-cov
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Target: ≥80% coverage on src/db.py, src/calculations.py, src/insights_rules.py
```

---

## 5. Risk Log

| ID | Risk | Probability | Impact | Mitigation | Contingency |
|---|---|---|---|---|---|
| R1 | **Ollama Cloud API breaking changes** — API endpoint, auth format, or model name changes, breaking `llm_client.py` | Medium (30%) | Low — LLM is optional "plus" | Pin `ollama` package version in `requirements.txt`. Wrap client in thin interface (`LLMClient` class) so API changes are localized to one file. | Fallback to `insights_rules.py` is automatic. LLM failure shows info banner, never crashes app. |
| R2 | **Ollama Free plan rate limit hit** — more than ~50 calls/day triggers 429 errors | Low (10%) | Low — only affects insight quality, not core functionality | Cache LLM responses per day (don't re-call if stats unchanged). Throttle: max 1 LLM call per 5 minutes. | Same as R1: rule-based fallback. Option to switch to DeepSeek API direct (~$0.05/mo). |
| R3 | **Streamlit API deprecation** — `st.connection` or `st.metric` behavior changes in version >1.54 | Low (15%) | Medium — could break data loading or KPI rendering | Pin `streamlit>=1.54.0,<2.0.0`. Check changelog before upgrading. | `st.connection` can be replaced with manual `sqlite3` connection. `st.metric` can be replaced with custom HTML/markdown. |
| R4 | **SQLite file corruption** — power loss or disk full during write | Very low (5%) | High — data loss for personal finance tool | `data/` directory is gitignored. Document backup in README: "Copy `data/telerrad.db` to backup." Consider adding `PRAGMA journal_mode=WAL` for crash safety. | User restores from manual backup. Low data volume (~365 rows/year) makes re-entry feasible. |
| R5 | **Schema migration needed** — future feature requires new columns | Medium (40%) | Low — single user, single file, schema is simple | Use `CREATE TABLE IF NOT EXISTS` with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern in `create_tables()`. Incremental migrations, not destructive. | Manual SQLite ALTER TABLE if needed. Schema is 3 tables with ~6 columns each — manageable. |
| R6 | **Business day miscalculation** — wrong work days count skews daily target and projection | Medium (25%) | Medium — user makes decisions based on wrong numbers | Unit test `remaining_work_days` extensively: verify excludes Sundays, includes Saturdays, handles month boundaries. Test with April 2026 (has 26 Mon–Sat days). | If bug found, fix in `calculations.py` and re-run tests. User can manually verify against calendar. |
| R7 | **Portuguese text quality from LLM** — DeepSeek generates awkward or incorrect Portuguese | Medium (30%) | Low — rule-based fallback is always available | Prompt includes "em português, tom amigável e direto". Use `temperature=0.3` for consistency. Review first 10 LLM outputs manually. | If LLM output is poor, disable LLM via config flag. Rule-based insights are in hand-crafted Portuguese. |
| R8 | **Streamlit limitations** — per DESIGN_SPEC §7.4: no multi-color st.progress, no custom fonts, per-component color limits | Certain (100%) | Low — workarounds documented | Use Plotly for progress gauge (not st.progress). Accept system font stack. Use custom markdown for amber deltas. All workarounds in DESIGN_SPEC §7.4. | N/A — workarounds are built into the design. |

---

## 6. Definition of Done per Phase

### Phase 1 — Foundation & Data Entry

- [ ] `streamlit run app.py` starts without errors on Ubuntu with Python 3.12
- [ ] Sidebar renders with: app title "📊 radtracker", greeting "Olá, Galvani 👋", date picker (DD/MM/YYYY, defaults to today), 3 number inputs (RM, TC, RX) in 3-column layout, 💾 Save button (full-width, primary color)
- [ ] Clicking "Salvar" inserts a row into `data/telerrad.db` table `daily_production`
- [ ] Clicking "Salvar" again on the same date updates the existing row (UPSERT, not duplicate)
- [ ] Toast notification "✅ Produção de DD/MM salva!" appears after save
- [ ] Four tabs visible: 📊 Hoje, 📅 Mês Atual, 📈 Análise, ⚙️ Config (all show placeholder text)
- [ ] `.env.example` lists `OLLAMA_API_KEY=your_key_here` with setup instructions
- [ ] `.gitignore` excludes `.env`, `data/*.db`, `__pycache__/`, `*.pyc`, `.streamlit/secrets.toml`, `venv/`
- [ ] `requirements.txt` installs cleanly with `pip install -r requirements.txt`

### Phase 2 — "Hoje" Tab

- [ ] 4 KPI cards in a horizontal `st.columns(4)` row:
  - 💰 Faturamento hoje: R$ formatted value + delta % vs yesterday (green ↑ / red ↓)
  - 📋 Exames hoje: total count + modality-colored pill indicators (RM ●8 · TC ●10 · RX ●6)
  - ⏱️ Horas estimadas: decimal hours + "~HH:MM – HH:MM" time range
  - 🎯 Meta mensal: percentage + "R$ MTD / R$ GOAL"
- [ ] Delta shows "—" when no yesterday data exists (first day)
- [ ] Modality donut chart below KPI row: 3 slices with correct colors (RM=#2563EB, TC=#D97706, RX=#0891B2), hole=0.4, labels in Portuguese, legend visible
- [ ] Empty state card shows when no data for selected date: centered, friendly message, arrow pointing to sidebar
- [ ] All monetary values formatted as Brazilian reais: "R$ 1.250,00"

### Phase 3 — "Mês Atual" Tab

- [ ] Monthly KPI row: Faturamento acumulado, % da meta (with color: green/amber/red), dias trabalhados/de N, média diária
- [ ] Monthly progress gauge: horizontal stacked bar with 4 color segments (red 0–25%, amber 25–50%, teal 50–75%, green 75–100%), marker at current position, percentage label
- [ ] Daily earnings line chart: teal line for each day's earnings, dashed gray line for daily target, vertical "hoje" marker, x-axis labeled with day numbers
- [ ] Monthly modality donut: revenue share per modality for the month
- [ ] Warning banner appears when behind pace (yellow info box with specific gap numbers)
- [ ] Behind-pace message includes: how much is missing, required daily rate, days remaining

### Phase 4 — "Análise & Insights" Tab

- [ ] Insight card at top: styled per DESIGN_SPEC (light gray background, teal 4px left border, 💡 icon)
- [ ] Insight text addresses Galvani by name, uses specific numbers, offers actionable suggestions
- [ ] Moving averages chart: teal solid line (MA7) with 10% opacity fill, muted gray dashed line (MA30)
- [ ] WoW comparison grouped bar chart: current week in modality colors, previous week in muted tones
- [ ] Modality mix evolution stacked area chart: shows RM/TC/RX percentage over months
- [ ] Insight tone adapts to data: success (≥75%) vs on-track (50–75%) vs warning (25–50%) vs danger (<25%)
- [ ] Edge cases: <7 days data → MA7 = available mean; no previous week → WoW shows "sem dados"

### Phase 5 — LLM & Settings

- [ ] Settings tab saves RM/TC/RX prices and monthly goal to `exam_prices` and `monthly_goals` tables
- [ ] Changing RM price from R$35.00 to R$40.00 and saving updates all earnings calculations immediately (verified on Hoje tab after re-save)
- [ ] When `OLLAMA_API_KEY` is set in `.env`: opening Análise tab shows `st.spinner`, then LLM-generated insight with "🤖 Gerado por DeepSeek V4" caption
- [ ] When `OLLAMA_API_KEY` is missing or invalid: Análise tab shows `st.info` banner "🤖 Insight automático (LLM indisponível)" + rule-based insight text
- [ ] LLM timeout (>15s) triggers fallback gracefully — no app crash, no hang
- [ ] Dark theme toggle works via Streamlit Settings menu → Theme → Dark
- [ ] Charts remain legible in dark mode (transparent backgrounds, adequate text contrast)
- [ ] "🗑️ Limpar todos os dados" shows warning, requires second click, then deletes all rows from all tables

### Phase 6 — Tests & Release

- [ ] `python -m pytest tests/ -v` exits with 0 failures
- [ ] Test coverage ≥80% on `src/db.py`, `src/calculations.py`, `src/insights_rules.py`
- [ ] `README.md` includes: project description, prerequisites, setup steps (5 commands), optional LLM config, project structure diagram, tech stack, license
- [ ] `git status` shows no untracked secrets, no `.env` file, no `*.db` files
- [ ] `git tag v1.0.0` exists with descriptive message
- [ ] Full fresh-install test: clone repo → venv → pip install → cp .env.example .env → streamlit run app.py → works end-to-end

---

## 7. Environment Setup Steps

These are the exact commands to go from zero to running app. Execute in order.

```bash
# 1. Ensure Python 3.12 is available
python3 --version
# Expected: Python 3.12.3 or higher

# 2. Clone the repository
cd ~/dev
git clone <repo-url> radtracker
cd radtracker

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create environment file (for LLM — optional)
cp .env.example .env
# Edit .env with your Ollama API key from https://ollama.com/settings/keys
# OLLAMA_API_KEY=sk_xxxxxxxxxxxx

# 6. Create data directory (auto-created by app, but explicit is fine)
mkdir -p data

# 7. Run the app
streamlit run app.py
# Opens browser at http://localhost:8501
```

### 7.1 File Creation Checklist (Phase 1, Task 1.1)

Files to create manually:

| File | Source | Notes |
|---|---|---|
| `.streamlit/config.toml` | Copy from DESIGN_SPEC §7.3 | Light + dark theme |
| `.env.example` | New file | Template: `OLLAMA_API_KEY=your_key_here` |
| `.gitignore` | New file | See Phase 1 DoD for entries |
| `requirements.txt` | Copy from RESEARCH §8 | Pinned versions |
| `src/__init__.py` | New file | Empty |
| `src/ui/__init__.py` | New file | Empty |
| `tests/__init__.py` | New file | Empty |
| `data/.gitkeep` | New file | Empty file to track directory in git |

### 7.2 requirements.txt Content

```
streamlit>=1.54.0,<2.0.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
ollama>=0.4.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

---

## 8. Code Standards

### 8.1 Language Convention

| Context | Language | Rationale |
|---|---|---|
| Source code (variable names, function names, comments) | **English** | Open-source convention, searchable, consistent with Python ecosystem |
| UI text (labels, insights, buttons, metrics, toasts) | **Portuguese** | Galvani is Brazilian, the tool is personal, insights address him directly |
| Commit messages | **English** | Standard Git practice |
| Documentation (README, PLAN) | **English** | Accessible to other developers |
| Docstrings | **English** | Same as code comments |

### 8.2 Module Structure Rules

- **One responsibility per file**: `db.py` does database only, `charts.py` does chart building only, etc.
- **Files under 500 lines**: Split if approaching this limit. A 300-line `calculations.py` is fine. A 700-line `app.py` is not.
- **Functions 4–20 lines**: Extract helpers if a function grows beyond 20 lines.
- **No `import *`**: Explicit imports only. `from src.db import upsert_daily, load_daily`.
- **Type hints on public functions**: Every function called across module boundaries must have type hints.
  ```python
  def compute_daily_stats(
      conn: Any, date_str: str, prices: dict[str, float]
  ) -> dict[str, Any]:
  ```
- **No `Dict`, `List`, `Any` from typing**: Use built-in `dict`, `list`, etc. (Python 3.12+).

### 8.3 Specific Conventions

#### Database (`src/db.py`)
- Connection obtained via `st.connection("telerrad", ...)` — the Streamlit-native way.
- All functions accept `conn` as first parameter (dependency injection, not global).
- `create_tables()` is idempotent — call it on every app start.
- UPSERT uses `ON CONFLICT(date) DO UPDATE SET` syntax.

#### Calculations (`src/calculations.py`)
- Pure functions where possible: DataFrame in, dict out.
- DB-dependent functions accept connection parameter.
- No Streamlit imports (except types if needed for type hints).
- All monetary values stored and computed as `float`, formatted only at UI layer.
- Business constants: `DEFAULT_PRICES = {"rm": 35.0, "tc": 25.0, "rx": 4.5}`, `PRODUCTIVITY = {"rm": 7.5, "tc": 7.5, "rx": 75.0}` (midpoint exams/hour).

#### Charts (`src/charts.py`)
- Every function returns a `plotly.graph_objects.Figure`.
- Every function accepts data (DataFrame or scalars), never queries DB.
- Use `CHART_COLORS` from `src/chart_colors.py` — no inline hex values.
- `paper_bgcolor='rgba(0,0,0,0)'` and `plot_bgcolor='rgba(0,0,0,0)'` on all figures for theme compatibility.
- Chart titles answer a question: "Faturamento diário — Abril 2026", not "Faturamento".

#### UI Modules (`src/ui/*.py`)
- Each file exports a single `render_*_tab(conn)` or `render_sidebar()` function.
- UI modules import from `db`, `calculations`, `charts`, `insights_rules`, `llm_client` — never access DB directly.
- No business logic in UI modules. If a calculation is needed, it belongs in `calculations.py`.
- `st.session_state` used for: `today_date`, `settings` (price/goal dict), transient flags.

#### Insights (`src/insights_rules.py`, `src/llm_client.py`)
- `insights_rules.py`: pure function, dict in → string out. No side effects.
- `llm_client.py`: single class `LLMClient` wrapping the Ollama SDK. Constructor takes API key. Method `generate(stats: dict) -> str`. Raises custom `LLMUnavailableError` on failure.
- Both modules return Portuguese strings ready for `st.markdown()` rendering.

### 8.4 Error Handling

- **Database errors**: Caught in `db.py`, re-raised as specific exceptions (`DatabaseError`). UI catches and shows `st.error()`.
- **LLM errors**: Caught in `llm_client.py`, returned as `LLMUnavailableError`. UI catches and falls back.
- **User input validation**: Sidebar validates `min_value=0`, `step=1`. No negative exam counts. Date input prevents future dates via `max_value=date.today()`.
- **Exception messages**: Include the offending value and expected shape. `f"Expected non-negative int for rm_count, got {rm_count} (type {type(rm_count).__name__})"`

### 8.5 Logging

For debugging/observability (structured JSON):

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":%(message)s}',
    handlers=[logging.FileHandler("data/app.log")]
)
logger = logging.getLogger(__name__)
```

- Log: app startup, database initialization, UPSERT operations, LLM call attempts/successes/failures, configuration changes.
- Do NOT log: exam counts (privacy), API keys.
- Log file: `data/app.log` (gitignored).

### 8.6 Imports Order

Standard order within each file:
1. Standard library (`sqlite3`, `datetime`, `os`)
2. Third-party (`streamlit`, `pandas`, `plotly`, `ollama`)
3. Local (`from src.db import ...`, `from src.calculations import ...`)

One blank line between groups.

---

## Summary

| Phase | Output | Days | Key Artifact |
|---|---|---|---|
| 1 | Working sidebar + SQLite persistence | 2–3 | `app.py`, `src/db.py`, `src/ui/sidebar.py` |
| 2 | Today tab with KPIs and donut chart | 1–2 | `src/ui/today.py`, `src/calculations.py`, `src/charts.py` |
| 3 | Month tab with progress gauge and trend | 2–3 | `src/ui/month.py`, progress gauge chart |
| 4 | Analysis tab with historical stats and rule insights | 2–3 | `src/ui/analysis.py`, `src/insights_rules.py` |
| 5 | LLM integration, settings, theme toggle | 1–2 | `src/llm_client.py`, `src/ui/settings.py` |
| 6 | Test suite, README, release | 1–2 | `tests/`, `README.md`, git tag v1.0.0 |

**Total estimated**: 9–15 days (single developer, part-time).

**First runnable artifact**: End of Phase 1 — sidebar that saves to SQLite.
**First useful artifact**: End of Phase 2 — today's KPI cards and modality breakdown.
**Fully featured**: End of Phase 5 — LLM insights, configurable prices/goals, dark mode.
**Production-ready**: End of Phase 6 — tested, documented, tagged.

---

## Source Documents Reference

These four documents formed the basis for this implementation plan. Consult them when decisions about design, behavior, or implementation details arise.

| Document | Role | Content | Consult when… |
|---|---|---|---|
| [**BRIEF.md**](./BRIEF.md) | Project charter & requirements | Problem statement, user goals, functional/non-functional requirements, business rules (prices, productivity rates, monthly goal), stack decisions, UX flow, definition of done | You need the *why*: user context, constraints, workflow. Start here for any question about what the system should do. |
| [**DESIGN_SPEC.md**](./DESIGN_SPEC.md) | Visual & interaction design authority | Color palette (24 tokens), typography hierarchy mapped to Streamlit elements, component specs (KPI cards, progress bar, insight card, sidebar, charts, empty state), spacing system, tone of voice with Portuguese examples, `config.toml` themes, state handling | You need the *how it looks and feels*: chart colors, metric card layout, insight text tone, spacing between components. The definitive source for any UI decision. |
| [**RESEARCH.md**](./RESEARCH.md) | Technical feasibility & API reference | Streamlit API patterns (tabs, sidebar, `st.metric`, `st.connection`, caching), Plotly chart code examples, Pandas time-series operations, SQLite schema with UPSERT, Ollama Cloud API integration code, dependency versions | You need the *how to build it*: exact function signatures, SQL queries, prompt templates, pip package versions. Code snippets here are the implementation starting point. |
| [**DESIGN.md**](./DESIGN.md) | External design reference (Cal.com) | Cal.com's design system analyzed: color tokens, typography (Cal Sans + Inter), spacing rhythm (4px base), border radius scale, elevation levels, component library, responsive breakpoints, do's and don'ts | You need *inspiration or pattern justification*: why we use light-gray cards, why 8px border radius on buttons, why generous whitespace. Not normative — DESIGN_SPEC.md is the authority adapted from this. |

**Reading order for new contributors**:
1. BRIEF.md — understand the user and the problem
2. RESEARCH.md — see the tech stack and code patterns
3. DESIGN_SPEC.md — learn the visual language and component specs
4. DESIGN.md — optional; understand the design philosophy origins
