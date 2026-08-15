# radtracker — Meta-Prompt for LLM Sessions

**Purpose:** Drop this into any LLM session to immediately re-establish full project context and start coding.

---

## Goal

You are working on **radtracker**, a personal productivity dashboard for a teleradiology physician. It's a Streamlit (≥1.54) single-page app with local SQLite persistence. The UI is in Brazilian Portuguese. Production deployment on Oracle Cloud Free Tier (VM.Standard.E2.1.Micro, Ubuntu 24.04, 1 OCPU / 1 GB RAM) via Docker + Caddy + fail2ban, managed with Ansible playbooks. Local dev VPS at 10.10.10.209 (LAN, galvani).

You will be modifying Python code in the `src/` tree, the Streamlit entry point `app.py`, the config `.streamlit/config.toml`, the test suite in `tests/`, Docker/deployment files at the project root, or Ansible playbooks in `ansible/`.

**Current release:** v1.7.9.

---

## Tech Stack

| Layer | Tech | Notes |
|-------|------|-------|
| Framework | **Streamlit ≥1.54** | Single-page, wide layout, `st.connection` for DB |
| Database | **SQLite** via SQLAlchemy + `st.connection` | File at `data/telerrad.db` (gitignored) |
| Charts | **Plotly ≥5.18** | All chart factories in `src/charts.py` and `src/charts_analysis.py` |
| Data | **Pandas ≥2.0** | DataFrames for calculations and chart data |
| HTTP | **httpx ≥0.27** | OpenRouter API calls (one-shot + SSE streaming) |
| Extras | **streamlit-extras ≥1.5** | `skeleton`, `rain`, `star_rating`, `stoggle`, `cookie_manager`, `pills` |
| Auth | **stdlib scrypt + TOTP (RFC 6238) + HMAC session cookie** | `src/auth_crypto.py`, `src/auth_store.py`, `data/auth.json` |
| Package mgr | **uv** | `uv.lock` is authoritative |
| Tests | **pytest ≥8.0**, **respx** for HTTP mocking | 294 tests, all passing |
| Lint/fmt | **ruff** (E, F, I, UP rules, line-length 100) | Run: `uv run ruff check src/ tests/` |
| Types | **mypy** (strict=false) | Run: `uv run mypy src/` |
| **Deployment** | | |
| Container | **Docker** (multi-stage build, non-root user) | `Dockerfile` + `docker-compose.yml` |
| Reverse proxy | **Caddy 2** (TLS + Let's Encrypt, no BasicAuth — auth lives in the app) | `Caddyfile`, Jinja2 template in `ansible/templates/` |
| Automation | **Ansible** (5 playbooks, Vault encryption) | `ansible/` directory |
| Security | **fail2ban** (sshd jail) | Jail in `deploy.yml` playbook |

---

## Key Files (Read these first for any task)

### Application core (Python)
1. **`app.py`** (94 lines) — Entry point, page config, auth gate + cookie manager, DB boot, 5-tab navigation
2. **`src/auth_crypto.py`** (134 lines) — stdlib crypto: scrypt password hashing, RFC 6238 TOTP, otpauth URI, HMAC session tokens
3. **`src/auth_store.py`** (156 lines) — `data/auth.json` load/save/validate (atomic 0600) + pure gate helpers
4. **`src/auth_bootstrap.py`** (70 lines) — non-interactive bootstrap run by Ansible (reads `data/.auth_creds`)
5. **`src/db.py`** (~420 lines) — All SQLite schema (v1+v2) + CRUD; `st.connection("telerrad")` pattern; 5-modality seed + 3 auto-migrations
3. **`src/calculations.py`** (~380 lines) — Pure business logic (earnings, hours, MA, projections) + DB-dependent stats; dynamic modality-aware
4. **`src/chart_colors.py`** (~85 lines) — Central color palette (11 modality colors + legacy aliases) + `color_for_modality(slug, modalities=None)` with DB-based lookup
5. **`src/charts.py`** (~330 lines) — Plotly factories for Today and Month tabs (dynamic modalities, DB-stored colors)
6. **`src/charts_analysis.py`** (~300 lines) — Plotly factories for Analysis tab (dynamic modalities)
7. **`src/formatting.py`** (~55 lines) — `fmt_brl()` BRL currency, `md_escape()` (escapes `$` for Streamlit Markdown), `MONTHS_PT`
8. **`src/insights_rules.py`** (~230 lines) — Rule-based Portuguese insight generator (dynamic modalities)
9. **`src/llm_client.py`** (~290 lines) — OpenRouter client with one-shot `generate()` + SSE `generate_stream()` + `build_rag_context()` for RAG
10. **`src/cookies.py`** (79 lines) — `get_cookie_manager()` (one construction per run) + tab cookie + signed session cookie helpers
11. **`src/ui/login.py`** (110 lines) — Auth gate: session restore, login form, TOTP step, 2FA banner, logout (only st.form usage)
12. **`src/ui/sidebar.py`** (~85 lines) — Dynamic date picker + modality inputs (label+input side by side) + save
13. **`src/ui/today.py`** (~195 lines) — KPI cards, modality bar, sparkline (dynamic)
14. **`src/ui/month.py`** (~210 lines) — Gauge, line chart, rhythm alert, celebration
15. **`src/ui/analysis.py`** (~130 lines) — Rule insights + 4 analysis charts (AI section removed in 1.5.0)
16. **`src/ui/chat.py`** (~280 lines) — RAG-powered Chat IA with SSE streaming, suggestion pills, history trimming (new in 1.5.0)
17. **`src/ui/settings.py`** (~340 lines) — `ensure_settings()` bootstrap + modality grid with add/delete/color_picker + LLM config + danger zone
18. **`.streamlit/config.toml`** (60 lines) — All theme config: colors, fonts, dark mode, semantic colors

### Deployment
18. **`Dockerfile`** — Multi-stage build (builder + runtime), non-root user (uid 1000), `qrencode` for the TOTP QR
19. **`docker-compose.yml`** — Caddy + Streamlit services, loopback-only port exposure
20. **`Caddyfile`** — Reverse proxy: access log, cache headers, streamlit upstream (auth is app-level)
21. **`scripts/manage_auth.py`** (180 lines) — SSH auth CLI (KIAUH-style): 2FA QR/activate/disable, password, username, status, repair
22. **`docs/deployment.md`** — Complete deployment guide with Vault secrets, playbooks, troubleshooting

### Tests
**`tests/conftest.py`** — `FakeConnection` (SQLite `:memory:` emulation, v2 schema with `color` column), `conn` fixture, `seeded_conn` fixture (5 production modalities), `active_modalities` fixture, `default_prices` fixture. Each `test_*.py` corresponds 1:1 to a `src/` module.

---

## Database Schema (5 tables, all in SQLite)

### v2 tables (primary)

- **`modalities`** — `slug` (PK, TEXT), `label`, `price` (REAL), `exams_per_hour` (REAL), `active` (INTEGER), `color` (TEXT, default `#64748B`), `sort_order` (INTEGER), `created_at`, `updated_at`. Seeded with 5 modalities with production values on `init_db()`. Colors customizable per-modality via Settings tab `st.color_picker`. Since v1.4.0: add/remove modalities dynamically. Since v1.8: "remove" = soft-delete (`active=0`, preserving all production history); re-adding the same slug reactivates it.
- **`daily_production_items`** — `date` (TEXT), `modality_slug` (TEXT), `count` (INTEGER), `created_at`, `updated_at`. PK: `(date, modality_slug)`. FK → `modalities(slug)`.
- **`modality_prices`** — `slug` (TEXT), `price` (REAL), `effective_from` (TEXT "YYYY-MM-DD"), `created_at`. PK `(slug, effective_from)`. Price-by-vigency: the price vigent on a date is the row with the greatest `effective_from <= date` (oldest as fallback). Editing a price opens a new vigency from today; the past keeps its own vigency and is **never** recomputed. Backfilled once from each modality's current price valid since its first production record. Since v2.1.

### Shared tables

- **`monthly_goals`** — `year_month` (PK, TEXT "YYYY-MM"), `goal_reais`, `updated_at`
- **`user_settings`** — `key` (PK, TEXT), `value`, `updated_at` (keys: `user_name`, `api_key`, `llm_prompt`, `llm_model`)

### Auto-migrations (run by `init_db()`, all idempotent; most are one-shot, flag-guarded in `user_settings`)

1. **`_add_color_column()`** — Adds `color` column via `PRAGMA table_info` + `ALTER TABLE`, backfills from `MODALITY_COLORS`
2. **`_migrate_v1_3_to_v1_4_defaults()`** — One-shot (flag `migration_v1_4_defaults_done`): applies production defaults to untouched modalities (price=0, active=0)
3. **`_backfill_price_vigencies()`** — One-shot: seeds `modality_prices` with each modality's current price valid since its first production record
4. **`_migrate_v1_cleanup()`** — One-shot (flag `migration_v1_cleanup_done`): drops the v1 legacy tables (`daily_production`, `exam_prices`) once `daily_production_items` is populated

### Key CRUD Functions (src/db.py)

| Function | Operation | Notes |
|----------|-----------|-------|
| `slugify(label)` | Utility | Portuguese text → URL-safe slug (NFKD → ASCII → `[^a-z0-9]+` → `_`) |
| `load_all_modalities(conn)` | Read | All modalities ordered by label COLLATE NOCASE |
| `load_active_modalities(conn)` | Read | `active=1 AND price>0 AND exams_per_hour>0` |
| `save_modality(conn, slug, price, eph, active, label=None, color=None)` | Write | Updates single modality; label/color unchanged when None |
| `add_modality(conn, slug, label, price, eph, active, color)` | Create/Reactivate | New slug: insert with auto sort_order. Existing INACTIVE slug: reactivates with the new values (preserves production history). Existing ACTIVE slug: returns False. |
| `deactivate_modality(conn, slug)` | Soft-delete | `active=0`, preserving the row and all `daily_production_items` (history intact; slug stays reserved). |
| `save_modality(conn, slug, price, eph, active, label=None, color=None)` | Write | Updates a modality; a real price change (>0, != old) also opens a new price vigency from today in `modality_prices`. |
| `save_price_vigency(conn, slug, price, effective_from)` | Write | UPSERT a `modality_prices` row (reajust). |
| `load_prices_at(conn, date_str)` | Read | slug→price vigent on `date_str` (from `modality_prices`). |
| `load_price_vigencies(conn)` | Read | All `modality_prices` rows ordered. |
| `upsert_daily_items(conn, date_str, items)` | Write | Dict slug→count; zero → DELETE, non-zero → UPSERT |
| `load_daily_items(conn, date_str)` | Read | Dict slug→count |
| `load_month_items(conn, year_month)` | Read | DataFrame: date, modality_slug, count |
| `load_goal` / `save_goal` | Read/Write | Per-month target with carry-forward: returns the most recent prior month's goal when the requested month has no row; falls back to 45000.0 only when no goal was ever recorded. |
| `load_setting` / `save_setting` | Read/Write | Key-value store |

All query functions pass `ttl=0` — no Streamlit caching.

---

## Session State Architecture

Every tab renderer calls `ensure_settings(conn)` first — it lazily loads from DB into `st.session_state`:

| Key | DB Source | Default Value |
|-----|-----------|---------------|
| `all_modalities` | `modalities` table | Empty list (seeded on init) |
| `active_modalities` | `modalities` WHERE `active=1 AND price>0 AND exams_per_hour>0` | Empty list |
| `prices` | Built from `active_modalities` (slug→price) | `{}` |
| `goal` | `monthly_goals` for current year-month | `45000.0` |
| `user_name` | `user_settings` key `"user_name"` | `"Galvani"` |
| `api_key` | `user_settings` key `"api_key"` | `""` |
| `llm_prompt` | `user_settings` key `"llm_prompt"` | Default system prompt (`{user_name}` interpolated) |
| `llm_model` | `user_settings` key `"llm_model"` | `"openai/gpt-oss-120b:free"` |

**Auth gate state (used by `src/ui/login.py`):**
- `auth_authenticated` — `True`/`False`; key presence triggers cookie restore (once per server session); logout sets `False`, never removes the key
- `auth_username` — display-only
- `auth_awaiting_totp` — transient, between the password and TOTP steps

**Analysis-tab specific state:**
- `historical_cache` — `{"key": "json_hash", "stats": {...}}` — invalidated when goal/active modalities change

**Chat IA specific state:**
- `messages` — list of `{"role": str, "content": str}` for chat history (system + user/assistant pairs, capped at 31)
- `chat_suggestions` — temporary pill selection

**Month tab:**
- `goal_celebrated_YYYY-MM` — boolean guard for celebration rain (once per month)

---

## Conventions & Constraints

### Hard constraints (never violate)
- **Python ≥ 3.12** — use modern syntax (match/case, `str | None`, walrus ok)
- **Streamlit ≥ 1.54** — use `container(border=True)`, `st.badge`, Material icons (`:material/name:`), `st.fragment`, `st.chat_message`, `st.chat_input`, `st.write_stream`, `st.pills`
- **No custom CSS / `unsafe_allow_html=True`** — all theming via `.streamlit/config.toml`. Exception: `st.html()` for chat avatar colors only (limited, scoped).
- **No deprecated streamlit-extras** — never import: `add_vertical_space`, `app_logo`, `colored_header`, `row`, `stylable_container`, `tags`
- **No `st.divider()`** — use natural spacing or section headers
- **No emojis as functional icons** — use `:material/` icons exclusively; emojis only for celebration rain
- **No `st.form` in sidebar** — it breaks date-dependent pre-fill (forms suppress widget-driven reruns)
- **No `.env` file in the application** — API key is stored in DB `user_settings` table, configured in UI
- **Portuguese locale for all user-facing text** — UI labels, tooltips, chart annotations, insights
- **No database access in chart modules** — `src/charts.py` and `src/charts_analysis.py` accept data as parameters only
- **No st.form in sidebar** — it breaks date-dependent pre-fill (forms suppress widget-driven reruns). Exception: the auth gate's login/TOTP forms in `src/ui/login.py` (main area) are the only `st.form` usage in the project.
- **Deployment: Streamlit on loopback only** — `127.0.0.1:8501` in docker-compose, never exposed externally
- **Dockerfile: non-root user** — container runs as `streamlit` (uid 1000), not root
- **Dynamic modalities** — never hardcode modality slugs, labels, or prices in UI code; always use `st.session_state.active_modalities`
- **`md_escape()` before `st.markdown()`** — all LLM outputs and BRL strings rendered via `st.markdown`, `st.write`, `st.expander`, `st.warning`, `st.info`, or `st.metric delta` must pass through `md_escape()`
- **`safe_stream` for `st.write_stream()`** — always wrap the token generator: `(token.replace("$", "\\$") for token in stream)`
- **History rendering in chat** — use `md_escape(msg["content"])` when rendering saved messages
- **Package management via `uv` only** — `uv add`, `uv sync`, `uv run`

### Style conventions
- **Functions: 4–20 lines.** Split if longer.
- **Files: under 500 lines.** Split by responsibility.
- **Names: specific and unique.** Avoid `data`, `handler`, `Manager`. Prefer <5 grep hits.
- **Types: explicit.** No `Any` except where the Streamlit API requires it (e.g., `conn: Any`).
- **Early returns over nested ifs.** Max 2 levels of indentation.
- **Docstrings on all public functions** — intent + one usage example.
- **No code duplication.** Extract shared logic.
- **Charts:** all colors from `color_for_modality()` or `CHART_COLORS` dict in `src/chart_colors.py` — no inline hex values.
- **Currency:** use `fmt_brl()` from `src/formatting.py`; it uses `Decimal.quantize(ROUND_HALF_UP)`.
- **Markdown safety:** wrap BRL strings in `md_escape()` before passing to `st.markdown`. See `docs/markdown-escaping-guide.md` for complete rules.

### Deployment conventions
- **Auth state:** single user, `data/auth.json` (gitignored), stdlib crypto only — no new Python deps for auth.
- **Credentials exempt from logging** — never log, print, or write passwords, TOTP codes, or session secrets (project logging is structured JSON).
- **CookieManager: exactly one construction per run** (`app.py`, passed down) — a second `cookie_manager()` call in the same run raises `StreamlitDuplicateElementKey`, and queued set/delete operations only flush when the component renders.
- **Auth gate placement:** in `app.py` right after `st.set_page_config`, before `get_connection()` — imports stay at the top (ruff E402).
- **Ansible secrets:** use `ansible-vault encrypt_string` for sensitive values; embed `!vault |` blocks directly in `all.yml`.
- **Playbook idempotency:** All playbooks must be safe to re-run. `data/` is bind-mounted, never touched by git ops.
- **Git authentication:** ed25519 deploy key auto-generated on VPS, registered via GitHub API. No ForwardAgent.

---

## Color Palette Reference

Modality colors are stored in the `modalities` table (`color` column) and default to the palettes below. Users can override any color via the Settings tab — chart factories read DB-stored color via `color_for_modality(slug, modalities)`.

```python
# 5 seeded modalities (active, with production values)
# angiotomografia:         #0D9488 (Teal-600)
# radiografia:             #2563EB (Blue-600)
# ressonancia_magnetica:   #7C3AED (Violet-600)
# tc_geral:                #6366F1 (Indigo-500)
# tc_abdome_total:         #0891B2 (Cyan-600)

# 6 additional colors in MODALITY_COLORS (for backward compat / user-added modalities)
# ultrassonografia:        #A855F7 (Purple-500)
# dopplervelocimetria:     #059669 (Emerald-600)
# radiografia_contrastada: #475569 (Slate-600)
# ultrassom_morfologico:   #0EA5E9 (Sky-500)
# mamografia:              #BE123C (Rose-700)
# densitometria:           #A16207 (Amber-700)
# fallback:                #64748B (Slate-500)

CHART_COLORS = {
    **MODALITY_COLORS,
    "rm": MODALITY_COLORS["ressonancia_magnetica"],  # legacy alias
    "tc": MODALITY_COLORS["tc_geral"],               # legacy alias
    "rx": MODALITY_COLORS["radiografia"],            # legacy alias
    "primary": "#0D9488",             # Teal-600 — main line/bar
    "muted": "#94A3B8",               # Slate-400
    "neutral": "#64748B",             # Slate-500
    "progress_danger": "#CCFBF1",     # teal-50  — 0-25%
    "progress_warning": "#5EEAD4",    # teal-300 — 25-50%
    "progress_on_track": "#14B8A6",   # teal-500 — 50-75%
    "progress_achieved": "#0F766E",   # teal-700 — 75-100%
    "track": "#E2E8F0",               # Slate-200 — gridlines, progress bg
}
```

---

## Business Constants

- 5 seeded modalities (see `_MODALITY_SEED` in `src/db.py`)
- Production default prices: Angiotomografia=R$30, Radiografia=R$4, RM=R$35, TC Geral=R$30, TC Abdome Total=R$60
- Production default exams/h: 4.0, 80.0, 8.0, 10.0, 5.0
- Default monthly goal: R$45,000 (used only when no goal has ever been recorded; otherwise the most recent prior month's goal carries forward across a month turnover)
- Production is counted in **dias corridos**: every day is work-eligible. `daily_avg = mtd / elapsed_days` (gaps count as zero-production days); `remaining_days` excludes today when today already has production. `days_worked` (days with ≥1 exam) is a displayed statistic only and never enters projection/rhythm/needed.
- Price changes are vigency-based (`modality_prices`): a reajust today does not recompute past months' faturamento.
- `_MAX_MESSAGE_PAIRS = 15` (chat history: system + 30 user/assistant)
- Streaming timeout: 30s (vs 15s for one-shot)
- SSE parser: safe accessor chain (`data.get("choices") or [{}]`, `choice.get("delta") or {}`)

---

## Success Criteria

Before considering any task done:
1. **Tests pass:** `uv run pytest tests/ -v` → 150 passed (or higher if new tests added)
2. **Lint clean:** `uv run ruff check src/ tests/` → no errors
3. **Types check:** `uv run mypy src/` → no new errors
4. **New functions have tests** — add to the appropriate `tests/test_*.py` file
5. **New public functions have docstrings** — intent + one usage example
6. **No dead code** — check with `rg`/`grep` for unused imports, functions, variables
7. **For deployment changes:** verify Ansible playbooks pass `ansible-lint` and syntax check
8. **For Dockerfile changes:** verify `hadolint` passes
9. **For chat changes:** verify both $ escaping rules (history + streaming) per `docs/markdown-escaping-guide.md`

---

## Validation (what to run)

```bash
# Test suite
uv run pytest tests/ -v

# Coverage report
uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Linting (Python)
uv run ruff check src/ tests/

# Type checking
uv run mypy src/

# Linting (deployment files)
ansible-lint ansible/                    # Ansible playbooks
hadolint Dockerfile                      # Dockerfile
yamllint .                               # All YAML files

# Run the app (manual spot-check)
uv run streamlit run app.py
```

---

## Stop / Escalate Rules

- **Stop and ask** (via `intercom` if available) when:
  - A proposed change would alter the database schema (needs migration)
  - A change affects multiple tabs or the core data flow
  - You need to introduce a new dependency not already in `pyproject.toml`
  - You're unsure whether a design decision is intentional
  - Changing `.streamlit/config.toml` theme values (has visual impact across all tabs)
  - Modifying the streaming/message pipeline in the Chat IA tab
- **Proceed without asking** when:
  - Adding tests for existing logic
  - Fixing a bug with clear reproduction
  - Adding a new pure calculation function (in `calculations.py`)
  - Adding a new chart factory (in `charts.py` or `charts_analysis.py`)
  - Improving docstrings, type annotations, or error messages
  - Refactoring within a single module (no API changes)
  - Adding or updating Ansible playbooks following existing patterns
  - Updating Dockerfile dependencies (must sync with `pyproject.toml`)
  - Editing documentation for clarity or accuracy
  - Adding a new modality color entry to `MODALITY_COLORS`

---

## Resolved Design Decisions (do not revisit)

- **App-level auth, single user** — username + scrypt password + optional TOTP 2FA; state in `data/auth.json` (not DB tables); stdlib crypto only
- **Session persistence via signed cookie** — HMAC-SHA256 token, `session_days` default 30; logout and password change (rotates `session_secret`) revoke it; no server-side sessions; no lockout / rate limiting in the app (per-session lockout was cosmetic against scripts and hostile to humans)
- **2FA setup/reset via SSH only** — QR rendered in the terminal (`qrencode`), `manage_auth.py` CLI behind the `radtracker-auth` wrapper; TOTP secret never touches the web
- **fail2ban sshd jail** — the Caddy 401 jail died with BasicAuth (the app never returns 401); network-level web brute-force protection is TOTP (+ optional Cloudflare rate limit on the final domain)
- **Bootstrap is idempotent** — Ansible creates `auth.json` once from vault vars; redeploys never overwrite it (password/2FA changes via `radtracker-auth`)

- **API key lives in DB** (`user_settings`), not in `.env` — do not reintroduce `python-dotenv` or `.env` loading
- **Sidebar does NOT use `st.form`** — the date-dependent pre-fill requires widgets to rerun naturally; keep the imperative save button + spinner pattern
- **Tab navigation uses `st.radio`** (not `st.tabs`) — Material icons render correctly in radio labels
- **Progress gauge uses teal monochrome gradient** (not red/amber/green) — deliberate aesthetic choice (Cal.com-inspired)
- **No `st.divider()` in the app** — removed intentionally; use spacing and section headers
- **Chart modules have no DB access** — they receive pre-computed data as parameters
- **Streamlit bound to loopback only** — Caddy is the sole public-facing endpoint; do not expose 8501 externally
- **Ansible secrets in `all.yml`** — encrypted inline via `ansible-vault encrypt_string`; do not create separate vault files
- **`requirements.txt` has been removed** — `pyproject.toml` + `uv.lock` are the only canonical dependency sources
- **Dynamic modalities** — never hardcode modality labels/prices in UI; always load from DB via `load_active_modalities()`
- **Git deploy key** — ed25519 SSH key auto-generated on VPS, registered via GitHub API; no ForwardAgent needed
- **LLM model configurable via slug** — stored in `user_settings` as `llm_model` key; constructor accepts it as parameter
- **AI insights moved to Chat IA tab** — the Analysis tab's AI section was removed in v1.5.0; all AI interaction now goes through the Chat IA tab with RAG context and streaming
- **Modality slugs immutable after creation** — `slugify()` is run once at add time; user edits label but slug persists
- **`md_escape()` required in two places** — history rendering AND streaming wrapper; both are required, not either-or (see `docs/markdown-escaping-guide.md`)
- **Chat history capped at 15 pairs** — system message preserved, older user/assistant pairs trimmed from front

---

## Assumptions

- Single user, local SQLite, no concurrency at the application layer
- Portuguese locale for all user-facing text
- Cal.com-inspired monochrome design aesthetic
- The `uv` package manager is installed and is the standard toolchain
- `data/telerrad.db` may contain production data; tests use `:memory:` databases
- Deployment target is a clean Debian 12+ or Ubuntu 22.04+ VPS
- Git access uses deploy key (ed25519 SSH key on VPS, registered as read-only GitHub deploy key)
- OpenRouter API key is configured by the user in the Settings tab

---

## Quick Start

```bash
cd /home/galvani/dev/radtracker
uv sync                          # install deps
uv run pytest tests/ -v          # verify tests pass (150 expected)
uv run streamlit run app.py      # run the app
```

For deployment:
```bash
export VPS_HOST=129.151.4.89  # Oracle Cloud Free Tier (prod)
# or VPS_HOST=10.10.10.209 VPS_USER=galvani  # LAN dev VPS
ansible-galaxy collection install -r ansible/requirements.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --vault-password-file ansible/.vault_pass
```

Local dev note: the auth gate needs `data/auth.json` — create a scratch one with
`python -c "from src.auth_store import create_bootstrap_auth; print(create_bootstrap_auth('dev', 'dev-password-123', 'data/auth.json', cookie_secure=False))"`,
or the app stops at "Autenticação não configurada".

Read `README.md` for end-user setup instructions. Read `docs/context.md` for exhaustive module-by-module detail. Read `docs/deployment.md` for the complete deployment guide. Read `docs/markdown-escaping-guide.md` for `$` escaping rules.
