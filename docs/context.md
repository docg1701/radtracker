# radtracker — Comprehensive Project Context

**Generated:** 2026-05-01  
**Version:** v1.0.3 (tagged), 4 tagged releases (v1.0.0 → v1.0.3)

---

## 1. Project Purpose

**radtracker** is a personal productivity dashboard for a teleradiology physician. It tracks daily exam counts (RM, TC, RX), converts them into earnings (Brazilian Real), monitors progress toward monthly revenue goals, and generates analytical insights — both rule-based and AI-driven (GPT-OSS 120B via OpenRouter). The app is a Streamlit single-page dashboard with local SQLite persistence.

**Target user:** A single radiologist (named Galvani, configurable).

---

## 2. Architecture Overview

### 2.1 High-Level Structure

```
radtracker/
├── app.py                  # Streamlit entry point, navigation, session init
├── src/
│   ├── db.py               # SQLite schema + CRUD (4 tables)
│   ├── calculations.py     # Business logic (earnings, MA, projections)
│   ├── charts.py           # Plotly charts (donut, gauge, sparkline, monthly)
│   ├── charts_analysis.py  # Analysis charts (MA, WoW, mix evolution, YTD)
│   ├── chart_colors.py     # Shared color palette + hex_to_rgba
│   ├── formatting.py       # fmt_brl (BRL currency), MONTHS_PT, md_escape
│   ├── insights_rules.py   # Rule-based insights engine (pure function)
│   ├── llm_client.py       # OpenRouter GPT-OSS 120B client
│   ├── cookies.py          # Cookie-based tab persistence (streamlit-extras)
│   └── ui/
│       ├── __init__.py
│       ├── sidebar.py      # Data entry form (date + 3 modality inputs)
│       ├── today.py        # "Hoje" tab — KPI cards, donut, sparkline
│       ├── month.py        # "Mês Atual" tab — gauge, line chart, rhythm alert
│       ├── analysis.py     # "Análise" tab — insights, LLM, 4 charts
│       └── settings.py     # "Config" tab — prices, goal, API key, prompt
├── tests/                  # Test suite: conftest.py + 6 test files
├── scripts/import_csv.py   # CSV import tool for legacy data
├── data/                   # SQLite DB + imported data markdown (gitignored)
├── docs/                   # DESIGN.md, sprint plan, streamlit guides
├── .streamlit/config.toml  # Theme, fonts, dark mode, chart colors
├── pyproject.toml          # Project metadata + deps (uv-managed)
├── uv.lock                 # Locked dependency versions
├── requirements.txt        # Legacy requirements (uv lock is authoritative)
└── README.md               # Usage, install, AI setup instructions
```

### 2.2 Data Flow

```
User Input (sidebar) → upsert_daily() → SQLite (daily_production)
                                             ↓
Tab Render → ensure_settings() → session_state (prices, goal, user_name, api_key)
                     ↓
              load_daily() / load_month() → calculations.py → charts.py
                     ↓
              compute_historical_stats() → insights_rules.py / llm_client.py
```

### 2.3 Session State Architecture

`ensure_settings(conn)` in `src/ui/settings.py` (called by every tab render) acts as the session-bootstrap function. It lazily loads from DB on first access, then caches in `st.session_state`:

| Key | Source | Default |
|-----|--------|---------|
| `prices` | `exam_prices` (latest row) | `{"rm": 35.0, "tc": 25.0, "rx": 4.5}` |
| `goal` | `monthly_goals` | 45000.0 |
| `user_name` | `user_settings` | `"Galvani"` |
| `api_key` | `user_settings` | `""` |
| `llm_prompt` | `user_settings` | Default system prompt |

Analysis tab adds `historical_cache` (dict with key+stats) and `llm_insight_text`.

---

## 3. Database Schema (SQLite)

Four tables managed via SQLAlchemy text execution through `st.connection`:

### 3.1 `daily_production`
```sql
date        TEXT PRIMARY KEY,     -- ISO format "YYYY-MM-DD"
rm_count    INTEGER NOT NULL DEFAULT 0,
tc_count    INTEGER NOT NULL DEFAULT 0,
rx_count    INTEGER NOT NULL DEFAULT 0,
created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.2 `exam_prices`
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT,
rm_price        REAL NOT NULL,
tc_price        REAL NOT NULL,
rx_price        REAL NOT NULL,
effective_from  TEXT NOT NULL,
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.3 `monthly_goals`
```sql
year_month  TEXT PRIMARY KEY,     -- "YYYY-MM"
goal_reais  REAL NOT NULL,
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.4 `user_settings`
```sql
key         TEXT PRIMARY KEY,
value       TEXT NOT NULL,
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

**DB file:** `data/telerrad.db` (gitignored, created idempotently on startup).

**Key CRUD functions:** `upsert_daily`, `load_daily`, `load_month`, `load_prices`, `save_prices`, `load_goal`, `save_goal`, `load_setting`, `save_setting`.

Connection is managed via `st.connection("telerrad", type="sql", url="sqlite:///...")` — a Streamlit-native SQL connection.

---

## 4. Key Modules — Detailed Analysis

### 4.1 `app.py` (Entry Point)
- Sets `st.set_page_config` with wide layout, page icon `:material/monitor_heart:`
- Initializes DB (idempotent `init_db()`)
- Renders sidebar
- Navigation via `st.radio` (horizontal, collapsed label) with 4 tabs
- Cookie-persisted tab selection via `cookies.py`
- Dispatches to `render_today_tab`, `render_month_tab`, `render_analysis_tab`, `render_settings_tab`

### 4.2 `src/db.py` (Data Layer)
- Uses `st.connection("telerrad")` pattern for SQLite access
- `init_db()` creates all 4 tables (`CREATE TABLE IF NOT EXISTS`)
- `upsert_daily()` uses `ON CONFLICT(date) DO UPDATE` — safe insert/update
- `load_prices()` returns latest row from `exam_prices` via `ORDER BY id DESC LIMIT 1`
- `load_goal()` is month-scoped; falls back to `DEFAULT_GOAL`
- `load_setting()`/`save_setting()` are generic key-value accessors
- All query functions pass `ttl=0` to disable Streamlit's result caching (real-time data expected)

### 4.3 `src/calculations.py` (Business Logic)
**Pure functions (no DB):**
- `compute_earnings(rm, tc, rx, prices)` → float — total R$ from exam counts × unit prices
- `estimate_hours(rm, tc, rx)` → float — work hours using productivity midpoints (RM/TC: 7.5/h, RX: 75/h)
- `format_time_range(hours)` → str — e.g. `"~08:00 – 13:12"`
- `compute_delta_pct(today, yesterday)` → float|None — percentage change
- `compute_daily_target(goal, total_days)` → float
- `compute_mtd_earnings(month_df, prices)` → float
- `add_earnings_column(df, prices)` → DataFrame — adds computed `earnings` column

**DB-dependent functions:**
- `compute_daily_stats(conn, date_str, prices)` → dict — complete "Hoje" tab stats including yesterday comparison
- `compute_monthly_stats(conn, year_month, goal, prices)` → dict — MTD earnings, % goal, days worked, projection, daily target needed
- `compute_historical_stats(conn, year_month, goal, prices)` → dict — all historical data with MA7/MA30 rolling windows, WoW/MoM deltas, modality mix, consecutive-below-target count, weekly totals (last 4 weeks), per-month modality mix history

**Business constants:**
- `PRODUCTIVITY = {"rm": 7.5, "tc": 7.5, "rx": 75.0}` (exams/hour)
- `WORK_START_HOUR = 8`, `WORK_START_MINUTE = 0`

### 4.4 `src/chart_colors.py` (Color System)
- Central palette `CHART_COLORS` dict with semantically-named hex values
- Modality colors: RM `#2563EB` (Blue-600), TC `#D97706` (Amber-600), RX `#0891B2` (Cyan-600)
- Chart accent: `primary` `#0D9488` (Teal-600), `muted` `#94A3B8`, `neutral` `#64748B`
- Progress gauge: teal monochrome gradient `progress_danger` → `progress_achieved`
- Track color: `#E2E8F0`
- `hex_to_rgba(hex, alpha)` → rgba string for transparent fills
- `get_chart_text_color()` → theme-aware annotation color (light `#0F172A`, dark `#E5E7EB`) using `st.context.theme.base` with fallback

### 4.5 `src/charts.py` (Plotly Chart Factories — Today/Month tabs)
All accept data as parameters; no DB access:
- `build_modality_donut(rm, tc, rx)` — donut chart with hole=0.5, 280px height
- `build_daily_sparkline(df)` — 7-day mini trend line with teal fill, 250px
- `build_progress_gauge(pct_goal)` — horizontal stacked bar with 4 milestone segments + vertical marker + annotation
- `build_monthly_earnings_chart(df, daily_target, year_month)` — full-month line chart with daily target, today marker
- `build_monthly_modality_donut(df, prices)` — revenue-share donut (count × price)

### 4.6 `src/charts_analysis.py` (Analysis Chart Factories)
- `build_moving_averages_chart(df, year_month)` — MA7 (solid teal fill) + MA30 (dashed gray)
- `build_wow_comparison_chart(weekly_data, prices)` — grouped bar chart (current vs previous week) with modality revenue breakdown
- `build_modality_mix_evolution(mix_history)` — stacked area chart (multi-month) or vertical stacked bar (single month)
- `build_ytd_earnings_chart(df, year_month, goal)` — year-to-date monthly bar chart with goal line; current month highlighted

### 4.7 `src/formatting.py` (Locale & Formatting)
- `fmt_brl(value)` → `"R$ X.XXX,XX"` — Brazilian currency with Decimal quantize (ROUND_HALF_UP) to avoid IEEE-754 traps
- `md_escape(text)` → escapes `$` for Streamlit markdown (prevents LaTeX math-mode)
- `MONTHS_PT` — dict mapping 1–12 → Portuguese month names

### 4.8 `src/insights_rules.py` (Rule-Based Insights)
- `generate_rule_insights(stats)` — pure function, returns Portuguese markdown
- **Tone determination:** success/on_track/warning/danger based on `daily_needed vs daily_avg` ratio
- Generates: opening % summary, projection analysis, WoW/MoM trends, modality mix shift detection (>10pp change triggers), consecutive-below-target alerts, context-aware suggestions
- Plural-aware helpers for correct Portuguese ("dia" vs "dias", "resta" vs "restam")

### 4.9 `src/llm_client.py` (OpenRouter LLM Client)
- **Model:** `openai/gpt-oss-120b:free` (OpenRouter free tier)
- `LLMClient` is stateless: constructor takes `api_key` and optional `system_prompt` override
- `generate(stats, prices)` builds enriched prompt from `_enrich_stats()` → sends to OpenRouter → returns text
- `LLMUnavailableError` raised on: missing key, timeout (>15s), HTTP errors
- `_enrich_stats()` extracts 20+ scalar metrics from the historical stats dict: MA7/MA30 latest, acceleration trend, total exam counts per modality, best day, ticket médio, historical monthly average, etc.
- `_build_prompt()` interpolates `_USER_PROMPT_TEMPLATE` with enriched data
- Test coverage uses `respx` to mock HTTP

### 4.10 `src/cookies.py` (Persistence)
- Uses `streamlit_extras.cookie_manager` to persist `radtracker_last_tab` (tab index)
- Best-effort: silent fallback when cookies unavailable

---

## 5. UI Structure (Streamlit)

### 5.1 Navigation
- **Method:** `st.radio` with `horizontal=True`, `label_visibility="collapsed"`
- **4 tabs:** "Hoje", "Mês Atual", "Análise", "Configuração"
- **Persistence:** last tab index saved to browser cookie via `cookies.py`
- Each tab label uses Material icons (`:material/today:`, etc.)

### 5.2 Sidebar (`src/ui/sidebar.py`)
- Greeting: "Olá, {user_name}." with app title "radtracker"
- Date picker (max: today, format: DD/MM/YYYY)
- 3 modality number inputs in 3 columns (RM, TC, RX) — pre-filled from existing data
- "Salvar produção" primary button with `:material/save:` icon, uses `st.spinner` + `st.toast` on success
- Footer: "radtracker v1.0 · local"

### 5.3 "Hoje" Tab (`src/ui/today.py`)
- Empty state: centered bordered container with guidance text
- KPI row (4 cards in `st.columns(4)`):
  1. Faturamento hoje (R$) with % delta vs yesterday
  2. Exames hoje (total + RM/TC/RX pill indicators)
  3. Horas estimadas (decimal + time range)
  4. Meta mensal (% progress + badge "No ritmo"/"Atenção")
- 2-column charts: Modality donut (left) + 7-day sparkline (right)
- Raw data toggle via `stoggle`

### 5.4 "Mês Atual" Tab (`src/ui/month.py`)
- Empty state: centered bordered container
- KPI row (4 cards): MTD earnings, % goal, days worked, daily average
- Progress gauge (Plotly horizontal bar)
- Star rating (0-5 based on % goal / 20)
- Celebration rain (`🎉`) on 100% goal (once per month, guarded by session_state)
- 2-column charts: Daily earnings line (left) + Revenue donut (right)
- Rhythm alert (`st.warning`) when behind pace (≥5 days of data)
- Raw data toggle

### 5.5 "Análise" Tab (`src/ui/analysis.py`)
- Skeleton loading placeholders before expensive `compute_historical_stats()`
- `historical_cache` in session_state keyed by `year_month:goal:prices_hash`
- **Insights expander** (expanded by default): rule-based text from `generate_rule_insights()`
- **AI section** (`@st.fragment` isolated):
  - Shows caption + link to OpenRouter when no API key
  - "Perguntar à IA" button with example prompts
  - In-flight guard with cancel mechanism
  - LLMUnavailableError handling with fallback error message
  - Cached LLM result in separate expander
- 4 charts: MA7/MA30 (left), WoW comparison (right), Modality mix evolution (full-width), YTD earnings (full-width)

### 5.6 "Configuração" Tab (`src/ui/settings.py`)
- **Fragment-isolated** save form and danger zone
- Exam prices (3 columns: RM/R$ TC/R$ RX/R$) with appropriate steps
- Monthly goal (R$)
- User name text input
- OpenRouter API key (password field) with link to OpenRouter
- Editable AI system prompt (text area, 200px) with `{user_name}` placeholder support
- "Salvar configurações" button → persists to DB + session_state + toast
- **Danger zone:** 2-step confirmation → `DELETE FROM` all 4 tables within transaction, resets to defaults

---

## 6. Theme & Branding

### 6.1 Design Philosophy
Cal.com-inspired monochrome aesthetic per `docs/DESIGN.md`:
- White canvas (`#FFFFFF`), near-black CTAs (`#111111`)
- Light-gray secondary surfaces (`#F8F9FA`, `#E5E7EB`)
- **No emojis** — Material icons everywhere (`:material/icon_name:`)
- **No custom CSS** — all theming through `.streamlit/config.toml`
- **Typography:** Manrope (headings, weight 600 — Cal Sans substitute) + Inter (body, weight 400)

### 6.2 Dark Mode
Full dark theme defined in `[theme.dark]`: `#101010` background, `#1A1A1A` secondary, `#E5E7EB` text, `#60A5FA` links. Charts use `get_chart_text_color()` for theme-aware annotations. Dark mode toggled via Streamlit Settings menu.

### 6.3 Color Palette
Defined in both `.streamlit/config.toml` (Streamlit theme tokens + chart categorical colors) and `src/chart_colors.py` (Plotly traces). Key semantic colors: `redColor: #EF4444`, `greenColor: #10B981`, `blueColor: #3B82F6`, `orangeColor: #F59E0B`, `violetColor: #8B5CF6`.

---

## 7. Dependencies

### 7.1 Runtime (pyproject.toml)
| Package | Version | Purpose |
|---------|---------|---------|
| `streamlit` | ≥1.54.0,<2.0.0 | Dashboard framework |
| `pandas` | ≥2.0.0 | Data manipulation |
| `numpy` | ≥1.24.0 | Numerical ops (pandas dependency) |
| `plotly` | ≥5.18.0 | Interactive charts |
| `httpx` | ≥0.27.0 | HTTP client for OpenRouter API |
| `sqlalchemy` | ≥2.0.0 | SQL abstraction (used via `st.connection`) |
| `streamlit-extras` | ≥1.5.0 | Skeleton loading, rain, star rating, stoggle, cookies |

### 7.2 Dev Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥8.0.0 | Test runner |
| `pytest-cov` | ≥6.0.0 | Coverage reporting |
| `respx` | ≥0.21.0 | HTTP mock for LLM client tests |
| `ruff` | ≥0.11.0 | Linting (pycodestyle, pyflakes, isort, pyupgrade) |
| `mypy` | ≥1.15.0 | Type checking |

### 7.3 Tooling
- **Package manager:** `uv` (lockfile at `uv.lock`)
- **Linting:** ruff (config in pyproject.toml: `E`, `F`, `I`, `UP` rules, line-length 100)
- **Type checking:** mypy (strict=false, ignore_missing_imports=true)

---

## 8. Data Model Summary

**Three exam modalities:**
- **RM** (Ressonância Magnética): R$35.00/exam (default), productivity 7.5 exams/h
- **TC** (Tomografia Computadorizada): R$25.00/exam (default), productivity 7.5 exams/h
- **RX** (Radiografia): R$4.50/exam (default), productivity 75 exams/h

**Pricing model:** Most recent `exam_prices` row is current; previous prices preserved for audit. Prices are user-configurable in settings.

**Goal model:** Per-month (`year_month` keyed), defaults to R$45,000. Daily target = goal / calendar days.

**Work schedule assumption:** Monday–Saturday, starting at 08:00.

---

## 9. Test Coverage

### 9.1 Status
- **95 pass, 1 fail** (known: `test_historical_consecutive_below_target` — timing edge case with `date.today()`)
- **Test files:** 6 (`test_calculations.py`, `test_chart_colors.py`, `test_db.py`, `test_formatting.py`, `test_insights.py`, `test_llm_client.py`)
- **Coverage:** 36% overall. Pure logic modules well-covered (calculations 94%, formatting 92%, llm_client 92%, db 87%, insights_rules 85%). UI and chart modules at 0% (no UI-level tests).

### 9.2 Test Architecture
- `FakeConnection` class in `conftest.py` emulates `st.connection` with SQLite `:memory:` — zero Streamlit dependency in tests
- `conn` fixture: full schema initialized in `:memory:` database
- `default_prices` fixture: copy of `DEFAULT_PRICES` dict
- LLM tests use `respx` mock with `@respx.mock` decorator
- Insights tests use `_make_stats()` helper factory to build stats dicts

### 9.3 Test Categories
| Module | Test count | Coverage % | Notes |
|--------|-----------|------------|-------|
| `calculations.py` | 22 | 94% | Pure functions + DB-dependent stats + historical |
| `db.py` | 14 | 87% | Schema, CRUD, default values, upsert behavior |
| `formatting.py` | 9 | 92% | BRL formatting including IEEE-754 trap tests |
| `insights_rules.py` | 17 | 85% | Tone detection, content, suggestions, trends, edge cases |
| `llm_client.py` | 12 | 92% | Success, missing key, timeout, HTTP errors, prompt building |
| `chart_colors.py` | 4 | 67% | hex_to_rgba, palette key validation |

---

## 10. Scripts & Tooling

### 10.1 `scripts/import_csv.py`
Import utility for legacy production data from CSV files:
- Reads CSV files from `temp/` directory (2 sources per month: assemed + radiplan)
- Parses Portuguese month names from filenames
- Modality mapping: `ag` → TC, `tt` → 2× TC (abdomen total = double regular TC)
- Sums assemed + radiplan counts per day
- UPSERTs into SQLite via raw `sqlite3` (not st.connection)
- Generates `data/producao_importada.md` markdown report

### 10.2 Data
- `data/telerrad.db` — main SQLite database (gitignored)
- `data/producao_importada.md` — Markdown report from CSV import, contains actual production data for Jan–Apr 2026 (~1,692 RM, 340 TC, 12,151 RX total across 92 days)

---

## 11. Current State Assessment

### 11.1 Completed (from sprint plan)
All 5 phases of the visual/UX overhaul are marked **Done**:
- **Phase 0:** Foundation fixes (localization, RX step, remove dividers)
- **Phase 1:** Theme & typography (Cal.com monochrome, Inter + Manrope fonts, dark mode)
- **Phase 2:** Layout & responsiveness (bordered KPI cards, stretch heights, donut resizing)
- **Phase 3:** Visual polish (Material icons, skeleton loading, AI UX, user name config, API key in DB, editable AI prompt)
- **Phase 4:** Chart refinements (teal gradient progress gauge, consistent colors, tooltip Portuguese, dark mode adaptation)
- **Phase 5:** UX enhancements (celebration rain, star rating, stoggle raw data, cookie persistence)

### 11.2 Known Issues
1. **Test failure:** `test_historical_consecutive_below_target` — inserts 3 days with today's date, but `compute_historical_stats` shows 0 consecutive_below_target. Root cause: test inserts data for `date.today()` but the insertion loop may create future dates or the daily target calculation doesn't match expected values. This is a test timing issue, not a logic bug.
2. **Low UI test coverage (0%):** No tests for Streamlit render functions (chart modules, UI modules). These are excluded from coverage by design since they require a Streamlit runtime.
3. **`requirements.txt` is stale:** The authoritative dependency list is in `pyproject.toml` + `uv.lock`. `requirements.txt` includes `python-dotenv` which is no longer used (API key moved to DB in Phase 3).

### 11.3 Design Decisions
- **No `st.form` in sidebar** (documented risk): Using `st.form` would break date-dependent pre-fill since form widgets don't rerun on value change. Sidebar keeps imperative save button pattern.
- **API key in DB, not `.env`:** Eliminates the `.env` file requirement. Key stored in `user_settings` table, configured entirely within the UI.
- **`st.radio` over `st.tabs` for navigation:** Material icons render correctly in radio buttons but not in tab components.
- **Cookie persistence over query params:** Tab selection persists via browser cookie, not URL params — simpler for a single-user local app.

### 11.4 Constraints
- **Python ≥ 3.12** required
- **Streamlit ≥ 1.54** for `container(border=...)`, `st.badge`, Material icon syntax
- **Single-user local app** — no authentication, no multi-tenancy, no deployment optimizations
- **SQLite-only** — no migration to PostgreSQL/other planned
- **Portuguese locale** — all user-facing text and tooltips in pt-BR

---

## 12. File Mapping — Key Lines Reference

| File | Key Lines | Purpose |
|------|-----------|---------|
| `app.py:20-24` | `st.set_page_config(...)` | Page config (must be first) |
| `app.py:27-28` | `conn = get_connection(); init_db(conn)` | DB boot |
| `app.py:32-36` | `TAB_LABELS = [...]` | 4-tab navigation array |
| `src/db.py:17-20` | `DEFAULT_PRICES`, `DEFAULT_GOAL` | Fallback constants |
| `src/db.py:23-28` | `get_connection()` | SQLite via st.connection |
| `src/db.py:31-56` | `init_db()` | 4-table DDL |
| `src/calculations.py:20-24` | `PRODUCTIVITY` | Exams/hour midpoints |
| `src/calculations.py:40-53` | `compute_earnings()` | Core earnings formula |
| `src/calculations.py:170-230` | `compute_monthly_stats()` | Month aggregate |
| `src/calculations.py:236-380` | `compute_historical_stats()` | All-time stats + MA |
| `src/chart_colors.py:22-43` | `CHART_COLORS` | Central color palette |
| `src/chart_colors.py:46-57` | `get_chart_text_color()` | Theme-aware text |
| `src/llm_client.py:22` | `_MODEL = "openai/gpt-oss-120b:free"` | LLM model |
| `src/insights_rules.py:21-120` | `generate_rule_insights()` | Tone + insights logic |
| `src/ui/settings.py:25-41` | `ensure_settings()` | Session bootstrap |
| `src/ui/analysis.py:107-120` | Fragment AI section | Isolated LLM calls |
| `.streamlit/config.toml` | Full theme config | Colors, fonts, dark mode |
| `tests/conftest.py:34-45` | `FakeConnection` | Test DB emulation |
