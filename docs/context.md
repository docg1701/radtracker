# radtracker — Comprehensive Project Context

**Generated:** 2026-05-01
**Version:** v1.0.3 (tagged), 4 tagged releases (v1.0.0 → v1.0.3)
**Test status:** 96 passed, 0 failed (2026-05-01)

---

## 1. Project Purpose

**radtracker** is a personal productivity dashboard for a teleradiology physician. It tracks daily exam counts across three modalities (RM, TC, RX), converts them into earnings in Brazilian Real (BRL), monitors progress toward monthly revenue goals, and generates analytical insights — both rule-based and AI-driven (GPT-OSS 120B via OpenRouter free tier).

The app is a **Streamlit single-page dashboard** with local SQLite persistence. Designed as a single-user, local-only tool — no authentication, no multi-tenancy, no deployment concerns.

**Target user:** A single radiologist (default name: "Galvani", configurable in settings).

**Real production data:** The database contains actual production data for January–April 2026 (~1,692 RM, 340 TC, 12,151 RX across 92 working days), imported from CSV via `scripts/import_csv.py`.

---

## 2. Architecture Overview

### 2.1 Directory Structure

```
radtracker/
├── app.py                  # Streamlit entry point, navigation, session init
├── src/
│   ├── __init__.py         # Empty package marker
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
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # FakeConnection + conn/default_prices fixtures
│   ├── test_calculations.py  # 22 tests — pure functions + DB stats + historical
│   ├── test_chart_colors.py  # 4 tests — hex_to_rgba + palette validation
│   ├── test_db.py            # 14 tests — schema, CRUD, default values
│   ├── test_formatting.py    # 9 tests — BRL formatting, month constants
│   ├── test_insights.py      # 17 tests — tone, content, trends, edge cases
│   └── test_llm_client.py    # 12 tests — success, errors, prompt building
├── scripts/import_csv.py  # CSV import tool for legacy data (assemed + radiplan)
├── data/                   # SQLite DB + imported data markdown (gitignored)
│   ├── .gitkeep
│   ├── telerrad.db         # Main database (gitignored)
│   └── producao_importada.md  # Markdown report from CSV import
├── docs/
│   ├── context.md          # This file
│   ├── meta-prompt.md      # LLM session handoff contract
│   ├── DESIGN.md           # Cal.com design system reference
│   ├── plan.md             # Sprint phases 0–5 implementation plan (all Done)
│   ├── streamlit_extras_guide.md  # Catalog of 56 streamlit-extras components
│   └── streamlit_pro_tips.md      # 25+ Streamlit best practices from co-founder
├── .streamlit/config.toml  # Theme, fonts, dark mode, chart colors, semantic colors
├── .gitignore
├── pyproject.toml          # Project metadata + deps (uv-managed)
├── uv.lock                 # Locked dependency versions
├── requirements.txt        # Legacy requirements (pyproject.toml is authoritative)
├── .env                    # No longer used (API key moved to DB in Phase 3)
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

`ensure_settings(conn)` in `src/ui/settings.py` (called at the top of every tab render function) acts as the session-bootstrap. It lazily loads from DB on first access, then caches in `st.session_state`:

| Key | DB Source | Default Value |
|-----|-----------|---------------|
| `prices` | `exam_prices` (latest row, ORDER BY id DESC LIMIT 1) | `{"rm": 35.0, "tc": 25.0, "rx": 4.5}` |
| `goal` | `monthly_goals` for current year-month | `45000.0` |
| `user_name` | `user_settings` key `"user_name"` | `"Galvani"` |
| `api_key` | `user_settings` key `"api_key"` | `""` |
| `llm_prompt` | `user_settings` key `"llm_prompt"` | Default system prompt (with `{user_name}` interpolated) |

**Analysis-tab specific state:**
- `historical_cache` — `{"key": "YYYY-MM:goal:prices_json_hash", "stats": {...}}` — invalidated when prices or goal change
- `llm_insight_text` — cached LLM response (cleared when historical cache invalidates)
- `llm_insight_pending`, `llm_insight_in_flight`, `llm_insight_cancelled` — AI state machine flags
- `goal_celebrated_YYYY-MM` — boolean guard for celebration rain (once per month)

---

## 3. Database Schema (SQLite)

All tables managed via `sqlalchemy.text` execution through `st.connection`. Database file: `data/telerrad.db` (gitignored, created idempotently on startup via `init_db()`).

### 3.1 `daily_production` — Exam counts per day
```sql
date        TEXT PRIMARY KEY,     -- ISO format "YYYY-MM-DD"
rm_count    INTEGER NOT NULL DEFAULT 0,
tc_count    INTEGER NOT NULL DEFAULT 0,
rx_count    INTEGER NOT NULL DEFAULT 0,
created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.2 `exam_prices` — Price history (append-only)
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT,
rm_price        REAL NOT NULL,
tc_price        REAL NOT NULL,
rx_price        REAL NOT NULL,
effective_from  TEXT NOT NULL,
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```
Current prices are the most recent row (`ORDER BY id DESC LIMIT 1`).

### 3.3 `monthly_goals` — Per-month revenue targets
```sql
year_month  TEXT PRIMARY KEY,     -- "YYYY-MM"
goal_reais  REAL NOT NULL,
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.4 `user_settings` — Generic key/value store
```sql
key         TEXT PRIMARY KEY,
value       TEXT NOT NULL,
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```
Current keys: `user_name`, `api_key`, `llm_prompt`.

### Key CRUD Functions (src/db.py)

| Function | Operation | Pattern |
|----------|-----------|---------|
| `get_connection()` | Connection factory | `st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")` |
| `init_db(conn)` | DDL | `CREATE TABLE IF NOT EXISTS` for all 4 tables, idempotent |
| `upsert_daily(conn, date, rm, tc, rx)` | Write | `INSERT ... ON CONFLICT(date) DO UPDATE` |
| `load_daily(conn, date)` | Read | Returns dict or None |
| `load_month(conn, year_month)` | Read | `WHERE date LIKE 'YYYY-MM%' ORDER BY date` |
| `load_prices(conn)` | Read | `ORDER BY id DESC LIMIT 1`, falls back to `DEFAULT_PRICES` |
| `save_prices(conn, rm, tc, rx)` | Write | Appends new row (append-only history) |
| `load_goal(conn, year_month)` | Read | Falls back to `DEFAULT_GOAL` (45000.0) |
| `save_goal(conn, year_month, goal)` | Write | `INSERT ... ON CONFLICT DO UPDATE` |
| `load_setting(conn, key, default)` | Read | Falls back to `default` |
| `save_setting(conn, key, value)` | Write | `INSERT ... ON CONFLICT DO UPDATE` |

All query functions pass `ttl=0` — no Streamlit result caching (real-time data expected).

---

## 4. Key Modules — Detailed Analysis

### 4.1 `app.py` (Entry Point, 53 lines)

- **Line 20:** `st.set_page_config(page_title="radtracker", page_icon=":material/monitor_heart:", layout="wide", initial_sidebar_state="auto")` — MUST be first Streamlit command
- **Lines 27–28:** DB boot: `conn = get_connection(); init_db(conn)` — idempotent
- **Line 31:** `render_sidebar(conn)`
- **Lines 34–39:** Navigation via horizontal `st.radio` with Material-icon-prefixed labels, `label_visibility="collapsed"`
- **Lines 42–55:** Tab index from `cookies.py` (fallback to 0), bounds check, cookie-persisted selection
- **Lines 58–65:** Dispatch to tab renderers based on `selected_idx`

### 4.2 `src/db.py` (Data Layer, 163 lines)

- Uses Streamlit's `st.connection()` pattern for managed SQLite — no raw `sqlite3` in production code
- `upsert_daily` uses `ON CONFLICT(date) DO UPDATE` — safe insert/update, preserves `created_at`, updates `updated_at`
- `save_prices` is append-only (new row each time) — audit trail preserved
- `load_setting`/`save_setting` are generic key-value accessors — extensible without DDL changes

### 4.3 `src/calculations.py` (Business Logic, 380 lines)

**Pure functions (no DB access):**

| Function | Inputs | Output | Purpose |
|----------|--------|--------|---------|
| `compute_earnings(rm, tc, rx, prices)` | 3 ints + price dict | float | Core: `rm×rm_price + tc×tc_price + rx×rx_price` |
| `estimate_hours(rm, tc, rx)` | 3 ints | float | Work hours via productivity midpoints |
| `format_time_range(hours)` | float | str | `"~08:00 – 13:12"` format |
| `compute_delta_pct(today, yesterday)` | 2 floats | float\|None | % change, returns None for zero/null yesterday |
| `compute_daily_target(goal, total_days)` | 2 floats | float | `goal / total_days` |
| `compute_mtd_earnings(month_df, prices)` | DataFrame + dict | float | Sum of all rows |
| `add_earnings_column(df, prices)` | DataFrame + dict | DataFrame | Copy with `earnings` column added |

**DB-dependent functions:**

| Function | Returns | Used By |
|----------|---------|---------|
| `compute_daily_stats(conn, date_str, prices)` | dict with 10 keys | `today.py` |
| `compute_monthly_stats(conn, year_month, goal, prices)` | dict with 9 keys | `month.py`, insights |
| `compute_historical_stats(conn, year_month, goal, prices)` | dict with 11 keys | `analysis.py`, insights, LLM |

**Business constants:**
- `PRODUCTIVITY = {"rm": 7.5, "tc": 7.5, "rx": 75.0}` — exams per hour
- `WORK_START_HOUR = 8`, `WORK_START_MINUTE = 0`

### 4.4 `src/chart_colors.py` (Color System, 58 lines)

Central palette — **no inline hex values anywhere else in the codebase:**

```python
CHART_COLORS = {
    "rm": "#2563EB",      # Blue-600
    "tc": "#D97706",      # Amber-600
    "rx": "#0891B2",      # Cyan-600
    "primary": "#0D9488", # Teal-600 — main line/bar
    "muted": "#94A3B8",   # Slate-400 — secondary lines
    "neutral": "#64748B", # Slate-500 — annotations
    "progress_danger": "#CCFBF1",     # teal-50  — 0-25%
    "progress_warning": "#5EEAD4",    # teal-300 — 25-50%
    "progress_on_track": "#14B8A6",   # teal-500 — 50-75%
    "progress_achieved": "#0F766E",   # teal-700 — 75-100%
    "track": "#E2E8F0",   # Slate-200 — gridlines, progress background
}
```

- `hex_to_rgba(hex_color, alpha)` — handles both 3-char and 6-char hex
- `get_chart_text_color()` — theme-aware annotation color using `st.context.theme.base`

### 4.5 `src/charts.py` (Plotly Factories — Today/Month, 299 lines)

All accept data as parameters; zero DB access:

| Function | Output | Dimensions | Key Details |
|----------|--------|------------|-------------|
| `build_modality_donut(rm, tc, rx)` | go.Figure | 280px, hole=0.5 | RM→TC→RX order, sort=False |
| `build_daily_sparkline(df)` | go.Figure | 250px | Teal line + fill, DD/MM labels, handles single-day |
| `build_progress_gauge(pct_goal)` | go.Figure | 130px | 4-segment stacked bar + vline marker + annotation |
| `build_monthly_earnings_chart(df, daily_target, year_month)` | go.Figure | 400px | Full-range x-axis with zero-fill, today marker |
| `build_monthly_modality_donut(df, prices)` | go.Figure | — | Revenue-weighted (count × price), not raw counts |

### 4.6 `src/charts_analysis.py` (Analysis Chart Factories, 289 lines)

| Function | Output | Key Details |
|----------|--------|-------------|
| `build_moving_averages_chart(df, year_month)` | go.Figure | MA7 (solid teal fill) + MA30 (dashed gray), same-month only |
| `build_wow_comparison_chart(weekly_data, prices)` | go.Figure | Grouped bar, prev week @ 50% opacity, single-week fallback |
| `build_modality_mix_evolution(mix_history)` | go.Figure | Stacked area (multi-month) or stacked bar (single month) |
| `build_ytd_earnings_chart(df, year_month, goal)` | go.Figure | Monthly bar chart, current month highlighted, goal line |

### 4.7 `src/formatting.py` (Locale & Formatting, 56 lines)

- `fmt_brl(value)` → `"R$ X.XXX,XX"` — uses `Decimal.quantize(ROUND_HALF_UP)` to avoid IEEE-754 floating-point artifacts (specifically tested for the `1.005` trap)
- `md_escape(text)` → escapes `$` for Streamlit markdown (prevents LaTeX math-mode corruption)
- `MONTHS_PT` — dict mapping 1–12 → Portuguese month names

### 4.8 `src/insights_rules.py` (Rule-Based Insights, 221 lines)

- `generate_rule_insights(stats)` — pure function, dict in → Portuguese markdown out
- **Tone determination algorithm:**
  - `remaining == 0 and pct >= 100` → `success`
  - `days_worked >= 5`: compare `daily_needed` vs `daily_avg` with thresholds (1.1×, 1.5×)
  - `days_worked < 5`: compare actual pct vs linear-expected pct
- **Generated analysis blocks:**
  1. Opening paragraph: % goal, MTD earnings, days worked
  2. Projection analysis (tone-dependent wording)
  3. Tone-based assessment emoji line
  4. WoW trend (`:material/trending_up:` / `:material/trending_down:` / `:material/trending_flat:`)
  5. MoM trend (same pattern)
  6. Modality mix shift detection (flags >10pp change from historical average)
  7. Consecutive-below-target warning (≥3 days)
  8. Context-aware suggestion
- **Portuguese plural awareness:** `"dia"/"dias"`, `"resta"/"restam"`, `"restante"/"restantes"`

### 4.9 `src/llm_client.py` (OpenRouter LLM, 193 lines)

- **Model:** `"openai/gpt-oss-120b:free"` (OpenRouter free tier)
- **Class `LLMClient`:**
  - Constructor: `__init__(api_key, prompt=None)` — raises `LLMUnavailableError` if key is None/empty
  - `generate(stats, prices)` → str — builds enriched prompt, calls OpenRouter, returns content
  - `_build_prompt(stats, prices)` → str — interpolates template
- **`LLMUnavailableError`** — raised on: missing key, timeout (>15s via httpx), any HTTP error status
- **`_enrich_stats(stats, prices)`** — extracts 20+ scalar metrics: MA7/MA30 latest, acceleration trend, total exams, best day, ticket médio, historical monthly average
- **`_USER_PROMPT_TEMPLATE`** — detailed Portuguese template with 4 sections (Meta e Ritmo, Tendências, Volume de Exames, Destaques)

### 4.10 `src/cookies.py` (Tab Persistence, 38 lines)

- Uses `streamlit_extras.cookie_manager.cookie_manager()`
- `get_last_tab_index(default="0")` → str — reads `radtracker_last_tab` cookie
- `set_last_tab_index(tab_index)` → None — writes cookie
- Best-effort pattern: silent fallback when cookies unavailable (not yet synced, or outside browser)

---

## 5. UI Structure (Streamlit)

### 5.1 Navigation
- **Method:** `st.radio` with `horizontal=True`, `label_visibility="collapsed"`
- **4 tabs:** `:material/today: Hoje` | `:material/calendar_month: Mês Atual` | `:material/trending_up: Análise` | `:material/settings: Configuração`
- **Persistence:** tab index saved to browser cookie `radtracker_last_tab`

### 5.2 Sidebar (`src/ui/sidebar.py`, 70 lines)
- Header: "**radtracker**" + greeting "Olá, {user_name}."
- Date picker (`max_value=date.today()`, format `DD/MM/YYYY`)
- 3 modality `st.number_input` in `st.columns(3)` — keyed by date string for pre-fill
- Pre-fill: loads existing data for selected date, shows current counts as default values
- "Salvar produção" button — `type="primary"`, spinner on save, toast on success, then `st.rerun()`
- **Not using `st.form`** — intentional decision to keep date-dependent pre-fill working (forms suppress widget-driven reruns)
- Footer: `st.caption("radtracker v1.0 · local")`

### 5.3 "Hoje" Tab (`src/ui/today.py`, 206 lines)

**Empty state:** Centered bordered container with `:material/content_paste:` icon + guidance text

**KPI Row** (4 `st.columns(4)` with bordered containers, stretch height, vertical center alignment):

| Card | Metric Label | Value | Delta |
|------|-------------|-------|-------|
| 1 | Faturamento hoje | `fmt_brl(earnings)` | `±X.X% vs ontem` |
| 2 | Exames hoje | Total count | `RM X · TC X · RX X` pills |
| 3 | Horas estimadas | `X.Xh` | Time range string |
| 4 | Meta mensal | `X%` | MTD / Goal + badge |

**Charts:** 2-column (`st.columns(2)`): Modality donut (left) + 7-day sparkline (right)
**Raw data:** Toggle via `streamlit_extras.stoggle`

### 5.4 "Mês Atual" Tab (`src/ui/month.py`, 194 lines)

**Empty state:** Centered bordered container
**KPI Row:** MTD earnings, % goal, days worked, daily average
**Progress gauge:** Plotly horizontal segmented bar
**Star rating:** `star_rating(stars)` where `stars = min(5.0, pct_goal / 20.0)`
**Celebration:** `rain(emoji="🎉", ...)` when `pct_goal >= 100` — guarded by per-month session_state flag
**Charts:** 2-column: Daily earnings line (left), Revenue donut (right)
**Rhythm alert:** `st.warning` when behind pace (≥5 days of data AND `pct_goal < linear_expected_pct`)
**Raw data:** Toggle via `streamlit_extras.stoggle`

### 5.5 "Análise" Tab (`src/ui/analysis.py`, 225 lines)

**Loading state:** Skeleton placeholders rendered before computing stats, with `st.spinner`
**Cache:** `historical_cache` in session_state, key = `"YYYY-MM:goal:prices_json_hash"`

**Insights expander** (expanded by default):
- Rule-based text from `generate_rule_insights(stats)`
- Caption: "Análise automática baseada nos seus dados"

**AI section** (`@st.fragment` — isolated rerun scope):
- No key configured: caption with link to OpenRouter, disabled button
- Key configured: example prompts, "Perguntar à IA" button
- In-flight state: `st.status` progress + cancel button
- Error handling: `LLMUnavailableError` → `st.error`
- Result: separate `st.expander(":material/smart_toy: Análise da IA")` with caption

**4 charts:**
1. MA7/MA30 (left column) — same-month moving averages
2. WoW comparison (right column) — grouped bar: prev vs current week
3. Modality mix evolution (full-width) — stacked area by month
4. YTD earnings (full-width) — monthly bars + goal line

### 5.6 "Configuração" Tab (`src/ui/settings.py`, 197 lines)

Two `@st.fragment` sections (isolated rerun):

**Settings form:**
- Exam prices: 3 `st.number_input` in columns (RM/R$, TC/R$, RX/R$ with `step=0.50` for RX)
- Monthly goal: `st.number_input` (R$, step=100)
- User name: `st.text_input`
- API key: `st.text_input(type="password")` with OpenRouter link
- AI prompt: `st.text_area(height=200)` with `{user_name}` placeholder support
- Save button → persists all to DB + session_state, clears historical cache, shows toast

**Danger zone:**
- 2-step confirmation: "Limpar todos os dados" → "Sim, limpar tudo" / "Cancelar"
- `_execute_delete()` → `DELETE FROM` all 4 tables in single transaction via raw `sqlite3`, resets session_state to defaults

---

## 6. Theme & Branding

### 6.1 Design Philosophy (Cal.com-inspired)
Defined in `.streamlit/config.toml` and `docs/DESIGN.md`:
- **White canvas** (`#FFFFFF`), **near-black CTAs** (`#111111`) — Cal.com's signature
- Light-gray secondary surfaces (`#F8F9FA`, `#E5E7EB`)
- **No emojis in UI** — Material icons exclusively (`:material/icon_name:`)
- **No custom CSS/`unsafe_allow_html`** — all theming via config.toml
- **No deprecated streamlit-extras** — zero use of `add_vertical_space`, `app_logo`, `colored_header`, `row`, `stylable_container`, `tags`
- **No `st.divider()`** — removed from all files

### 6.2 Typography
- **Headings:** Manrope weight 600 (geometric — Cal Sans substitute)
- **Body:** Inter weight 400
- Font sizes: `["32px", "25px", "21px", "18px", "16px", "14px"]`
- Heading weights: `[600, 600, 600, 500, 500, 500]`
- Loaded via Google Fonts CDN URLs in config.toml

### 6.3 Dark Mode
Full `[theme.dark]` block: `#101010` background, `#1A1A1A` secondary, `#E5E7EB` text, lighter link color. Charts adapt via `get_chart_text_color()` which reads `st.context.theme.base`.

### 6.4 Semantic Colors
`redColor: #EF4444`, `greenColor: #10B981`, `blueColor: #3B82F6`, `orangeColor: #F59E0B`, `violetColor: #8B5CF6`, `grayColor: #6B7280`

---

## 7. Dependencies

### 7.1 Runtime (pyproject.toml — authoritative)

| Package | Version | Purpose |
|---------|---------|---------|
| `streamlit` | ≥1.54.0,<2.0.0 | Dashboard framework |
| `pandas` | ≥2.0.0 | Data manipulation |
| `numpy` | ≥1.24.0 | Numerical ops |
| `plotly` | ≥5.18.0 | Interactive charts |
| `httpx` | ≥0.27.0 | HTTP client for OpenRouter |
| `sqlalchemy` | ≥2.0.0 | SQL abstraction (via `st.connection`) |
| `streamlit-extras` | ≥1.5.0 | Skeleton, rain, star_rating, stoggle, cookies |

### 7.2 Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥8.0.0 | Test runner |
| `pytest-cov` | ≥6.0.0 | Coverage reporting |
| `respx` | ≥0.21.0 | HTTP mock for LLM client tests |
| `ruff` | ≥0.11.0 | Linting (E, F, I, UP rules) |
| `mypy` | ≥1.15.0 | Type checking |

### 7.3 Tooling Configuration

**ruff** (pyproject.toml): line-length=100, select=E,F,I,UP, known-first-party=["src"]
**mypy** (pyproject.toml): python_version=3.12, strict=false, ignore_missing_imports=true, warn_unused_configs=true
**Package manager:** `uv` with `uv.lock`

---

## 8. Data Model Summary

**Three exam modalities:**
- **RM** (Ressonância Magnética): R$35.00/exam (default), productivity 7.5/hour
- **TC** (Tomografia Computadorizada): R$25.00/exam (default), productivity 7.5/hour
- **RX** (Radiografia): R$4.50/exam (default), productivity 75/hour

**Pricing model:** Append-only history in `exam_prices`. Most recent row is current. Previous prices preserved.

**Goal model:** Per-month (`year_month` keyed). Daily target = `goal / calendar_days`. Default: R$45,000/month.

**Work schedule:** Monday–Saturday assumption. Day starts at 08:00 for time-range display.

### CSV Import Mapping (scripts/import_csv.py)
- Raw modalities: `rm`, `tc`, `ag` (angiotomografia), `tt` (tc abdome total), `rx`
- `ag` → merged into TC count
- `tt` → counts 2× toward TC
- Two sources per month: assemed + radiplan, summed per day

---

## 9. Test Coverage

### 9.1 Status (2026-05-01)
**96 passed, 0 failed** (was 95/1 — the `test_historical_consecutive_below_target` timing issue resolved).
Run: `uv run pytest tests/ -v` (1.68s)

### 9.2 Module-Level Coverage

| Module | Tests | Coverage | Notes |
|--------|-------|----------|-------|
| `calculations.py` | 22 | ~94% | Earning formulas, stats, MA, WoW, MoM, historical |
| `db.py` | 14 | ~87% | Schema, CRUD, upsert idempotency, created_at preservation |
| `formatting.py` | 9 | ~92% | BRL currency, IEEE-754 trap (1.005), negative values |
| `insights_rules.py` | 17 | ~85% | Tone detection, content, plural awareness, trends, mix shifts |
| `llm_client.py` | 12 | ~92% | Success, missing key, timeout, HTTP errors, prompt building, multi-month filtering |
| `chart_colors.py` | 4 | ~67% | hex_to_rgba, palette key validation |
| UI modules | 0 | 0% | No Streamlit runtime — excluded by design |
| Chart modules | 0 | 0% | Return plotly Figures; no behavioral tests |

**Overall:** ~36% (UI/chart modules at 0% drags down average; pure-logic modules well-covered)

### 9.3 Test Infrastructure
- `FakeConnection` in `conftest.py` — emulates `st.connection` with SQLite `:memory:` → zero Streamlit dependency
- `conn` fixture: full 3-table schema initialized in `:memory:`
- `default_prices` fixture: copy of `DEFAULT_PRICES`
- LLM tests: `@respx.mock` for HTTP interception
- Insights tests: `_make_stats()` factory for building stats dicts

---

## 10. Scripts

### 10.1 `scripts/import_csv.py` (157 lines)
Self-contained utility for importing legacy production data:
- Reads CSV from `temp/` (assemed + radiplan per month)
- Parses Portuguese month names from filenames
- Combines two sources per day, applies modality mapping rules
- UPSERTs via raw `sqlite3` (standalone, not through `st.connection`)
- Generates `data/producao_importada.md` Markdown report
- Usage: `python scripts/import_csv.py`

---

## 11. Current State & Known Issues

### 11.1 Completed Sprint Phases
All 5 phases of the visual/UX overhaul (from `docs/plan.md`) are ✅ **Done**:
- **Phase 0:** Localization fixes, RX step, remove dividers, hide deploy
- **Phase 1:** Cal.com monochrome theme, Inter + Manrope, dark mode
- **Phase 2:** Bordered KPI cards, stretch heights, donut resizing, responsive sidebar
- **Phase 3:** Material icons, skeleton loading, AI UX, user name config, API key in DB, editable prompt
- **Phase 4:** Teal gradient progress gauge, consistent colors, dark mode chart adaptation
- **Phase 5:** Celebration rain, star rating, stoggle raw data, cookie persistence

### 11.2 Known Issues
1. **`requirements.txt` is stale** — includes `python-dotenv` which is no longer used (API key moved to DB). Authoritative deps are in `pyproject.toml` + `uv.lock`.
2. **No UI-level tests (0%)** — chart and UI modules have no test coverage by design; they require a Streamlit runtime.
3. **Single-user assumption** — no authentication, no concurrent write protection, no deployment considerations.

### 11.3 Critical Design Decisions
- **No `st.form` in sidebar** — using a form would break date-dependent pre-fill since form widgets don't rerun on value change. Sidebar uses imperative save button.
- **API key stored in DB, not `.env`** — eliminates external file dependency. Configured entirely within the UI.
- **`st.radio` for tab navigation** (not `st.tabs`) — Material icon syntax works correctly in radio labels.
- **Cookie persistence for tabs** (not URL params) — simpler for a local single-user app.

### 11.4 Constraints
- **Python ≥ 3.12**
- **Streamlit ≥ 1.54** (for `container(border=...)`, `st.badge`, Material icon syntax in config)
- **SQLite only** — no migration path planned
- **Portuguese locale** — all UI text, tooltips, chart labels, and insights in pt-BR

---

## 12. Key File Reference

| File | Lines | Key Lines | Purpose |
|------|-------|-----------|---------|
| `app.py` | 65 | L20–24, L34–39 | Page config, tab navigation |
| `src/db.py` | 163 | L14–16 (DEFAULT_PRICES), L23–28 (get_connection), L31–56 (init_db) | DB connection + schema |
| `src/calculations.py` | 380 | L20–24 (PRODUCTIVITY), L40–53 (compute_earnings), L170–230 (monthly stats), L236–380 (historical stats) | Business logic |
| `src/chart_colors.py` | 58 | L10–20 (hex_to_rgba), L22–43 (CHART_COLORS), L46–57 (get_chart_text_color) | Color system |
| `src/charts.py` | 299 | L20–65 (modality_donut), L70–115 (sparkline), L120–195 (progress_gauge), L200–275 (monthly_earnings) | Today/Month chart factories |
| `src/charts_analysis.py` | 289 | L25–80 (moving_averages), L85–165 (wow_comparison), L170–250 (mix_evolution), L255–289 (ytd_earnings) | Analysis chart factories |
| `src/formatting.py` | 56 | L5–12 (MONTHS_PT), L15–22 (md_escape), L25–56 (fmt_brl) | Locale + formatting |
| `src/insights_rules.py` | 221 | L21–120 (tone determination), L122–221 (insight generation) | Rule-based analysis |
| `src/llm_client.py` | 193 | L17–21 (LLMUnavailableError), L22–23 (config), L70–180 (class LLMClient), L30–67 (USER_PROMPT_TEMPLATE), L140–180 (_enrich_stats) | OpenRouter LLM integration |
| `src/cookies.py` | 38 | L6–11 (_get_manager), L14–20 (get_last_tab_index), L23–29 (set_last_tab_index) | Tab cookie persistence |
| `src/ui/sidebar.py` | 70 | L6–70 | Data entry form |
| `src/ui/today.py` | 206 | L25–66 (render_today_tab), L69–130 (KPI row), L132–175 (sparkline) | Today dashboard |
| `src/ui/month.py` | 194 | L32–95 (render_month_tab), L98–170 (KPI + rhythm alert), L172–194 (celebration) | Month dashboard |
| `src/ui/analysis.py` | 225 | L38–120 (render_analysis_tab), L122–170 (empty state), L172–225 (AI fragment section) | Analysis + AI |
| `src/ui/settings.py` | 197 | L25–41 (ensure_settings), L54–100 (render_settings_tab), L102–160 (save + delete) | Config |
| `.streamlit/config.toml` | 60 | Full theme config | Colors, fonts, dark mode |
| `tests/conftest.py` | 67 | L10–33 (DB_CREATE_SQL), L36–69 (FakeConnection), L72–85 (conn fixture) | Test infrastructure |
| `scripts/import_csv.py` | 157 | L16–19 (DB_PATH, CSV_DIR), L23–49 (parse_csv), L63–83 (combine_sources), L86–100 (normalize), L148–157 (main) | CSV import |
