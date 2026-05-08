# radtracker — Comprehensive Project Context

**Generated:** 2026-05-06
**Version:** v1.5.2
**Test status:** 150 passed, 0 failed (2026-05-06)

---

## 1. Project Purpose

**radtracker** is a personal productivity dashboard for a teleradiology physician. It tracks daily exam counts across **configurable dynamic modalities**, converts them into earnings in Brazilian Real (BRL), monitors progress toward monthly revenue goals, and generates analytical insights — both rule-based and AI-driven (OpenRouter, configurable model slug).

The app is a **Streamlit single-page dashboard** with local SQLite persistence. Designed as a single-user, local-only tool for development use — no authentication, no multi-tenancy at the application layer.

**Self-hosted deployment** is supported via Docker + Caddy (reverse proxy with BasicAuth + automatic HTTPS) + fail2ban intrusion prevention, managed with Ansible playbooks.

**Target user:** A single radiologist (default name: "Galvani", configurable in settings).

**New in v1.5.0:** Chat IA tab with RAG-powered conversational assistant, SSE streaming via OpenRouter, suggestion pills, and markdown-escaping guide for `$` handling.

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
│   ├── charts.py           # Plotly charts (bar, donut, sparkline, gauge, monthly earnings, modality donut)
│   ├── charts_analysis.py  # Analysis charts (MA7/MA30, WoW, mix evolution, YTD)
│   ├── chart_colors.py     # 11 modality colors + legacy aliases + hex_to_rgba + DB-based color lookup
│   ├── formatting.py       # fmt_brl (BRL currency), md_escape ($ for Markdown), MONTHS_PT
│   ├── insights_rules.py   # Rule-based insights engine (dynamic modalities)
│   ├── llm_client.py       # OpenRouter client (one-shot + SSE streaming) + RAG context builder
│   ├── cookies.py          # Cookie-based tab persistence (streamlit-extras)
│   └── ui/
│       ├── __init__.py
│       ├── sidebar.py      # Dynamic data entry form (date + N modality inputs)
│       ├── today.py        # "Hoje" tab — KPI cards, modality bar, sparkline (dynamic)
│       ├── month.py        # "Mês Atual" tab — gauge, line chart, rhythm alert, celebration
│       ├── analysis.py     # "Análise" tab — rule insights + 4 analysis charts (AI section removed in 1.5.0)
│       ├── chat.py         # "Chat IA" tab — RAG-powered streaming chat (new in 1.5.0)
│       └── settings.py     # "Config" tab — modality grid + add/delete, goal, LLM, danger zone
├── ansible/                # Self-hosted deployment automation
│   ├── ansible.cfg         # pipelining; ForwardAgent removed (deploy key)
│   ├── inventory.yml       # VPS_HOST + VPS_USER via env vars
│   ├── requirements.yml    # community.docker + community.crypto collections
│   ├── group_vars/
│   │   └── all.yml         # Shared vars + Vault-encrypted secrets
│   ├── templates/
│   │   ├── Caddyfile.j2    # Caddy template (LAN or internet mode)
│   │   └── .env.j2         # Docker env_file template ($ → $$ escaping)
│   └── playbooks/
│       ├── deploy.yml      # Bootstrap + deploy (idempotent)
│       ├── update.yml      # Git update via deploy key + rebuild (preserves data/)
│       ├── health.yml      # Container health, Streamlit endpoint, fail2ban
│       ├── backup.yml      # SQLite dump via docker exec + integrity check
│       └── cleanup.yml     # Full VPS reset
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # FakeConnection (v2 schema) + conn/seeded_conn/active_modalities fixtures
│   ├── test_calculations.py  # 32 tests — pure functions + DB stats + historical (v2 dynamic)
│   ├── test_chart_colors.py  # 14 tests — hex_to_rgba + 11 modality colors + legacy aliases
│   ├── test_charts.py        # 3 tests — chart figure structure validation
│   ├── test_db.py            # 54 tests — v2 schema, seed, CRUD, migration, add/delete, v1 backward compat
│   ├── test_formatting.py    # 9 tests — BRL formatting, md_escape, month constants
│   ├── test_insights.py      # 10 tests — dynamic modality insights, tone, trends, mix shifts
│   └── test_llm_client.py    # 28 tests — success, errors, streaming, RAG context, prompt building
├── scripts/
│   └── import_csv.py       # CSV import tool for legacy data (assemed + radiplan)
├── data/                   # SQLite DB + imported data markdown (gitignored)
│   ├── .gitkeep
│   └── telerrad.db         # Main database (gitignored)
├── docs/
│   ├── context.md          # This file
│   ├── meta-prompt.md      # LLM session handoff contract
│   ├── deployment.md       # Ansible deployment guide
│   ├── DESIGN.md           # Cal.com design system reference
│   ├── markdown-escaping-guide.md  # Guide for $ escaping in Streamlit Markdown
│   ├── streamlit_extras_guide.md  # Catalog of 56 streamlit-extras components
│   └── streamlit_pro_tips.md      # 25+ Streamlit best practices
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
                     ↓
              build_rag_context() → Chat IA (SSE streaming via generate_stream())
```

### 2.3 Session State Architecture

`ensure_settings(conn)` in `src/ui/settings.py` (called at the top of every tab render function) acts as the session-bootstrap. It lazily loads from DB on first access, then caches in `st.session_state`:

| Key | DB Source | Default Value |
|-----|-----------|---------------|
| `all_modalities` | `modalities` table (all rows) | Empty list (seeded by `init_db()`) |
| `active_modalities` | `modalities` WHERE `active=1 AND price>0 AND exams_per_hour>0` | Empty list |
| `prices` | Built from `active_modalities` (slug→price) | `{}` |
| `goal` | `monthly_goals` for current year-month | `45000.0` |
| `user_name` | `user_settings` key `"user_name"` | `"Galvani"` |
| `api_key` | `user_settings` key `"api_key"` | `""` |
| `llm_prompt` | `user_settings` key `"llm_prompt"` | Default system prompt (with `{user_name}` interpolated) |
| `llm_model` | `user_settings` key `"llm_model"` | `"openai/gpt-oss-120b:free"` |

**Analysis-tab specific state:**
- `historical_cache` — `{"key": "json_hash_of_ym_goal_modalities", "stats": {...}}` — invalidated when goal or active modalities change
- `goal_celebrated_YYYY-MM` — boolean guard for celebration rain (once per month)

**Chat IA specific state:**
- `messages` — list of `{"role": str, "content": str}` dicts for chat history (system + user/assistant pairs)
- `chat_suggestions` — temporary pill selection (popped after use)

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
color           TEXT NOT NULL DEFAULT '#64748B',
sort_order      INTEGER NOT NULL DEFAULT 0,
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
```
Seeded with 5 modalities by `_seed_modalities()` — all with production values (price, exams_per_hour, active=1). Colors are customizable per-modality via Settings tab `st.color_picker`. Users can add or remove modalities dynamically (since v1.4.0).

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

### Auto-migrations

**`_add_color_column()`** — Adds `color` column to `modalities` if missing (for DBs created before v1.3.0). Uses `PRAGMA table_info` to detect column existence, then `ALTER TABLE ADD COLUMN`. Backfills default colors from `MODALITY_COLORS` dict.

**`_migrate_v1_3_to_v1_4_defaults()`** — One-shot: applies production defaults (`_PRODUCTION_DEFAULTS`) to the 5 standard modalities, but only those still at price=0 AND active=0 (untouched by user). Preserves user-configured modalities as-is. Idempotent.

**`_migrate_v1_to_v2()`** — One-shot, idempotent v1→v2 migration:
- Trigger: v1 `daily_production` has rows AND v2 `daily_production_items` is empty
- Copies RM→ressonancia_magnetica, TC→tc_geral, RX→radiografia
- Copies latest prices from `exam_prices` (or DEFAULT_PRICES fallback)
- Activates those 3 modalities with prices and exams_per_hour

### Key CRUD Functions (src/db.py)

| Function | Operation | Pattern |
|----------|-----------|---------|
| `get_connection()` | Connection factory | `st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")` |
| `init_db(conn)` | DDL | `CREATE TABLE IF NOT EXISTS` for all 6 tables, then seed + all 3 migrations |
| `slugify(label)` | Utility | Portuguese text → URL-safe slug (NFKD normalization, ASCII transliteration) |
| `load_all_modalities(conn)` | Read | Returns all modalities ordered by label COLLATE NOCASE |
| `load_active_modalities(conn)` | Read | Returns only active AND price>0 AND exams_per_hour>0 |
| `save_modality(conn, slug, price, eph, active, label=None, color=None)` | Write | Updates single modality row; label/color optional (left unchanged if None) |
| `add_modality(conn, slug, label, price, eph, active, color)` | Create | Inserts new modality with auto-generated sort_order; returns False if slug exists |
| `delete_modality(conn, slug)` | Delete | Deletes child items THEN parent in transaction; returns False if slug not found |
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

## 4. The 5 Standard Modalities

Seeded from `_MODALITY_SEED` in `src/db.py` with production values from `_PRODUCTION_DEFAULTS`:

| # | Slug | Label (pt-BR) | Price (R$) | Exams/h | Color |
|---|------|---------------|------------|---------|-------|
| 1 | `angiotomografia` | Angiotomografia | 30.00 | 4.0 | `#0D9488` (Teal-600) |
| 2 | `radiografia` | Radiografia | 4.00 | 80.0 | `#2563EB` (Blue-600) |
| 3 | `ressonancia_magnetica` | Ressonância Magnética | 35.00 | 8.0 | `#7C3AED` (Violet-600) |
| 4 | `tc_geral` | TC Geral | 30.00 | 10.0 | `#6366F1` (Indigo-500) |
| 5 | `tc_abdome_total` | TC de Abdome Total | 60.00 | 5.0 | `#0891B2` (Cyan-600) |

Since v1.4.0, modalities are fully configurable: users can add new ones, remove existing ones (deletes associated production data), rename labels (slug is immutable after creation, auto-generated via `slugify()`), change prices, productivity rates, and colors.

---

## 5. Key Modules — Detailed Analysis

### 5.1 `app.py` (Entry Point, 61 lines)

- **Line 23:** `st.set_page_config(page_title="radtracker", page_icon=":material/monitor_heart:", layout="wide", initial_sidebar_state="auto")` — MUST be first Streamlit command
- **Lines 30–31:** DB boot: `conn = get_connection(); init_db(conn)` — idempotent, seeds + migrates
- **Line 34:** `render_sidebar(conn)`
- **Lines 37–42:** Navigation via horizontal `st.radio` with Material-icon-prefixed labels — **5 tabs**
- **Lines 44–52:** Tab index from `cookies.py` (fallback to 0), bounds check, cookie-persisted selection
- **Lines 54–63:** Dispatch to tab renderers based on `selected_idx`

### 5.2 `src/db.py` (Data Layer, ~420 lines)

Uses Streamlit's `st.connection()` pattern for managed SQLite. Key patterns:

- **`_MODALITY_SEED`**: 5 modality definitions with sort_order and color
- **`_PRODUCTION_DEFAULTS`**: dict slug→(label, price, exams_per_hour) for production values
- **`init_db()`**: Creates 6 tables, runs `_add_color_column()`, seeds modalities if empty, runs `_migrate_v1_3_to_v1_4_defaults()`, runs `_migrate_v1_to_v2()`
- **`slugify(label)`**: Normalizes Portuguese text: NFKD → ASCII transliteration → lowercase → `[^a-z0-9]+` → underscore → strip
- **`load_all_modalities()`**: Returns all rows ordered by label COLLATE NOCASE
- **`load_active_modalities()`**: Filters `active=1 AND price>0 AND exams_per_hour>0`
- **`save_modality(slug, price, eph, active, label=None, color=None)`**: Updates single modality; label/color unchanged when None
- **`add_modality(slug, label, price, eph, active, color)`**: Insert with auto sort_order; checks for duplicate slug
- **`delete_modality(slug)`**: Transactional: deletes from daily_production_items first, then modalities
- **`upsert_daily_items()`**: Smart insert/update; zero counts → DELETE rather than store zeros
- **`load_daily_items()`**: Dict slug→count
- **`load_month_items()`**: DataFrame of date, modality_slug, count
- **`load_prices()`**: Returns slug→price from active modalities

### 5.3 `src/calculations.py` (Business Logic, ~380 lines)

**Helper:**
- `_build_lookups(modalities)` → (slug→price, slug→exams_per_hour) dicts from modality list

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
| `compute_daily_stats(conn, date_str, active_modalities)` | dict with 12 keys | `today.py` |
| `compute_monthly_stats(conn, year_month, goal, active_modalities)` | dict with 9 keys | `month.py`, insights |
| `compute_historical_stats(conn, year_month, goal, active_modalities)` | dict with 11 keys (v2 items schema) | `analysis.py`, insights, LLM, chat RAG |

Key: all functions accept `active_modalities: list[dict]` — no hardcoded RM/TC/RX. `compute_historical_stats()` pivots from `daily_production_items` table. `_compute_daily_earnings_from_items()` aggregates items into daily earnings with per-modality count columns.

**Business constants:**
- `WORK_START_HOUR = 8`, `WORK_START_MINUTE = 0`

### 5.4 `src/chart_colors.py` (Color System, ~85 lines)

Central palette — **no inline hex values anywhere else in the codebase:**

```python
MODALITY_COLORS: dict[str, str] = {
    "radiografia": "#2563EB",              # Blue-600
    "tc_geral": "#6366F1",                 # Indigo-500
    "tc_abdome_total": "#0891B2",          # Cyan-600
    "ressonancia_magnetica": "#7C3AED",    # Violet-600
    "angiotomografia": "#0D9488",           # Teal-600
    "ultrassonografia": "#A855F7",          # Purple-500
    "dopplervelocimetria": "#059669",       # Emerald-600
    "radiografia_contrastada": "#475569",   # Slate-600
    "ultrassom_morfologico": "#0EA5E9",     # Sky-500
    "mamografia": "#BE123C",                # Rose-700
    "densitometria": "#A16207",             # Amber-700
}
```

- 11 colors retained for backward compatibility (new custom modalities get fallback `#64748B`)
- **`color_for_modality(slug, modalities=None)`** → returns DB-stored color when `modalities` list provided, falls back to hardcoded palette, then to `#64748B` (Slate-500)
- **`CHART_COLORS`** combines `MODALITY_COLORS` + legacy aliases (`"rm"`, `"tc"`, `"rx"`) + chart accent colors
- **`hex_to_rgba(hex, alpha)`** handles 3- and 6-char hex
- **`get_chart_text_color()`** theme-aware annotation color (dark: `#E5E7EB`, light: `#0F172A`, test-safe: `#0F172A`)

### 5.5 `src/charts.py` (Plotly Factories — Today/Month, ~330 lines)

All accept data as parameters; zero DB access:

| Function | Output | Key Details |
|----------|--------|-------------|
| `build_modality_bar(counts, labels_lookup, modalities)` | go.Figure | Horizontal bars, per-modality colors from DB via `color_for_modality()`, sorted ascending |
| `build_modality_donut(counts, labels_lookup, modalities)` | go.Figure | Dynamic: iterates over counts dict, per-modality colors, hole=0.5 (backward compat) |
| `build_daily_sparkline(df)` | go.Figure | Teal line + fill, DD/MM labels, last 1–7 rows |
| `build_progress_gauge(pct_goal)` | go.Figure | 4-segment stacked bar (teal gradient) + vline marker + annotation |
| `build_monthly_earnings_chart(df, daily_target, year_month)` | go.Figure | Full-range x-axis with zero-fill, dashed target line, today marker (annotated) |
| `build_monthly_modality_donut(df, active_modalities)` | go.Figure | Revenue-weighted (count × price), per-modality colors from DB |

### 5.6 `src/charts_analysis.py` (Analysis Chart Factories, ~300 lines)

| Function | Output | Key Details |
|----------|--------|-------------|
| `build_moving_averages_chart(df, year_month)` | go.Figure | MA7 (solid teal fill) + MA30 (dashed gray) for current month only |
| `build_wow_comparison_chart(weekly_data, df, active_modalities)` | go.Figure | Dynamic grouped bar per modality, prev week @ 50% opacity; single-week fallback |
| `build_modality_mix_evolution(mix_history, active_modalities)` | go.Figure | Dynamic stacked area (multi-month) or stacked bar (single month), abbreviated labels |
| `build_ytd_earnings_chart(df, year_month, goal)` | go.Figure | Monthly bar chart, current month highlighted, goal line with annotation |

### 5.7 `src/formatting.py` (Locale & Formatting, ~55 lines)

- `fmt_brl(value)` → `"R$ X.XXX,XX"` — uses `Decimal.quantize(ROUND_HALF_UP)` to avoid IEEE-754 floating-point artifacts. Negative values use Unicode minus sign `\u2212`.
- `md_escape(text)` → escapes `$` for Streamlit markdown (prevents LaTeX math-mode corruption). Use on any string containing R$ rendered via `st.markdown`, `st.expander`, `st.warning`, `st.info`, or `st.metric delta`.
- `MONTHS_PT` — dict mapping 1–12 → Portuguese month names (Janeiro–Dezembro)

### 5.8 `src/insights_rules.py` (Rule-Based Insights, ~230 lines)

- `generate_rule_insights(stats, active_modalities)` — pure function, dict + modality list → Portuguese markdown
- **Tone determination:** based on whether current pace can realistically hit goal (not fixed pct threshold)
  - 5 tones: `success`, `on_track`, `warning`, `danger`, plus edge cases for remaining=0
  - Uses daily_avg vs daily_needed comparison after ≥5 days worked
  - Early month: compares actual pct vs expected linear pct
- **Analysis blocks:** opening paragraph → projection (tone-dependent) → tone assessment → WoW trend → MoM trend → modality mix shift → consecutive-below-target → context-aware suggestion
- Plural awareness: `"dia"/"dias"`, `"resta"/"restam"`, `"restante"/"restantes"`
- Suggestion block finds highest-priced modality dynamically from active list
- All icons use `:material/` prefix (no emojis)

### 5.9 `src/llm_client.py` (OpenRouter LLM, ~290 lines)

**Configurable model:** constructor accepts `model` slug (default `"openai/gpt-oss-120b:free"`).

**Public RAG context builder (new in v1.5.0):**
- `build_rag_context(stats, active_mods, system_prompt=None)` → str
  - Enriches stats via `_enrich_stats()`, interpolates into `_USER_PROMPT_TEMPLATE`
  - Prepends custom or default system prompt with RAG data block
  - Used by chat UI to inject context before each chat session

**Class `LLMClient`:**
- `__init__(api_key, model, prompt=None)` — raises `LLMUnavailableError` if key is None/empty
- `generate(stats, active_modalities)` → str — one-shot, builds enriched prompt, calls OpenRouter, returns content (used by legacy analysis code)
- `generate_stream(messages)` → Generator[str, None, None] — SSE streaming (new in v1.5.0)
  - Accepts full message list (caller includes system prompt with RAG context)
  - Uses `httpx.stream()` with 30s timeout
  - Safe SSE parser: null-safe accessor chain (`data.get("choices") or [{}]`, etc.)
  - Skips malformed lines silently, handles `[DONE]` with whitespace
  - Raises `LLMUnavailableError` if no tokens yielded

**`_enrich_stats(stats, active_modalities)`** — extracts 20+ scalar metrics:
- MA7/MA30 latest, acceleration trend (last 2 weeks delta)
- Per-modality exam counts (current month only), modality breakdown lines
- Best day, ticket médio, historical monthly average, average exams/day

**`_USER_PROMPT_TEMPLATE`** — detailed Portuguese template with 4 sections: Meta e Ritmo, Tendências, Volume de Exames, Destaques do Mês

**`LLMUnavailableError`** — single exception class for all failure modes (timeout, HTTP error, rate limit, missing key, empty response)

### 5.10 `src/cookies.py` (Tab Persistence, ~30 lines)

- Uses `streamlit_extras.cookie_manager.cookie_manager()`
- `get_last_tab_index(default="0")` → str — reads `radtracker_last_tab` cookie
- `set_last_tab_index(tab_index)` → None — writes cookie
- Best-effort: silent fallback when cookies unavailable or not yet synced

---

## 6. UI Structure (Streamlit)

### 6.1 Navigation
- **Method:** `st.radio` with `horizontal=True`, `label_visibility="collapsed"`
- **5 tabs:** `:material/today: Hoje` | `:material/calendar_month: Mês Atual` | `:material/trending_up: Análise` | `:material/smart_toy: Chat IA` | `:material/settings: Configuração`
- **Persistence:** tab index saved to browser cookie `radtracker_last_tab`

### 6.2 Sidebar (`src/ui/sidebar.py`, ~85 lines)

- Header: "**radtracker**" + greeting "Olá, {user_name}."
- Date picker (`max_value=date.today()`, format `DD/MM/YYYY`)
- **Dynamic modality inputs:** iterates over `st.session_state.active_modalities`
  - Each modality: `st.columns([3, 1])` — label text in left column, `st.number_input` (label_visibility="collapsed") in right column
  - Keyed by `f"sidebar_{slug}_{date_str}"` for date-dependent pre-fill
- Pre-fill: loads existing data for selected date via `load_daily_items()`
- "Salvar produção" button — `type="primary", width="stretch"`, spinner on save, toast on success, clears historical_cache, `st.rerun()`
- Footer: `st.caption("radtracker v1.5 · local")`

### 6.3 "Hoje" Tab (`src/ui/today.py`, ~195 lines)

**Empty state:** Centered bordered container with `:material/content_paste:` icon + guidance text
**KPI Row** (4 bordered containers, stretch height):

| Card | Metric Label | Value | Delta |
|------|-------------|-------|-------|
| 1 | Faturamento hoje | `fmt_brl(earnings)` | `±X.X% vs ontem` (or "— sem dados de ontem") |
| 2 | Exames hoje | Total count | Per-modality counts with labels |
| 3 | Horas estimadas | `X.Xh` | Time range string |
| 4 | Meta mensal | `X%` | MTD / Goal + badge (green "No ritmo" or orange "Atenção") |

**Charts:** 2-column: Dynamic modality bar (left, horizontal, per-modality colors) + 7-day sparkline (right, auto-pulls from prev month if <7 days)
**Raw data:** Toggle via `streamlit_extras.stoggle`

### 6.4 "Mês Atual" Tab (`src/ui/month.py`, ~210 lines)

**Empty state:** Centered bordered container with `:material/calendar_month:` icon
**KPI Row:** MTD earnings, % goal, days worked, daily average (all with delta annotations)
**Progress gauge:** Plotly horizontal segmented bar (teal gradient, 4 segments)
**Star rating:** `star_rating(stars)` where `stars = min(5.0, pct_goal / 20.0)`
**Celebration:** `rain(emoji="🎉")` when `pct_goal >= 100` — per-month session_state guard
**Charts:** 2-column: Daily earnings line (left, with target line and today marker), Revenue donut (right, per-modality revenue)
**Rhythm alert:** `st.warning` when behind pace (≥5 days AND `pct_goal < linear_expected_pct` AND not at goal yet). Uses `md_escape(fmt_brl(...))` throughout.
**Raw data:** Toggle via `streamlit_extras.stoggle`

### 6.5 "Análise" Tab (`src/ui/analysis.py`, ~130 lines)

**Loading state:** Skeleton placeholders before computing stats, with `st.spinner`
**Cache:** `historical_cache` key = JSON hash of (year_month, goal, modality_slugs/prices)

**Insights expander** (expanded by default):
- Rule-based text from `generate_rule_insights(stats, active_modalities)`
- Rendered with `md_escape()` before `st.markdown()`
- Caption: "Análise automática baseada nos seus dados"

**Note:** AI section was removed from this tab in v1.5.0 — full AI functionality moved to the Chat IA tab.

**4 charts:**
1. MA7/MA30 (left) — same-month moving averages
2. WoW comparison (right) — dynamic grouped bar per modality
3. Modality mix evolution (full-width) — dynamic stacked area by month
4. YTD earnings (full-width) — monthly bars + goal line

### 6.6 "Chat IA" Tab (`src/ui/chat.py`, ~280 lines, new in v1.5.0)

**Entry point:** `render_chat_tab(conn)` — `@st.fragment` for isolated rerun scope.

**Pastel avatar colors:** Custom CSS via `st.html()` — assistant `#34D399` (emerald), user `#60A5FA` (blue).

**Flow:**
1. No API key → friendly empty state with OpenRouter signup link
2. No messages → initial screen with "Iniciar análise" button
3. Button click → `_trigger_initial_report()` computes stats, builds RAG context via `build_rag_context()`, queues "Gere um relatório completo..." message
4. Message rendering: skips system messages, renders user/assistant with `md_escape()`
5. Pending dispatcher: if last message is from user → `_stream_response()` for streaming reply
6. Chat input: `st.chat_input()` appends to messages, triggers rerun
7. Suggestion pills: 5 follow-up questions rendered below conversation after initial report
8. "Novo chat" button: clears messages + historical_cache

**Streaming implementation:**
- `LLMClient.generate_stream(st.session_state.messages)` returns token generator
- `safe_stream = (token.replace("$", "\\$") for token in stream)` — escapes `$` for Streamlit Markdown
- `st.write_stream(safe_stream)` renders tokens progressively
- Error handling: catches `LLMUnavailableError` and generic `Exception`, shows error in chat

**History management:**
- `_trim_history()` called before each LLM call
- Cap: system message + `_MAX_MESSAGE_PAIRS` (15) user/assistant pairs = 31 messages max
- Older pairs dropped from the front (preserves system message at index 0)

### 6.7 "Configuração" Tab (`src/ui/settings.py`, ~340 lines)

Three `@st.fragment` sections:

**Modality grid:**
- Subheader + caption explaining the grid
- Header row: Modalidade | Preço (R$) | Exames/h | Cor | Ativo | (delete)
- Dynamic rows: iterates `st.session_state.all_modalities`
  - Each row: `st.columns([3, 2, 2, 0.4, 0.3, 0.3])` — label | price | exams/h | color_picker | active checkbox | delete button
  - Tracks changed rows via comparison with loaded values
  - "Salvar modalidades" button when changes detected
  - Inline delete confirmation flow (warning + Confirmar/Cancelar buttons)
- Add modality section: toggle via `new_modality_pending` flag
  - Inputs: label (with slug preview), price, exams/h, color_picker
  - Save validates uniqueness, cancel resets state
- `_reload_modalities()` helper clears caches and reloads from DB

**LLM section:**
- Monthly goal (`st.number_input`, step 100.0)
- User name
- API key (`type="password"`) with OpenRouter link
- LLM model slug (`st.text_input`, warns if format missing `provedor/modelo`)
- System prompt (`st.text_area`, height=200, `{user_name}` placeholder)
- "Salvar configurações" button — persists to DB + session_state, clears historical_cache

**Danger zone:**
- 2-step confirmation: "Limpar todos os dados" → "Sim, limpar tudo" / "Cancelar"
- `_execute_delete()` → raw `sqlite3` DELETE FROM all 6 tables, resets session_state, clears `st.cache_data`

---

## 7. Theme & Branding

### 7.1 Design Philosophy (Cal.com-inspired)
Defined in `.streamlit/config.toml` and `docs/DESIGN.md`:
- **White canvas** (`#FFFFFF`), **near-black** (`#111111`)
- Light-gray secondary surfaces (`#F8F9FA`, `#E5E7EB`)
- **No emojis in UI** — Material icons exclusively
- **No custom CSS/`unsafe_allow_html`** — all theming via config.toml (exception: `st.html()` in chat.py for avatar colors only)
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
| `httpx` | ≥0.27.0 | HTTP client for OpenRouter (one-shot + streaming) |
| `sqlalchemy` | ≥2.0.0 | SQL abstraction (via `st.connection`) |
| `streamlit-extras` | ≥1.5.0 | Skeleton, rain, star_rating, stoggle, cookies, pills |

### 8.2 Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥8.0.0 | Test runner |
| `pytest-cov` | ≥6.0.0 | Coverage reporting |
| `respx` | ≥0.21.0 | HTTP mock for LLM client tests |
| `ruff` | ≥0.11.0 | Linting (E, F, I, UP rules, line-length 100) |
| `mypy` | ≥1.15.0 | Type checking |
| `yamllint` | ≥1.38.0 | YAML linting |
| `ansible-lint` | ≥26.4.0 | Ansible playbook linting |

### 8.3 Linter Configs (for deployment-layer files)

| Tool | Config File | Purpose |
|------|-----------|---------|
| `ansible-lint` | `.ansible-lint.yml` | Ansible playbook rules |
| `hadolint` | `.hadolint.yml` | Dockerfile rules |
| `yamllint` | `.yamllint.yml` | YAML: 2-space indent, disable line-length, ignore ansible/templates/ |

---

## 9. Test Coverage

### 9.1 Status (2026-05-06)
**150 passed, 0 failed** in ~2.30s.
Run: `uv run pytest tests/ -v`

### 9.2 Module-Level Coverage

| Module | Tests | Notes |
|--------|-------|-------|
| `test_calculations.py` | 32 | Earnings, hours, daily/monthly/historical stats, MA, WoW, MoM (v2 dynamic) |
| `test_chart_colors.py` | 14 | hex_to_rgba, 11 modality colors, legacy aliases, uniqueness, color_for_modality with DB lookup |
| `test_charts.py` | 3 | Chart figure structure validation |
| `test_db.py` | 54 | Schema (v2), seed, CRUD, add/delete modality, migration (v1→v2, v1.3→v1.4, color column), backward compat |
| `test_formatting.py` | 9 | BRL currency (IEEE-754 trap for 1.005), md_escape, negative values, month constants |
| `test_insights.py` | 10 | Tone detection, dynamic modality labels, trends, mix shifts |
| `test_llm_client.py` | 28 | One-shot success/errors, SSE streaming, RAG context builder, prompt building, multi-month filtering |
| UI modules | 0 | No Streamlit runtime — excluded by design |

### 9.3 Test Infrastructure
- `FakeConnection` in `conftest.py` — emulates `st.connection` with SQLite `:memory:`, v2 schema (6 tables with `color` column)
- `conn` fixture: full 6-table schema initialized in `:memory:`
- `seeded_conn` fixture: conn with 5 seeded modalities + production values
- `active_modalities` fixture: list of 5 active modality dicts with production values
- `default_prices` fixture: copy of `DEFAULT_PRICES` dict
- LLM tests: `@respx.mock` for HTTP interception (both one-shot and streaming)
- Insights tests: `_make_stats()` factory for building stats dicts

---

## 10. Deployment Infrastructure

Self-hosted deployment to a VPS via Docker + Caddy + fail2ban, managed with Ansible.

### 10.1 Architecture

```
Browser → Caddy (:80/:443) → Streamlit (:8501 loopback)
                ↓
          BasicAuth + Let's Encrypt (auto TLS)
          fail2ban watches /var/log/caddy/access.log for 401s
```

**Two modes:** LAN (HTTPS with self-signed cert) and Internet (real domain, Let's Encrypt).

**Security layers:**
1. Caddy BasicAuth on all routes
2. Streamlit only on loopback (127.0.0.1:8501)
3. fail2ban blocks IPs after 5 failed auth attempts in 10 minutes (1-hour ban)
4. fail2ban whitelists local/RFC1918 networks
5. Non-root container user (uid 1000)

### 10.2 Docker

**`Dockerfile`** — Multi-stage build:
- **Stage 1 (builder):** `python:3.12-slim`, installs `uv`, pins production deps
- **Stage 2 (runtime):** Copies venv, creates `streamlit` user (uid 1000), runs as non-root
- Healthcheck via `/_stcore/health`

**`docker-compose.yml`** — Two services:
- **`streamlit`**: Build from Dockerfile, `127.0.0.1:8501:8501`, mem_limit 512m, cpus 1.0
- **`caddy`**: `caddy:2-alpine`, ports 80 + 443
- Both share `radtracker` bridge network

### 10.3 Ansible

5 playbooks: `deploy.yml` (bootstrap + deploy, idempotent), `update.yml` (git update via deploy key, preserves data/), `health.yml`, `backup.yml`, `cleanup.yml`.

Git authentication via ed25519 deploy key auto-generated on VPS and registered on GitHub via API.

---

## 11. Key File Reference

| File | Lines | Key Lines | Purpose |
|------|-------|-----------|---------|
| `app.py` | 61 | L23, L37–42, L54–63 | Page config, 5-tab navigation, dispatch |
| `src/db.py` | ~420 | `_MODALITY_SEED`, `_PRODUCTION_DEFAULTS`, `init_db()`, `slugify()`, `add_modality()`, `delete_modality()`, `upsert_daily_items()`, migrations | DB schema, seed, CRUD, migration |
| `src/calculations.py` | ~380 | `_build_lookups()`, `compute_earnings()`, `estimate_hours()`, `compute_daily_stats()`, `compute_monthly_stats()`, `compute_historical_stats()` | Business logic |
| `src/chart_colors.py` | ~85 | `MODALITY_COLORS`, `color_for_modality()`, `CHART_COLORS`, `hex_to_rgba()`, `get_chart_text_color()` | Color system |
| `src/charts.py` | ~330 | `build_modality_bar()`, `build_modality_donut()`, `build_daily_sparkline()`, `build_progress_gauge()`, `build_monthly_earnings_chart()`, `build_monthly_modality_donut()` | Chart factories |
| `src/charts_analysis.py` | ~300 | `build_moving_averages_chart()`, `build_wow_comparison_chart()`, `build_modality_mix_evolution()`, `build_ytd_earnings_chart()` | Analysis charts |
| `src/formatting.py` | ~55 | `MONTHS_PT`, `md_escape()`, `fmt_brl()` | Locale + formatting |
| `src/insights_rules.py` | ~230 | `generate_rule_insights()` | Rule-based insights |
| `src/llm_client.py` | ~290 | `LLMUnavailableError`, `build_rag_context()`, `LLMClient.__init__()`, `LLMClient.generate()`, `LLMClient.generate_stream()`, `_enrich_stats()`, `_USER_PROMPT_TEMPLATE` | OpenRouter LLM + RAG |
| `src/cookies.py` | ~30 | `get_last_tab_index()`, `set_last_tab_index()` | Tab cookie persistence |
| `src/ui/sidebar.py` | ~85 | `render_sidebar()` | Dynamic sidebar form |
| `src/ui/today.py` | ~195 | `render_today_tab()`, `_render_kpi_row()`, `_build_sparkline_figure()` | Today dashboard |
| `src/ui/month.py` | ~210 | `render_month_tab()`, `_render_rhythm_alert()`, `_maybe_celebrate()` | Month dashboard |
| `src/ui/analysis.py` | ~130 | `render_analysis_tab()`, `_render_insight_body()` | Analysis + insights |
| `src/ui/chat.py` | ~280 | `render_chat_tab()`, `_trigger_initial_report()`, `_stream_response()`, `_trim_history()`, `_render_suggestion_chips()` | Chat IA with streaming |
| `src/ui/settings.py` | ~340 | `ensure_settings()`, `_render_modality_grid()`, `_render_llm_section()`, `_render_danger_zone()`, `_reload_modalities()` | Settings + modality config |
| `.streamlit/config.toml` | 60 | Full theme config | Colors, fonts, dark mode |
| `tests/conftest.py` | ~155 | `FakeConnection`, `conn`, `seeded_conn`, `active_modalities`, `default_prices` | Test infrastructure |
