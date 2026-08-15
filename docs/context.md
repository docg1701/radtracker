# radtracker — Comprehensive Project Context

**Generated:** 2026-08-14
**Version:** v1.8.1
**Test status:** 294 passed, 0 failed (2026-08-14)

---

## 1. Project Purpose

**radtracker** is a personal productivity dashboard for a teleradiology physician. It tracks daily exam counts across **configurable dynamic modalities**, converts them into earnings in Brazilian Real (BRL), monitors progress toward monthly revenue goals, and generates analytical insights — both rule-based and AI-driven (OpenRouter, configurable model slug).

The app is a **Streamlit single-page dashboard** with local SQLite persistence. Single-user by design, with **app-level authentication** (username + scrypt password + optional TOTP 2FA) implemented by the `feat/app-auth` branch: gate in `src/ui/login.py`, state in `data/auth.json` (a JSON file, not DB tables), signed session cookie for persistence across refreshes. See `docs/auth-implementation-plan.md`.

**Self-hosted deployment** is supported via Docker + Caddy (reverse proxy with automatic HTTPS — no BasicAuth, authentication lives in the app) + fail2ban (sshd jail), managed with Ansible playbooks.

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
├── Caddyfile               # Reverse proxy config: access logging, cache headers, streamlit upstream (auth in app)
├── .env.example            # Template: DOMAIN + TZ (use with Ansible .env.j2)
├── .dockerignore           # Exclude secrets, data, git, caddy dirs, tests from build context
├── src/
│   ├── __init__.py         # Empty package marker
│   ├── auth_crypto.py      # stdlib crypto: scrypt passwords, RFC 6238 TOTP, HMAC session tokens
│   ├── auth_store.py       # auth.json load/save/validate + pure gate helpers (no Streamlit)
│   ├── auth_bootstrap.py   # Non-interactive bootstrap run by Ansible (reads data/.auth_creds)
│   ├── db.py               # SQLite schema (v2, 5 tables) + CRUD + price vigency + seed + migration
│   ├── calculations.py     # Business logic (earnings, hours, MA, projections, stats)
│   ├── charts.py           # Plotly charts (bar, donut, sparkline, gauge, monthly earnings, modality donut)
│   ├── charts_analysis.py  # Analysis charts (MA7/MA30, WoW, mix evolution, YTD)
│   ├── chart_colors.py     # 11 modality colors + legacy aliases + hex_to_rgba + DB-based color lookup
│   ├── formatting.py       # fmt_brl (BRL currency), md_escape ($ for Markdown), MONTHS_PT
│   ├── insights_rules.py   # Rule-based insights engine (dynamic modalities)
│   ├── llm_client.py       # OpenRouter client (one-shot + SSE streaming) + RAG context builder
│   ├── cookies.py          # Cookies: tab persistence + signed session token (streamlit-extras)
│   └── ui/
│       ├── __init__.py
│       ├── sidebar.py      # Dynamic data entry form (date + N modality inputs)
│       ├── today.py        # "Hoje" tab — KPI cards, modality bar, sparkline (dynamic)
│       ├── month.py        # "Mês Atual" tab — gauge, line chart, rhythm alert, celebration
│       ├── analysis.py     # "Análise" tab — rule insights + 4 analysis charts (AI section removed in 1.5.0)
│       ├── chat.py         # "Chat IA" tab — RAG-powered streaming chat (new in 1.5.0)
│       ├── login.py        # Auth gate: session restore, login, TOTP, 2FA banner, logout
│       └── settings.py     # "Config" tab — modality grid + add/delete, goal, LLM, danger zone
├── ansible/                # Self-hosted deployment automation
│   ├── ansible.cfg         # pipelining; ForwardAgent removed (deploy key)
│   ├── inventory.yml       # VPS_HOST + VPS_USER via env vars
│   ├── requirements.yml    # community.docker + community.crypto collections
│   ├── group_vars/
│   │   └── all.yml         # Shared vars + Vault-encrypted secrets
│   ├── templates/
│   │   ├── Caddyfile.j2    # Caddy template (LAN or internet mode)
│   │   └── .env.j2         # Docker env_file template (DOMAIN + TZ)
│   └── playbooks/
│       ├── deploy.yml      # Bootstrap + deploy (idempotent)
│       ├── update.yml      # Git update via deploy key + rebuild (preserves data/)
│       ├── health.yml      # Container health, Streamlit endpoint, fail2ban
│       ├── backup.yml      # SQLite dump via docker exec + integrity check
│       └── cleanup.yml     # Full VPS reset
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # FakeConnection (v2 schema) + conn/seeded_conn/active_modalities fixtures
│   ├── test_auth_crypto.py   # 26 tests — scrypt, RFC 6238 vectors, TOTP window, session tokens
│   ├── test_auth_store.py    # 25 tests — auth.json schema/atomic save, gate helpers
│   ├── test_auth_bootstrap.py # 8 tests — subprocess bootstrap (creds file, idempotency, exit codes)
│   ├── test_calculations.py  # 32 tests — pure functions + DB stats + historical (v2 dynamic)
│   ├── test_chart_colors.py  # 14 tests — hex_to_rgba + 11 modality colors + legacy aliases
│   ├── test_charts.py        # 3 tests — chart figure structure validation
│   ├── test_db.py            # 54 tests — v2 schema, seed, CRUD, migration, add/delete, v1 backward compat
│   ├── test_formatting.py    # 9 tests — BRL formatting, md_escape, month constants
│   ├── test_insights.py      # 10 tests — dynamic modality insights, tone, trends, mix shifts
│   └── test_llm_client.py    # 28 tests — success, errors, streaming, RAG context, prompt building
├── scripts/
│   ├── import_csv.py       # CSV import tool for legacy data (assemed + radiplan)
│   └── manage_auth.py      # Auth CLI (SSH): 2FA QR/activate/disable, password, username, status, repair
├── data/                   # SQLite DB + auth state (gitignored)
│   ├── .gitkeep
│   ├── telerrad.db         # Main database (gitignored)
│   └── auth.json           # Auth state: password hash, TOTP + session secrets (gitignored)
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

### 3.3 `modality_prices` — Price vigency history (price per modality per date)
```sql
slug            TEXT NOT NULL,
price           REAL NOT NULL,
effective_from  TEXT NOT NULL,     -- ISO date "YYYY-MM-DD"
created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
PRIMARY KEY (slug, effective_from),
FOREIGN KEY (slug) REFERENCES modalities(slug)
```
A price change today opens a new vigency from today; the past keeps the
vigency that was in effect at the time (`load_prices_at(conn, date)`).

### 3.4 `monthly_goals` — Per-month revenue targets
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

**`_migrate_v1_3_to_v1_4_defaults()`** — One-shot (guarded by `user_settings` flag `migration_v1_4_defaults_done`): applies production defaults (`_PRODUCTION_DEFAULTS`) to the 5 standard modalities only if still at price=0 AND active=0 (untouched by user). Never reactivates user-deactivated/zeroed modalities on subsequent boots.

**`_migrate_v1_cleanup()`** — One-shot (flag `migration_v1_cleanup_done`): drops legacy v1 tables `daily_production` and `exam_prices` only after `daily_production_items` is populated.

**`_backfill_price_vigencies()`** — One-shot: seeds `modality_prices` with each modality's current price vigent since its first production record (or `created_at` if no items).

### Key CRUD Functions (src/db.py)

| Function | Operation | Pattern |
|----------|-----------|---------|
| `get_connection()` | Connection factory | `st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")` |
| `init_db(conn)` | DDL | `CREATE TABLE IF NOT EXISTS` for all 5 tables, then seed + 3 one-shot migrations |
| `slugify(label)` | Utility | Portuguese text → URL-safe slug (NFKD normalization, ASCII transliteration) |
| `load_all_modalities(conn)` | Read | Returns all modalities ordered by label COLLATE NOCASE |
| `load_active_modalities(conn)` | Read | Returns only active AND price>0 AND exams_per_hour>0 |
| `save_modality(conn, slug, price, eph, active, label=None, color=None)` | Write | Updates single modality row; label/color optional (left unchanged if None) |
| `add_modality(conn, slug, label, price, eph, active, color)` | Create/Reactivate | Inserts new modality with auto sort_order; returns False if slug is active, reactivates an inactive slug with the new values (preserves production) |
| `deactivate_modality(conn, slug)` | Soft-delete | Sets `active=0`, preserves the row and all `daily_production_items`; returns False if slug not found |
| `upsert_daily_items(conn, date, items)` | Write | Dict slug→count; zero=DELETE, non-zero=UPSERT |
| `load_daily_items(conn, date)` | Read | Returns dict slug→count |
| `load_month_items(conn, year_month)` | Read | DataFrame with date, modality_slug, count |
| `save_price_vigency(conn, slug, price, effective_from)` | Write | UPSERT a price-vigency row |
| `load_prices_at(conn, date_str)` | Read | Returns slug→price vigent on the given date |
| `load_price_vigencies(conn)` | Read | All price-vigency rows |
| `load_goal(conn, year_month)` | Read | Carry-forward: returns the most recent prior month's goal; DEFAULT_GOAL (45000.0) only when no goal was ever recorded |
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

Since v1.4.0, modalities are fully configurable: users can add new ones, deactivate existing ones (soft-delete: preserves production history; reactivating with the same slug restores it), rename labels (slug is immutable after creation, auto-generated via `slugify()`), change prices (opens a new price vigency from today; the past keeps its vigency), productivity rates, and colors.

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
- **`init_db()`**: Creates 5 tables (modalities, daily_production_items, modality_prices, monthly_goals, user_settings), runs `_add_color_column()`, seeds modalities if empty, then one-shot migrations (`_migrate_v1_3_to_v1_4_defaults`, `_backfill_price_vigencies`, `_migrate_v1_cleanup`), all guarded by `user_settings` flags
- **`slugify(label)`**: Normalizes Portuguese text: NFKD → ASCII transliteration → lowercase → `[^a-z0-9]+` → underscore → strip
- **`load_all_modalities()`**: Returns all rows ordered by label COLLATE NOCASE
- **`load_active_modalities()`**: Filters `active=1 AND price>0 AND exams_per_hour>0`
- **`save_modality(slug, price, eph, active, label=None, color=None)`**: Updates single modality; label/color unchanged when None
- **`add_modality(slug, label, price, eph, active, color)`**: Insert with auto sort_order; checks for duplicate slug
- **`deactivate_modality(slug)`**: Soft-delete (`active=0`), preserves row + production history; UI hides it but past stats are intact
- **`add_modality(slug, label, price, eph, active, color)`**: Inserts new; reactivates inactive slug with new values; returns False if slug already active
- **`save_modality(slug, price, eph, active, label, color)`**: Updates; on real price change (>0, != old) opens a new `modality_prices` vigency from today; label/color/active edits do not rewrite history
- **`save_price_vigency(slug, price, effective_from)`** / **`load_prices_at(date)`** / **`load_price_vigencies()`**: price-vigency CRUD
- **`upsert_daily_items()`**: Smart insert/update; zero counts → DELETE rather than store zeros
- **`load_daily_items()`**: Dict slug→count
- **`load_month_items()`**: DataFrame of date, modality_slug, count
- **`load_goal(year_month)`**: Carry-forward — most recent prior month's goal; DEFAULT_GOAL only when none ever recorded

### 5.3 `src/calculations.py` (Business Logic, ~380 lines)

**Helper:**
- `_build_lookups(modalities)` → (slug→price, slug→exams_per_hour) dicts from modality list

**Pure functions (no DB access):**

| Function | Inputs → Output | Purpose |
|----------|-----------------|---------|
| `compute_earnings(counts, prices)` | dict[str,int] + dict[str,float] → float | `sum(count×price)` over all slugs |
| `estimate_hours(counts, exams_per_hour)` | dict[str,int] + dict[str,float] → float | Sum of count/rate per modality |
| `compute_delta_pct(today, yesterday)` | float + float\|None → float\|None | % change, returns None for zero/NULL |
| `compute_daily_target(goal, days)` | float + int → float | `goal / days` |

**DB-dependent functions:**

| Function | Returns | Used By |
|----------|---------|---------|
| `compute_daily_stats(conn, date_str, active_modalities)` | dict with 8 keys | `today.py` |
| `compute_monthly_stats(conn, year_month, goal, active_modalities, today=None)` | dict with 10 keys (dias corridos) | `month.py`, insights |
| `compute_historical_stats(conn, year_month, goal, active_modalities)` | dict with 11 keys (v2 items schema) | `analysis.py`, insights, LLM, chat RAG |

Key: all functions accept `active_modalities: list[dict]` — no hardcoded RM/TC/RX. `compute_monthly_stats` counts in **dias corridos** (every day is work-eligible): `daily_avg = mtd/elapsed_days`, `remaining_days = total - elapsed` (today excluded from remaining when it already has production), `days_worked` (days with ≥1 exam) is a displayed statistic only. `today` is injectable for deterministic tests. `compute_historical_stats()` pivots from `daily_production_items` table. `_compute_daily_earnings_from_items()` aggregates items into daily earnings with per-modality count columns.

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
- `_execute_delete()` → raw `sqlite3` DELETE FROM all 5 tables, resets session_state, clears `st.cache_data`

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
- `FakeConnection` in `conftest.py` — emulates `st.connection` with SQLite `:memory:`, v2 schema (5 tables with `color` column)
- `conn` fixture: full 5-table schema initialized in `:memory:`
- `seeded_conn` fixture: conn with 5 seeded modalities + production values
- `active_modalities` fixture: list of 5 active modality dicts with production values
- LLM tests: `@respx.mock` for HTTP interception (both one-shot and streaming)
- Insights tests: `_make_stats()` factory for building stats dicts

---

## 10. Deployment Infrastructure

Self-hosted deployment to a VPS via Docker + Caddy + fail2ban, managed with Ansible.

### 10.1 Architecture

```
Browser → Caddy (:80/:443) → Streamlit (:8501 loopback)
                ↓
          TLS (Let's Encrypt in internet mode; self-signed cert on LAN)
          app-level login gate (src/ui/login.py, data/auth.json)
          fail2ban: sshd jail only — no Caddy 401 jail (the app never returns 401)
```

**Two modes:** LAN (HTTPS with self-signed cert — Caddy redirects HTTP→HTTPS) and Internet (real domain, Let's Encrypt).

**Security layers:**
1. App-level authentication (username + scrypt password + optional TOTP 2FA)
2. Session persistence: HMAC-signed cookie, 30-day expiry (logout and password change revoke it)
3. 2FA setup/reset only via SSH (`radtracker-auth`); QR renders in the terminal, never on the web
4. Streamlit only on loopback (127.0.0.1:8501)
5. fail2ban sshd jail blocks SSH brute force (5 failures / 10 min → 1-hour ban)
6. fail2ban whitelists local/RFC1918 networks
7. Non-root container user (uid 1000)

### 10.2 Docker

**`Dockerfile`** — Multi-stage build:
- **Stage 1 (builder):** `python:3.12-slim`, installs `uv`, pins production deps
- **Stage 2 (runtime):** Copies venv, creates `streamlit` user (uid 1000), runs as non-root
- Installs `qrencode` (TOTP QR rendered in the terminal by `manage_auth.py`)
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
| `app.py` | 94 | L1–30, L36–62 | Page config, auth gate + cookie manager, 5-tab navigation, dispatch |
| `src/auth_crypto.py` | 134 | `hash_password()`, `verify_totp()`, `totp_code()`, `sign_session()`, `verify_session()` | stdlib crypto (scrypt, RFC 6238, HMAC tokens) |
| `src/auth_store.py` | 156 | `load_auth()`, `save_auth()`, `create_bootstrap_auth()`, `verify_login()`, `verify_session_token()` | auth.json persistence + pure gate helpers |
| `src/auth_bootstrap.py` | 70 | `main()`, `_parse_creds()` | Ansible bootstrap (data/.auth_creds → data/auth.json) |
| `src/db.py` | ~710 | `_MODALITY_SEED`, `_PRODUCTION_DEFAULTS`, `init_db()`, `slugify()`, `add_modality()`, `deactivate_modality()`, `save_modality()`, `save_price_vigency()`, `load_prices_at()`, `upsert_daily_items()`, migrations | DB schema, seed, CRUD, price vigency, migration |
| `src/calculations.py` | ~510 | `_build_lookups()`, `_month_time_window()`, `compute_earnings()`, `estimate_hours()`, `compute_daily_stats()`, `compute_monthly_stats()`, `compute_historical_stats()`, `attach_revenue()` | Business logic (price-vigent revenue, calendar-day counting) |
| `src/chart_colors.py` | ~85 | `MODALITY_COLORS`, `color_for_modality()`, `CHART_COLORS`, `hex_to_rgba()`, `get_chart_text_color()` | Color system |
| `src/charts.py` | ~330 | `build_modality_bar()`, `build_modality_donut()`, `build_daily_sparkline()`, `build_progress_gauge()`, `build_monthly_earnings_chart()`, `build_monthly_modality_donut()` | Chart factories |
| `src/charts_analysis.py` | ~300 | `build_moving_averages_chart()`, `build_wow_comparison_chart()`, `build_modality_mix_evolution()`, `build_ytd_earnings_chart()` | Analysis charts |
| `src/formatting.py` | ~55 | `MONTHS_PT`, `md_escape()`, `fmt_brl()` | Locale + formatting |
| `src/insights_rules.py` | ~130 | `_projection_scenarios()`, `generate_rule_insights()` | Rule-based insights (factual + 3 projection scenarios) |
| `src/llm_client.py` | ~430 | `LLMUnavailableError`, `build_rag_context()`, `LLMClient.__init__()`, `LLMClient.generate()`, `LLMClient.generate_stream()`, `_enrich_stats()`, `_USER_PROMPT_TEMPLATE` | OpenRouter LLM + RAG |
| `src/cookies.py` | 79 | `get_cookie_manager()`, `get_last_tab_index()`, `set_last_tab_index()`, `get_session_token()`, `set_session_token()`, `delete_session_token()` | Tab cookie + signed session cookie (one manager construction per run) |
| `src/ui/sidebar.py` | ~85 | `render_sidebar()` | Dynamic sidebar form |
| `src/ui/today.py` | ~195 | `render_today_tab()`, `_render_kpi_row()`, `_build_sparkline_figure()` | Today dashboard |
| `src/ui/month.py` | ~225 | `render_month_tab()`, `_should_show_rhythm_alert()`, `_render_rhythm_alert()`, `_maybe_celebrate()` | Month dashboard |
| `src/ui/analysis.py` | ~130 | `render_analysis_tab()`, `_render_insight_body()` | Analysis + insights |
| `src/ui/chat.py` | ~280 | `render_chat_tab()`, `_trigger_initial_report()`, `_stream_response()`, `_trim_history()`, `_render_suggestion_chips()` | Chat IA with streaming |
| `src/ui/login.py` | 110 | `render_login_gate()`, `render_logout_button()`, `_restore_session()`, `_establish_session()` | Auth gate (restore/login/TOTP/banner/logout) — only st.form usage |
| `src/ui/settings.py` | ~340 | `ensure_settings()`, `_render_modality_grid()`, `_render_llm_section()`, `_render_danger_zone()`, `_reload_modalities()` | Settings + modality config |
| `.streamlit/config.toml` | 60 | Full theme config | Colors, fonts, dark mode |
| `tests/conftest.py` | ~155 | `FakeConnection`, `conn`, `seeded_conn`, `active_modalities`, `default_prices` | Test infrastructure |
| `scripts/manage_auth.py` | 180 | `main()`, `_enable_2fa()`, `_change_password()`, `_repair()` | SSH auth CLI (KIAUH-style menu) |
