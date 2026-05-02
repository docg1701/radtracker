# radtracker — Comprehensive Project Context

**Generated:** 2026-05-02
**Version:** v1.2.1 (sidebar footer: v1.2), 7+ tagged releases
**Test status:** 108 passed, 0 failed (2026-05-02)

---

## 1. Project Purpose

**radtracker** is a personal productivity dashboard for a teleradiology physician. It tracks daily exam counts across **11 dynamic modalities**, converts them into earnings in Brazilian Real (BRL), monitors progress toward monthly revenue goals, and generates analytical insights — both rule-based and AI-driven (OpenRouter, configurable model slug).

The app is a **Streamlit single-page dashboard** with local SQLite persistence. Designed as a single-user, local-only tool for development use — no authentication, no multi-tenancy at the application layer.

**Self-hosted deployment** is supported via Docker + Caddy (reverse proxy with BasicAuth + automatic HTTPS) + fail2ban intrusion prevention, managed with Ansible playbooks (v1.2.0+).

**Target user:** A single radiologist (default name: "Galvani", configurable in settings).

**Real production data:** The database contains actual production data for January–April 2026 across multiple modalities, auto-migrated from the v1 schema.

---

## 2. Architecture Overview

### 2.1 Directory Structure

```
radtracker/
├── app.py                  # Streamlit entry point, navigation, session init
├── Dockerfile              # Multi-stage Docker build (builder + runtime, non-root user)
├── docker-compose.yml      # Caddy + Streamlit services, loopback-only port exposure
├── Caddyfile               # Reverse proxy config: BasicAuth, JSON logging, streamlit upstream
├── .env.example            # Template: DOMAIN + BASICAUTH_USERS (use with Ansible .env.j2)
├── .dockerignore           # Exclude secrets, data, git, caddy dirs, tests from build context
├── src/
│   ├── __init__.py         # Empty package marker
│   ├── db.py               # SQLite schema (v1+v2, 6 tables) + CRUD + seed + migration
│   ├── calculations.py     # Business logic (earnings, hours, MA, projections, stats)
│   ├── charts.py           # Plotly charts (donut, sparkline, gauge, monthly earnings, modality donut)
│   ├── charts_analysis.py  # Analysis charts (MA7/MA30, WoW, mix evolution, YTD)
│   ├── chart_colors.py     # 11 modality colors + legacy aliases + hex_to_rgba
│   ├── formatting.py       # fmt_brl (BRL currency), MONTHS_PT, md_escape
│   ├── insights_rules.py   # Rule-based insights engine (dynamic modalities)
│   ├── llm_client.py       # OpenRouter client (configurable model slug)
│   ├── cookies.py          # Cookie-based tab persistence (streamlit-extras)
│   └── ui/
│       ├── __init__.py
│       ├── sidebar.py      # Dynamic data entry form (date + N modality inputs)
│       ├── today.py        # "Hoje" tab — KPI cards, donut, sparkline (dynamic)
│       ├── month.py        # "Mês Atual" tab — gauge, line chart, rhythm alert
│       ├── analysis.py     # "Análise" tab — insights, configurable LLM, 4 charts
│       └── settings.py     # "Config" tab — modality grid, goal, LLM model, danger zone
├── ansible/                # Self-hosted deployment automation
│   ├── ansible.cfg         # pipelining; ForwardAgent removed (deploy key)
│   ├── inventory.yml       # VPS_HOST + VPS_USER via env vars
│   ├── requirements.yml    # community.docker + community.crypto collections
│   ├── group_vars/
│   │   └── all.yml         # Shared vars + Vault-encrypted secrets (deployment_mode, basicauth_users, github_pat)
│   ├── templates/
│   │   ├── Caddyfile.j2    # Caddy template (LAN or internet mode)
│   │   └── .env.j2         # Docker env_file template ($ → $$ escaping)
│   └── playbooks/
│       ├── deploy.yml      # Bootstrap + deploy (idempotent, generates deploy key + registers via GitHub API)
│       ├── update.yml      # Git update via deploy key + rebuild (preserves data/)
│       ├── health.yml      # Container health, Streamlit endpoint, fail2ban
│       ├── backup.yml      # SQLite dump via docker exec + integrity check
│       └── cleanup.yml     # Full VPS reset (Docker, fail2ban, project, prerequisites)
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # FakeConnection (v2 schema) + conn/seeded_conn/active_modalities fixtures
│   ├── test_calculations.py  # 32 tests — pure functions + DB stats + historical (v2 dynamic)
│   ├── test_chart_colors.py  # 11 tests — hex_to_rgba + 11 modality colors + legacy aliases
│   ├── test_db.py            # 34 tests — v2 schema, seed, CRUD, migration, v1 backward compat
│   ├── test_formatting.py    # 9 tests — BRL formatting, month constants
│   ├── test_insights.py      # 10 tests — dynamic modality insights, tone, trends, mix shifts
│   └── test_llm_client.py    # 12 tests — success, errors, prompt building, multi-month filtering
├── scripts/
│   └── import_csv.py       # CSV import tool for legacy data (assemed + radiplan)
├── data/                   # SQLite DB + imported data markdown (gitignored)
│   ├── .gitkeep
│   ├── telerrad.db         # Main database (gitignored)
│   └── producao_importada.md  # Markdown report from CSV import
├── docs/
│   ├── context.md          # This file
│   ├── meta-prompt.md      # LLM session handoff contract
│   ├── deployment.md       # Ansible deployment guide (v1.2.0+)
│   ├── DESIGN.md           # Cal.com design system reference
│   ├── plan.md             # Sprint phases 0–5 implementation plan (all Done)
│   ├── streamlit_extras_guide.md  # Catalog of 56 streamlit-extras components
│   └── streamlit_pro_tips.md      # 25+ Streamlit best practices from co-founder
├── .streamlit/config.toml  # Theme, fonts, dark mode, chart colors, semantic colors
├── .ansible-lint.yml       # Ansible lint config
├── .hadolint.yml           # Dockerfile lint config
├── .yamllint.yml           # YAML lint config
├── .gitignore
├── pyproject.toml          # Project metadata + deps (uv-managed)
└── uv.lock                 # Locked dependency versions
```

### 2.2 Data Flow

```
User Input (sidebar) → upsert_daily_items() → SQLite (daily_production_items)
                                                     ↓
Tab Render → ensure_settings() → session_state (all_modalities, active_modalities,
                                         prices, goal, user_name, api_key,
                                         llm_model, llm_prompt)
                     ↓
              load_daily_items() / load_month_items() → calculations.py → charts.py
                     ↓
              compute_historical_stats() → insights_rules.py / llm_client.py
```

### 2.3 Session State Architecture

`ensure_settings(conn)` in `src/ui/settings.py` (called at the top of every tab render function) acts as the session-bootstrap. It lazily loads from DB on first access, then caches in `st.session_state`:

| Key | DB Source | Default Value |
|-----|-----------|---------------|
| `all_modalities` | `modalities` table (all 11 rows) | Empty list (seeded by `init_db()`) |
| `active_modalities` | `modalities` WHERE `active=1 AND price>0 AND exams_per_hour>0` | Empty list |
| `prices` | Built from `active_modalities` (slug→price) | `{}` |
| `goal` | `monthly_goals` for current year-month | `45000.0` |
| `user_name` | `user_settings` key `"user_name"` | `"Galvani"` |
| `api_key` | `user_settings` key `"api_key"` | `""` |
| `llm_prompt` | `user_settings` key `"llm_prompt"` | Default system prompt (with `{user_name}` interpolated) |
| `llm_model` | `user_settings` key `"llm_model"` | `"openai/gpt-oss-120b:free"` |

**Analysis-tab specific state:**
- `historical_cache` — `{"key": "json_hash_of_ym_goal_modalities", "stats": {...}}` — invalidated when goal or active modalities change
- `llm_insight_text` — cached LLM response (cleared when historical cache invalidates)
- `llm_insight_pending`, `llm_insight_in_flight`, `llm_insight_cancelled` — AI state machine flags
- `goal_celebrated_YYYY-MM` — boolean guard for celebration rain (once per month)

---

## 3. Database Schema (SQLite)

All tables managed via `sqlalchemy.text` execution through `st.connection`. Database file: `data/telerrad.db` (gitignored, created idempotently on startup via `init_db()`).

### 3.1 `modalities` — Dynamic modality catalog (v2)
```sql
slug            TEXT PRIMARY KEY,     -- e.g. "ressonancia_magnetica"
label           TEXT NOT NULL,        -- "Ressonância Magnética"
price           REAL NOT NULL DEFAULT 0.0,
exams_per_hour  REAL NOT NULL DEFAULT 0.0,
active          INTEGER NOT NULL DEFAULT 0,
sort_order      INTEGER NOT NULL DEFAULT 0,
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```
Seeded with 11 modalities by `_seed_modalities()` — all start with price=0, exams_per_hour=0, active=0. The migration activates the 3 legacy modalities (RM, TC Geral, Radiografia).

### 3.2 `daily_production_items` — Exam counts per day/modality (v2)
```sql
date            TEXT NOT NULL,
modality_slug   TEXT NOT NULL,
count           INTEGER NOT NULL DEFAULT 0,
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
PRIMARY KEY (date, modality_slug),
FOREIGN KEY (modality_slug) REFERENCES modalities(slug)
```

### 3.3 `daily_production` — Legacy v1 counts (kept for migration)
```sql
date        TEXT PRIMARY KEY,     -- ISO format "YYYY-MM-DD"
rm_count    INTEGER NOT NULL DEFAULT 0,
tc_count    INTEGER NOT NULL DEFAULT 0,
rx_count    INTEGER NOT NULL DEFAULT 0,
created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.4 `exam_prices` — Legacy v1 price history (kept for migration)
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT,
rm_price        REAL NOT NULL,
tc_price        REAL NOT NULL,
rx_price        REAL NOT NULL,
effective_from  TEXT NOT NULL,
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.5 `monthly_goals` — Per-month revenue targets
```sql
year_month  TEXT PRIMARY KEY,     -- "YYYY-MM"
goal_reais  REAL NOT NULL,
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```

### 3.6 `user_settings` — Generic key/value store
```sql
key         TEXT PRIMARY KEY,
value       TEXT NOT NULL,
updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```
Current keys: `user_name`, `api_key`, `llm_prompt`, `llm_model`.

### Auto-migration (v1→v2)

`_migrate_v1_to_v2()` in `src/db.py` L339–416:
- Trigger: v1 `daily_production` has rows AND v2 `daily_production_items` is empty
- Copies RM→ressonancia_magnetica, TC→tc_geral, RX→radiografia
- Copies latest prices from `exam_prices` (or DEFAULT_PRICES fallback)
- Activates those 3 modalities with prices and exams_per_hour
- Idempotent: no-op if already migrated

### Key CRUD Functions (src/db.py)

| Function | Operation | Pattern |
|----------|-----------|---------|
| `get_connection()` | Connection factory | `st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")` |
| `init_db(conn)` | DDL | `CREATE TABLE IF NOT EXISTS` for all 6 tables, then seed + migrate |
| `load_all_modalities(conn)` | Read | Returns 11 dicts ordered by label COLLATE NOCASE |
| `load_active_modalities(conn)` | Read | Returns only active AND price>0 AND exams_per_hour>0 |
| `save_modality(conn, slug, price, eph, active)` | Write | Updates single modality row |
| `upsert_daily_items(conn, date, items)` | Write | Dict slug→count; zero=DELETE, non-zero=UPSERT |
| `load_daily_items(conn, date)` | Read | Returns dict slug→count |
| `load_month_items(conn, year_month)` | Read | DataFrame with date, modality_slug, count |
| `upsert_daily(conn, date, rm, tc, rx)` | v1 Write | Legacy insert/update |
| `load_daily(conn, date)` | v1 Read | Returns dict or None |
| `load_month(conn, year_month)` | v1 Read | Legacy DataFrame |
| `load_prices(conn)` | Read | Returns slug→price from active modalities (falls back to DEFAULT_PRICES) |
| `save_prices(conn, rm, tc, rx)` | v1 Write | Legacy append-only |
| `load_goal(conn, year_month)` | Read | Falls back to DEFAULT_GOAL (45000.0) |
| `save_goal(conn, year_month, goal)` | Write | `INSERT ... ON CONFLICT DO UPDATE` |
| `load_setting(conn, key, default)` | Read | Falls back to `default` |
| `save_setting(conn, key, value)` | Write | `INSERT ... ON CONFLICT DO UPDATE` |

All query functions pass `ttl=0` — no Streamlit result caching (real-time data expected).

---

## 4. The 11 Dynamic Modalities

Seeded from `_MODALITY_SEED` in `src/db.py` L30–40:

| # | Slug | Label (pt-BR) | Default Price | Default Exams/h | Default Active |
|---|------|---------------|---------------|-----------------|----------------|
| 1 | `tc_abdome_total` | TC de Abdome Total | 0.00 | 0.0 | 0 |
| 2 | `tc_geral` | TC Geral | 0.00 | 0.0 | 0 |
| 3 | `angiotomografia` | Angiotomografia | 0.00 | 0.0 | 0 |
| 4 | `ressonancia_magnetica` | Ressonância Magnética | 0.00 | 0.0 | 0 |
| 5 | `ultrassonografia` | Ultrassonografia | 0.00 | 0.0 | 0 |
| 6 | `dopplervelocimetria` | Dopplervelocimetria | 0.00 | 0.0 | 0 |
| 7 | `mamografia` | Mamografia | 0.00 | 0.0 | 0 |
| 8 | `radiografia` | Radiografia | 0.00 | 0.0 | 0 |
| 9 | `radiografia_contrastada` | Radiografia Contrastada | 0.00 | 0.0 | 0 |
| 10 | `ultrassom_morfologico` | Ultrassom Morfológico | 0.00 | 0.0 | 0 |
| 11 | `densitometria` | Densitometria | 0.00 | 0.0 | 0 |

After v1→v2 migration, modalities #2, #4, and #8 are activated with historical prices.

---

## 5. Key Modules — Detailed Analysis

### 5.1 `app.py` (Entry Point, 73 lines)

- **Line 20:** `st.set_page_config(page_title="radtracker", page_icon=":material/monitor_heart:", layout="wide", initial_sidebar_state="auto")` — MUST be first Streamlit command
- **Lines 27–28:** DB boot: `conn = get_connection(); init_db(conn)` — idempotent, seeds + migrates
- **Line 31:** `render_sidebar(conn)`
- **Lines 34–39:** Navigation via horizontal `st.radio` with Material-icon-prefixed labels
- **Lines 42–55:** Tab index from `cookies.py` (fallback to 0), bounds check, cookie-persisted selection
- **Lines 58–65:** Dispatch to tab renderers based on `selected_idx`

### 5.2 `src/db.py` (Data Layer, 476 lines)

Uses Streamlit's `st.connection()` pattern for managed SQLite. Key patterns:

- **`_MODALITY_SEED`** (L30–40): 11 modality definitions
- **`init_db()`** (L48–95): Creates 6 tables, seeds modalities if empty, runs v1→v2 migration
- **`load_all_modalities()`** (L102–111): Returns all 11 rows ordered by label
- **`load_active_modalities()`** (L114–126): Filters `active=1 AND price>0 AND exams_per_hour>0`
- **`save_modality()`** (L129–147): Updates single modality
- **`upsert_daily_items()`** (L154–180): Smart insert/update; zero counts → DELETE rather than store zeros
- **`load_daily_items()`** (L181–195): Dict slug→count
- **`load_month_items()`** (L198–209): DataFrame of date, modality_slug, count
- **`load_prices()`** (L235–240): Returns slug→price from active modalities
- **`_seed_modalities()`** (L301–322): Seeds 11 rows if table is empty
- **`_migrate_v1_to_v2()`** (L339–416): One-shot, idempotent v1→v2 migration

### 5.3 `src/calculations.py` (Business Logic, 445 lines)

**Helper:**
- `_build_lookups(modalities)` (L32–41): Returns (slug→price, slug→exams_per_hour) dicts from modality list

**Pure functions (no DB access):**

| Function | Inputs → Output | Purpose |
|----------|-----------------|---------|
| `compute_earnings(counts, prices)` | dict[str,int] + dict[str,float] → float | `sum(count×price)` over all slugs |
| `estimate_hours(counts, exams_per_hour)` | dict[str,int] + dict[str,float] → float | Sum of count/rate per modality |
| `format_time_range(hours)` | float → str | `"~08:00 – HH:MM"` format |
| `compute_delta_pct(today, yesterday)` | float + float\|None → float\|None | % change, returns None for zero/NULL |
| `compute_daily_target(goal, days)` | float + int → float | `goal / days` |

**DB-dependent functions:**

| Function | Returns | Used By |
|----------|---------|---------|
| `compute_daily_stats(conn, date_str, active_modalities)` | dict with 10 keys | `today.py` |
| `compute_monthly_stats(conn, year_month, goal, active_modalities)` | dict with 9 keys | `month.py`, insights |
| `compute_historical_stats(conn, year_month, goal, active_modalities)` | dict with 11 keys (v2 items schema) | `analysis.py`, insights, LLM |

**Key difference from v1:** All functions accept `active_modalities: list[dict]` instead of assuming RM/TC/RX. `compute_historical_stats()` now pivots from `daily_production_items` table.

**Business constants:**
- `WORK_START_HOUR = 8`, `WORK_START_MINUTE = 0`

### 5.4 `src/chart_colors.py` (Color System, 84 lines)

Central palette — **no inline hex values anywhere else in the codebase:**

```python
MODALITY_COLORS: dict[str, str] = {
    "tc_abdome_total": "#2563EB",          # Blue-600
    "tc_geral": "#D97706",                 # Amber-600
    "angiotomografia": "#0891B2",          # Cyan-600
    "ressonancia_magnetica": "#DC2626",    # Red-600
    "ultrassonografia": "#7C3AED",         # Violet-600
    "dopplervelocimetria": "#059669",      # Emerald-600
    "mamografia": "#DB2777",               # Pink-600
    "radiografia": "#CA8A04",              # Yellow-600
    "radiografia_contrastada": "#9333EA",  # Purple-600
    "ultrassom_morfologico": "#0D9488",    # Teal-600
    "densitometria": "#EA580C",            # Orange-600
}
```

- **`color_for_modality(slug)`** → returns fixed color; fallback to `#64748B` (Slate-500) for unknown slugs
- **`CHART_COLORS`** combines `MODALITY_COLORS` + legacy aliases (`"rm"`, `"tc"`, `"rx"`) + chart accent colors
- **`hex_to_rgba(hex, alpha)`** handles 3- and 6-char hex
- **`get_chart_text_color()`** theme-aware annotation color

### 5.5 `src/charts.py` (Plotly Factories — Today/Month, 366 lines)

All accept data as parameters; zero DB access:

| Function | Output | Key Details |
|----------|--------|-------------|
| `build_modality_donut(counts, labels_lookup)` | go.Figure | Dynamic: iterates over counts dict, per-modality colors, hole=0.5 |
| `build_daily_sparkline(df)` | go.Figure | Teal line + fill, DD/MM labels |
| `build_progress_gauge(pct_goal)` | go.Figure | 4-segment stacked bar + vline marker + annotation |
| `build_monthly_earnings_chart(df, daily_target, year_month)` | go.Figure | Full-range x-axis with zero-fill, today marker |
| `build_monthly_modality_donut(df, active_modalities)` | go.Figure | Revenue-weighted (count × price), per-modality colors |

### 5.6 `src/charts_analysis.py` (Analysis Chart Factories, 363 lines)

| Function | Output | Key Details |
|----------|--------|-------------|
| `build_moving_averages_chart(df, year_month)` | go.Figure | MA7 (solid teal fill) + MA30 (dashed gray) |
| `build_wow_comparison_chart(weekly_data, df, active_modalities)` | go.Figure | Dynamic grouped bar per modality, prev week @ 50% opacity |
| `build_modality_mix_evolution(mix_history, active_modalities)` | go.Figure | Dynamic stacked area (multi-month) or stacked bar (single month) |
| `build_ytd_earnings_chart(df, year_month, goal)` | go.Figure | Monthly bar chart, current month highlighted, goal line |

### 5.7 `src/formatting.py` (Locale & Formatting, 53 lines)

- `fmt_brl(value)` → `"R$ X.XXX,XX"` — uses `Decimal.quantize(ROUND_HALF_UP)` to avoid IEEE-754 floating-point artifacts
- `md_escape(text)` → escapes `$` for Streamlit markdown
- `MONTHS_PT` — dict mapping 1–12 → Portuguese month names

### 5.8 `src/insights_rules.py` (Rule-Based Insights, 247 lines)

- `generate_rule_insights(stats, active_modalities)` — pure function, dict + modality list → Portuguese markdown
- **Tone determination algorithm:** identical to v1 (based on remaining days, daily needed vs avg)
- **Key v2 changes:**
  - Accepts `active_modalities` list for modality labels (not hardcoded RM/TC/RX)
  - Modality mix shift detection uses `slug_to_label` from active modalities
  - Suggestion block finds highest-priced modality dynamically from active list
  - Plural awareness: `"dia"/"dias"`, `"resta"/"restam"`, `"restante"/"restantes"`
- **Analysis blocks:** opening paragraph → projection (tone-dependent) → tone assessment → WoW trend → MoM trend → modality mix shift → consecutive-below-target → context-aware suggestion

### 5.9 `src/llm_client.py` (OpenRouter LLM, 255 lines)

- **Configurable model:** constructor accepts `model` slug (default `"openai/gpt-oss-120b:free"`)
- **Class `LLMClient`:**
  - `__init__(api_key, model="...", prompt=None)` — raises `LLMUnavailableError` if key is None/empty
  - `generate(stats, active_modalities)` → str — builds enriched prompt, calls OpenRouter, returns content
  - `_build_prompt(stats, active_modalities)` → str — passes active_modalities to `_enrich_stats`
- **`_enrich_stats(stats, active_modalities)`** — extracts 20+ scalar metrics:
  - MA7/MA30 latest values, acceleration trend
  - Per-modality exam counts (filtered to current month only)
  - Best day, ticket médio (current month only)
  - Historical monthly average
- **`_USER_PROMPT_TEMPLATE`** — detailed Portuguese template with 4 sections (Meta e Ritmo, Tendências, Volume de Exames, Destaques)

### 5.10 `src/cookies.py` (Tab Persistence, 39 lines)

- Uses `streamlit_extras.cookie_manager.cookie_manager()`
- `get_last_tab_index(default="0")` → str — reads `radtracker_last_tab` cookie
- `set_last_tab_index(tab_index)` → None — writes cookie
- Best-effort: silent fallback when cookies unavailable

---

## 6. UI Structure (Streamlit)

### 6.1 Navigation
- **Method:** `st.radio` with `horizontal=True`, `label_visibility="collapsed"`
- **4 tabs:** `:material/today: Hoje` | `:material/calendar_month: Mês Atual` | `:material/trending_up: Análise` | `:material/settings: Configuração`
- **Persistence:** tab index saved to browser cookie `radtracker_last_tab`

### 6.2 Sidebar (`src/ui/sidebar.py`, 89 lines)

- Header: "**radtracker**" + greeting "Olá, {user_name}."
- Date picker (`max_value=date.today()`, format `DD/MM/YYYY`)
- **Dynamic modality inputs:** iterates over `st.session_state.active_modalities`
  - Each modality: `st.columns([3, 1])` — label text in left column, `st.number_input` (label_visibility="collapsed") in right column
  - Label + input side by side on the same row
  - Keyed by `f"sidebar_{slug}_{date_str}"` for date-dependent pre-fill
- Pre-fill: loads existing data for selected date via `load_daily_items()`, shows current counts as default values
- "Salvar produção" button — `type="primary", width="stretch"`, spinner on save, toast on success, clears historical_cache, `st.rerun()`
- Footer: `st.caption("radtracker v1.2 · local")`

### 6.3 "Hoje" Tab (`src/ui/today.py`, 202 lines)

**Empty state:** Centered bordered container with `:material/content_paste:` icon + guidance text
**KPI Row** (4 bordered containers, stretch height):

| Card | Metric Label | Value | Delta |
|------|-------------|-------|-------|
| 1 | Faturamento hoje | `fmt_brl(earnings)` | `±X.X% vs ontem` |
| 2 | Exames hoje | Total count | Per-modality counts with labels |
| 3 | Horas estimadas | `X.Xh` | Time range string |
| 4 | Meta mensal | `X%` | MTD / Goal + badge |

**Charts:** 2-column: Dynamic modality donut (left) + 7-day sparkline (right, auto-pulls from prev month if <7 days)
**Raw data:** Toggle via `streamlit_extras.stoggle`

### 6.4 "Mês Atual" Tab (`src/ui/month.py`, 226 lines)

**Empty state:** Centered bordered container
**KPI Row:** MTD earnings, % goal, days worked, daily average
**Progress gauge:** Plotly horizontal segmented bar
**Star rating:** `star_rating(stars)` where `stars = min(5.0, pct_goal / 20.0)`
**Celebration:** `rain(emoji="🎉")` when `pct_goal >= 100` — per-month session_state guard
**Charts:** 2-column: Daily earnings line (left), Revenue donut (right, per-modality revenue)
**Rhythm alert:** `st.warning` when behind pace (≥5 days AND `pct_goal < linear_expected_pct`)
**Raw data:** Toggle via `streamlit_extras.stoggle`

### 6.5 "Análise" Tab (`src/ui/analysis.py`, 239 lines)

**Loading state:** Skeleton placeholders before computing stats, with `st.spinner`
**Cache:** `historical_cache` key = JSON hash of (year_month, goal, modality_slugs/prices)

**Insights expander** (expanded by default):
- Rule-based text from `generate_rule_insights(stats, active_modalities)`
- Caption: "Análise automática baseada nos seus dados"

**AI section** (`@st.fragment` — isolated rerun scope):
- Shows configured model slug: `st.caption(f"Modelo: {llm_model}")`
- No key: caption with OpenRouter link, disabled button
- Key configured: example prompts, "Perguntar à IA" button
- LLMClient constructed with `model=llm_model` from session state
- In-flight: `st.status` progress + cancel button
- Result: separate expander with model name in caption

**4 charts:**
1. MA7/MA30 (left) — same-month moving averages
2. WoW comparison (right) — dynamic grouped bar per modality
3. Modality mix evolution (full-width) — dynamic stacked area by month
4. YTD earnings (full-width) — monthly bars + goal line

### 6.6 "Configuração" Tab (`src/ui/settings.py`, 323 lines)

Three `@st.fragment` sections:

**Modality grid:**
- Subheader + caption explaining the grid
- Header row: Modalidade | Preço (R$) | Exames/h | Ativo
- Dynamic rows: iterates `st.session_state.all_modalities` (11 rows)
  - Each row: `st.columns([3, 2, 2, 1])` — label | price input | exams/h input | active checkbox
  - Tracks changed rows via comparison with loaded values
  - "Salvar modalidades" button when changes detected
  - On save: persists to DB, clears cache, refreshes session_state

**LLM section:**
- Monthly goal (`st.number_input`)
- User name
- API key (`type="password"`) with OpenRouter link
- LLM model slug (`st.text_input`, validates `provedor/modelo` format)
- System prompt (`st.text_area`, height=200)
- "Salvar configurações" button

**Danger zone:**
- 2-step confirmation: "Limpar todos os dados" → "Sim, limpar tudo" / "Cancelar"
- `_execute_delete()` → `DELETE FROM` all 6 tables via raw `sqlite3`, resets session_state

---

## 7. Theme & Branding

### 7.1 Design Philosophy (Cal.com-inspired)
Defined in `.streamlit/config.toml` and `docs/DESIGN.md`:
- **White canvas** (`#FFFFFF`), **near-black** (`#111111`)
- Light-gray secondary surfaces (`#F8F9FA`, `#E5E7EB`)
- **No emojis in UI** — Material icons exclusively
- **No custom CSS/`unsafe_allow_html`** — all theming via config.toml
- **No deprecated streamlit-extras** — zero use of `add_vertical_space`, `app_logo`, `colored_header`, `row`, `stylable_container`, `tags`
- **No `st.divider()`** — removed from all files

### 7.2 Typography
- **Headings:** Manrope weight 600
- **Body:** Inter weight 400
- Loaded via Google Fonts CDN URLs in config.toml

### 7.3 Dark Mode
Full `[theme.dark]` block. Charts adapt via `get_chart_text_color()` which reads `st.context.theme.base`.

### 7.4 Semantic Colors
`redColor: #EF4444`, `greenColor: #10B981`, `blueColor: #3B82F6`, `orangeColor: #F59E0B`, `violetColor: #8B5CF6`, `grayColor: #6B7280`

---

## 8. Dependencies

### 8.1 Runtime (pyproject.toml — authoritative)

| Package | Version | Purpose |
|---------|---------|---------|
| `streamlit` | ≥1.54.0,<2.0.0 | Dashboard framework |
| `pandas` | ≥2.0.0 | Data manipulation |
| `numpy` | ≥1.24.0 | Numerical ops |
| `plotly` | ≥5.18.0 | Interactive charts |
| `httpx` | ≥0.27.0 | HTTP client for OpenRouter |
| `sqlalchemy` | ≥2.0.0 | SQL abstraction (via `st.connection`) |
| `streamlit-extras` | ≥1.5.0 | Skeleton, rain, star_rating, stoggle, cookies |

### 8.2 Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥8.0.0 | Test runner |
| `pytest-cov` | ≥6.0.0 | Coverage reporting |
| `respx` | ≥0.21.0 | HTTP mock for LLM client tests |
| `ruff` | ≥0.11.0 | Linting (E, F, I, UP rules) |
| `mypy` | ≥1.15.0 | Type checking |
| `yamllint` | ≥1.38.0 | YAML linting |
| `ansible-lint` | ≥26.4.0 | Ansible playbook linting |

### 8.3 Linter Configs (for deployment-layer files)

| Tool | Config File | Purpose |
|------|-----------|---------|
| `ansible-lint` | `.ansible-lint.yml` | Skip no-relative-paths, ignore-errors, command-instead-of-module |
| `hadolint` | `.hadolint.yml` | Ignore DL3008, DL3013, DL3042, DL3059 |
| `yamllint` | `.yamllint.yml` | 2-space indent, disable line-length, ignore ansible/templates/ |

---

## 9. Test Coverage

### 9.1 Status (2026-05-02)
**108 passed, 0 failed** in ~1.89s.
Run: `uv run pytest tests/ -v`

### 9.2 Module-Level Coverage

| Module | Tests | Notes |
|--------|-------|-------|
| `calculations.py` | 32 | Earnings, hours, daily/monthly/historical stats, MA, WoW, MoM (v2 dynamic) |
| `db.py` | 34 | Schema (v2), seed, CRUD, migration (v1→v2), backward compat, prices |
| `chart_colors.py` | 11 | hex_to_rgba, 11 modality colors, legacy aliases, uniqueness |
| `formatting.py` | 9 | BRL currency, IEEE-754 trap (1.005), negative values |
| `insights_rules.py` | 10 | Tone detection, dynamic modality labels, trends, mix shifts |
| `llm_client.py` | 12 | Success, errors, prompt building, multi-month filtering |
| UI modules | 0 | No Streamlit runtime — excluded by design |
| Chart modules | 0 | Return plotly Figures; no behavioral tests |

**Overall:** ~30% (UI/chart modules at 0% drags down average; pure-logic modules well-covered)

### 9.3 Test Infrastructure
- `FakeConnection` in `conftest.py` — emulates `st.connection` with SQLite `:memory:`, v2 schema
- `conn` fixture: full 6-table schema initialized in `:memory:`
- `seeded_conn` fixture: conn with 11 seeded modalities + 3 activated
- `active_modalities` fixture: list of 3 active modality dicts
- `default_prices` fixture: copy of `DEFAULT_PRICES` dict
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

---

## 11. Deployment Infrastructure (v1.2.0+)

Self-hosted deployment to a VPS via Docker + Caddy + fail2ban, managed with Ansible.

### 11.1 Architecture

```
Browser → Caddy (:80/:443) → Streamlit (:8501 loopback)
                ↓
          BasicAuth + Let's Encrypt (auto TLS)
          fail2ban watches /var/log/caddy/access.log for 401s
```

**Two modes:** LAN (plain HTTP, IP-based) and Internet (real domain, Let's Encrypt).

**Security layers:**
1. Caddy BasicAuth on all routes
2. Streamlit only on loopback (127.0.0.1:8501)
3. fail2ban blocks IPs after 5 failed auth attempts in 10 minutes (1-hour ban)
4. fail2ban whitelists local/RFC1918 networks
5. Non-root container user (uid 1000)

### 11.2 Git Authentication — Deploy Key (v1.2.0)

v1.1.0 used SSH agent forwarding (`ForwardAgent=yes`). v1.2.0 replaces this with an ed25519 deploy key:

1. **Generation:** `community.crypto.openssh_keypair` creates `~/.ssh/radtracker_deploy` on the VPS
2. **Registration:** The public key is registered on GitHub via API using `github_pat` (Vault-encrypted, PAT classic with `repo` scope)
3. **Git operations:** Both `deploy.yml` and `update.yml` use `key_file: "{{ deploy_key_path }}"` in the `ansible.builtin.git` module
4. **PAT lifecycle:** The PAT is only needed for initial key registration; it can expire afterwards
5. **ansible.cfg:** The `ForwardAgent` option is removed (commented out)

**Idempotency:** The deploy key task has `changed_when: deploy_key_result.status == 201`. Status 422 (key already exists) is treated as ok — no change.

### 11.3 Docker

**`Dockerfile`** — Multi-stage build:
- **Stage 1 (builder):** `python:3.12-slim`, installs `uv`, pins production deps
- **Stage 2 (runtime):** Copies venv, creates `streamlit` user (uid 1000), runs as non-root
- Healthcheck via `/_stcore/health`

**`docker-compose.yml`** — Two services:
- **`streamlit`**: Build from Dockerfile, `127.0.0.1:8501:8501`
- **`caddy`**: `caddy:2-alpine`, ports 80 + 443
- Both share `radtracker` bridge network
- Container strategy: `recreate: always`

### 11.4 Ansible

**`inventory.yml`** — Single host `radtracker_vps`, configured via env vars `VPS_HOST` + `VPS_USER`.

**`ansible.cfg`** — Pipelining enabled. ForwardAgent removed (deploy key replaces it).

**`group_vars/all.yml`** — Shared variables:
- `radtracker_dir`, `radtracker_data_dir`, `radtracker_backup_dir` — VPS paths
- `deployment_mode` — `"lan"` or `"internet"` (Vault-encrypted)
- `domain` — DNS domain (internet mode only)
- `github_repo`, `github_branch` — clone target
- `github_pat` — GitHub PAT with `repo` scope (Vault-encrypted)
- `deploy_key_path` — `"/home/{{ ansible_user }}/.ssh/radtracker_deploy"`
- `basicauth_users` — `"username bcrypt_hash"` (Vault-encrypted)
- `backup_retention_days` — 30-day rotation

**Playbooks (5):**

| Playbook | Purpose | Key characteristic |
|----------|---------|-------------------|
| `deploy.yml` | Bootstrap + deploy | 10-step idempotent: packages → Docker → deploy key → clone → template → fail2ban → compose up → health check |
| `update.yml` | Zero-downtime update | Git update via deploy key, re-template, rebuild, recreate |
| `health.yml` | Health verification | Container existence, running, healthy, Streamlit 200, Caddy 401, fail2ban active |
| `backup.yml` | SQLite backup | `docker exec` sqlite3 `.backup` → integrity check → rotation |
| `cleanup.yml` | Full VPS reset | Removes containers, prunes Docker, uninstalls everything + project dir |

### 11.5 fail2ban

- Filter: `radtracker-caddy.conf` — regex matches Caddy JSON log lines with `"status": 401`
- Jail: `radtracker.conf` — watches `caddy_logs/access.log`, max 5 retries in 600s, 3600s ban
- Whitelist: `local.conf` — ignores 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16

---

## 12. Current State & Known Issues

### 12.1 Version History
- v1.0.0: Initial release (RM/TC/RX hardcoded)
- v1.1.0: Deployment infrastructure (Docker, Caddy, fail2ban, Ansible)
- v1.1.1: Linter configs, `requirements.txt` removed, Debian 13 compat
- v1.2.0: Dynamic modalities (11), v2 schema, deploy key SSH
- v1.2.1: (current) LLM model configurable, 108 tests

### 12.2 Known Issues
1. **Sidebar footer shows v1.2** — `st.caption("radtracker v1.2 · local")` in `src/ui/sidebar.py` L89; should match current tag
2. **No UI-level tests (0%)** — chart and UI modules have no test coverage by design
3. **Single-user assumption** — no authentication at the application layer
4. **`pyproject.toml` version still shows 1.0.0** — never updated; sidebar footer is the authorative version indicator

---

## 13. Key File Reference

| File | Lines | Key Lines | Purpose |
|------|-------|-----------|---------|
| `app.py` | 73 | L20–24, L34–39 | Page config, tab navigation |
| `src/db.py` | 476 | L30–40 (_MODALITY_SEED), L48–92 (init_db), L154–180 (upsert_daily_items), L339–416 (_migrate_v1_to_v2) | DB schema, seed, migration, CRUD |
| `src/calculations.py` | 445 | L32–41 (_build_lookups), L47–64 (compute_earnings), L65–78 (estimate_hours), L140–210 (monthly stats), L216–360 (historical stats) | Business logic |
| `src/chart_colors.py` | 84 | L11–19 (hex_to_rgba), L22–35 (MODALITY_COLORS), L38–43 (color_for_modality), L47–74 (CHART_COLORS) | Color system |
| `src/charts.py` | 366 | L22–82 (modality_donut), L88–140 (sparkline), L146–225 (progress_gauge), L230–310 (monthly_earnings), L316–366 (modality_donut_monthly) | Chart factories |
| `src/charts_analysis.py` | 363 | L25–80 (moving_averages), L85–210 (wow_comparison), L216–300 (mix_evolution), L305–363 (ytd_earnings) | Analysis charts |
| `src/formatting.py` | 53 | L5–12 (MONTHS_PT), L15–22 (md_escape), L25–53 (fmt_brl) | Locale + formatting |
| `src/insights_rules.py` | 247 | L19–170 (tone determination + analysis blocks) | Rule-based insights |
| `src/llm_client.py` | 255 | L17–21 (LLMUnavailableError), L185–252 (class LLMClient), L74–182 (_enrich_stats) | OpenRouter LLM integration |
| `src/cookies.py` | 39 | L6–11 (_get_manager), L14–20 (get_last_tab_index), L23–29 (set_last_tab_index) | Tab cookie persistence |
| `src/ui/sidebar.py` | 89 | L20–89 | Dynamic sidebar form |
| `src/ui/today.py` | 202 | L25–70 (render_today_tab), L88–175 (KPI row + sparkline) | Today dashboard |
| `src/ui/month.py` | 226 | L30–110 (render + KPI + gauge), L155–195 (rhythm alert), L210–226 (celebration) | Month dashboard |
| `src/ui/analysis.py` | 239 | L25–120 (render + cache + insights), L135–195 (AI fragment) | Analysis + AI |
| `src/ui/settings.py` | 323 | L25–60 (ensure_settings), L84–190 (modality grid + LLM section), L198–250 (danger zone) | Settings + modality config |
| `.streamlit/config.toml` | 60 | Full theme config | Colors, fonts, dark mode |
| `ansible/playbooks/deploy.yml` | 214 | L60–95 (deploy key gen + GitHub API), L125–160 (Docker compose), L170–225 (fail2ban) | Deployment automation |
| `ansible/group_vars/all.yml` | 26 | Vault-encrypted secrets + shared vars | Deployment configuration |
| `tests/conftest.py` | 138 | L17–76 (DB_CREATE_SQL, v2), L78–131 (FakeConnection), L133–156 (fixtures) | Test infrastructure |
