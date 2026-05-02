# radtracker — Meta-Prompt for LLM Sessions

**Purpose:** Drop this into any LLM session to immediately re-establish full project context and start coding.

---

## Goal

You are working on **radtracker**, a personal productivity dashboard for a teleradiology physician. It's a Streamlit (≥1.54) single-page app with local SQLite persistence. The UI is in Brazilian Portuguese. Self-hosted deployment to a VPS is supported via Docker + Caddy + fail2ban, managed with Ansible playbooks (v1.1.0+).

You will be modifying Python code in the `src/` tree, the Streamlit entry point `app.py`, the config `.streamlit/config.toml`, the test suite in `tests/`, Docker/deployment files at the project root, or Ansible playbooks in `ansible/`.

---

## Tech Stack

| Layer | Tech | Notes |
|-------|------|-------|
| Framework | **Streamlit ≥1.54** | Single-page, wide layout, `st.connection` for DB |
| Database | **SQLite** via SQLAlchemy + `st.connection` | File at `data/telerrad.db` (gitignored) |
| Charts | **Plotly ≥5.18** | All chart factories in `src/charts.py` and `src/charts_analysis.py` |
| Data | **Pandas ≥2.0** | DataFrames for calculations and chart data |
| HTTP | **httpx ≥0.27** | OpenRouter API calls only |
| Extras | **streamlit-extras ≥1.5** | `skeleton`, `rain`, `star_rating`, `stoggle`, `cookie_manager` |
| Package mgr | **uv** | `uv.lock` is authoritative |
| Tests | **pytest ≥8.0**, **respx** for HTTP mocking | 96 tests, all passing |
| Lint/fmt | **ruff** (E, F, I, UP rules, line-length 100) | Run: `uv run ruff check src/ tests/` |
| Types | **mypy** (strict=false) | Run: `uv run mypy src/` |
| **Deployment** | | |
| Container | **Docker** (multi-stage build, non-root user) | `Dockerfile` + `docker-compose.yml` |
| Reverse proxy | **Caddy 2** (BasicAuth + Let's Encrypt) | `Caddyfile`, Jinja2 template in `ansible/templates/` |
| Automation | **Ansible** (5 playbooks, Vault encryption) | `ansible/` directory |
| Security | **fail2ban** (401 detection) | Filter + jail in `deploy.yml` playbook |
| Lint (deploy) | **ansible-lint**, **hadolint**, **yamllint** | `.ansible-lint.yml`, `.hadolint.yml`, `.yamllint.yml` |

---

## Key Files (Read these first for any task)

### Application core (Python)
1. **`app.py`** (73 lines) — Entry point, page config, DB boot, tab navigation
2. **`src/db.py`** (163 lines) — All SQLite schema + CRUD; `st.connection("telerrad")` pattern
3. **`src/calculations.py`** (380 lines) — Pure business logic (earnings, hours, MA, projections) + DB-dependent stats
4. **`src/chart_colors.py`** (58 lines) — Central color palette; no inline hex anywhere else
5. **`src/charts.py`** (299 lines) — Plotly factories for Today and Month tabs
6. **`src/charts_analysis.py`** (289 lines) — Plotly factories for Analysis tab
7. **`src/formatting.py`** (56 lines) — `fmt_brl()` BRL currency, `md_escape()`, `MONTHS_PT`
8. **`src/insights_rules.py`** (221 lines) — Rule-based Portuguese insight generator
9. **`src/llm_client.py`** (193 lines) — OpenRouter `openai/gpt-oss-120b:free` client
10. **`src/cookies.py`** (38 lines) — `cookie_manager` for tab persistence
11. **`src/ui/sidebar.py`** (71 lines) — Date picker + 3 modality inputs + save
12. **`src/ui/today.py`** (206 lines) — KPI cards, donut, sparkline
13. **`src/ui/month.py`** (194 lines) — Gauge, line chart, rhythm alert, celebration
14. **`src/ui/analysis.py`** (225 lines) — Rule insights + LLM (fragment) + 4 analysis charts
15. **`src/ui/settings.py`** (197 lines) — `ensure_settings()` bootstrap + config form + danger zone
16. **`.streamlit/config.toml`** (60 lines) — All theme config: colors, fonts, dark mode, semantic colors

### Deployment
17. **`Dockerfile`** (~40 lines) — Multi-stage build (builder + runtime), non-root user (uid 1000)
18. **`docker-compose.yml`** (~35 lines) — Caddy + Streamlit services, loopback-only port exposure
19. **`Caddyfile`** (~13 lines) — Reverse proxy: BasicAuth, JSON access log, streamlit upstream
20. **`.env.example`** — Template: DOMAIN + BASICAUTH_USERS (with `$$` escaping note)
21. **`.dockerignore`** — Build context exclusions
22. **`ansible/ansible.cfg`** — ForwardAgent, pipelining
23. **`ansible/inventory.yml`** — Single host via `VPS_HOST` + `VPS_USER` env vars
24. **`ansible/group_vars/all.yml`** — Vault-encrypted secrets + shared vars
25. **`ansible/playbooks/deploy.yml`** — 10-step idempotent bootstrap + deploy pipeline
26. **`ansible/templates/Caddyfile.j2`** — LAN vs internet mode template
27. **`ansible/templates/.env.j2`** — `.env` template with `$` → `$$` escaping
28. **`docs/deployment.md`** — Complete deployment guide

**For tests:** `tests/conftest.py` defines `FakeConnection` (SQLite `:memory:` emulation), `conn` fixture, `default_prices` fixture. Each `test_*.py` corresponds 1:1 to a `src/` module.

---

## Database Schema (4 tables, all in SQLite)

- **`daily_production`** — `date` (PK, TEXT ISO), `rm_count`, `tc_count`, `rx_count`, `created_at`, `updated_at`
- **`exam_prices`** — `id` (PK autoincrement), `rm_price`, `tc_price`, `rx_price`, `effective_from`, `created_at` (append-only history, latest row is current)
- **`monthly_goals`** — `year_month` (PK, TEXT "YYYY-MM"), `goal_reais`, `updated_at`
- **`user_settings`** — `key` (PK, TEXT), `value`, `updated_at` (keys: `user_name`, `api_key`, `llm_prompt`)

All CRUD functions are in `src/db.py`. Use `upsert_daily` for inserts/updates; it uses `ON CONFLICT(date) DO UPDATE`. All query functions pass `ttl=0` (no Streamlit caching).

---

## Session State Architecture

Every tab renderer calls `ensure_settings(conn)` first — it lazily loads from DB into `st.session_state`:
- `st.session_state.prices` — `{"rm": 35.0, "tc": 25.0, "rx": 4.5}`
- `st.session_state.goal` — float (default 45000.0)
- `st.session_state.user_name` — str (default "Galvani")
- `st.session_state.api_key` — str (default "")
- `st.session_state.llm_prompt` — str (default system prompt with `{user_name}` interpolated)

Analysis tab adds: `historical_cache`, `llm_insight_text`, `llm_insight_pending`, `llm_insight_in_flight`, `llm_insight_cancelled`.

---

## Conventions & Constraints

### Hard constraints (never violate)
- **Python ≥ 3.12** — use modern syntax (match/case, `str | None`, walrus ok)
- **Streamlit ≥ 1.54** — use `container(border=True)`, `st.badge`, Material icons (`:material/name:`), `st.fragment`
- **No custom CSS / `unsafe_allow_html=True`** — all theming via `.streamlit/config.toml`
- **No deprecated streamlit-extras** — never import: `add_vertical_space`, `app_logo`, `colored_header`, `row`, `stylable_container`, `tags`
- **No `st.divider()`** — use natural spacing or section headers
- **No emojis as functional icons** — use Material icons exclusively; emojis only for celebration rain
- **No `st.form` in sidebar** — it breaks date-dependent pre-fill (forms suppress widget-driven reruns)
- **No `.env` file in the application** — API key is stored in DB `user_settings` table, configured in UI
- **Portuguese locale for all user-facing text** — UI labels, tooltips, chart annotations, insights
- **No database access in chart modules** — `src/charts.py` and `src/charts_analysis.py` accept data as parameters only
- **Deployment: Streamlit on loopback only** — `127.0.0.1:8501` in docker-compose, never exposed externally
- **Dockerfile: non-root user** — container runs as `streamlit` (uid 1000), not root

### Style conventions
- **Functions: 4–20 lines.** Split if longer.
- **Files: under 500 lines.** Split by responsibility.
- **Names: specific and unique.** Avoid `data`, `handler`, `Manager`. Prefer <5 grep hits.
- **Types: explicit.** No `Any` except where the Streamlit API requires it (e.g., `conn: Any`).
- **Early returns over nested ifs.** Max 2 levels of indentation.
- **Docstrings on all public functions** — intent + one usage example.
- **Logging: structured JSON** for debugging; plain text only for CLI output.
- **No code duplication.** Extract shared logic.
- **Charts:** all colors from `CHART_COLORS` dict in `src/chart_colors.py` — no inline hex values.
- **Currency:** use `fmt_brl()` from `src/formatting.py`; it uses `Decimal.quantize(ROUND_HALF_UP)`.
- **Markdown safety:** wrap BRL strings in `md_escape()` before passing to `st.markdown`.

### Deployment conventions
- **`$` in `BASICAUTH_USERS`:** must be escaped as `$$` in `.env` (Docker env_file parser)
  - The `.env.j2` Ansible template handles this automatically with `regex_replace('\\$', '$$')`
  - When editing `.env.example` or `.env` manually, double all `$` characters in the bcrypt hash
- **Ansible secrets:** use `ansible-vault encrypt_string` for sensitive values (`deployment_mode`, `basicauth_users`)
  - Embed `!vault |` blocks directly in `all.yml` — no separate vault file
- **Playbook idempotency:** All playbooks must be safe to re-run without data loss
  - `data/` is bind-mounted, never touched by git operations or rebuilds
  - Container strategy: `recreate: always` (ensures fresh config on every deploy)
- **fail2ban whitelist:** Always include RFC1918 + loopback ranges in jail config to prevent admin lockout

### Color palette reference
```python
CHART_COLORS = {
    "rm": "#2563EB",      # Blue-600
    "tc": "#D97706",      # Amber-600
    "rx": "#0891B2",      # Cyan-600
    "primary": "#0D9488", # Teal-600
    "muted": "#94A3B8",   # Slate-400
    "neutral": "#64748B", # Slate-500
    "progress_danger": "#CCFBF1",     # teal-50
    "progress_warning": "#5EEAD4",    # teal-300
    "progress_on_track": "#14B8A6",   # teal-500
    "progress_achieved": "#0F766E",   # teal-700
    "track": "#E2E8F0",   # Slate-200
}
```

### Business constants
- Productivity: RM 7.5/h, TC 7.5/h, RX 75/h
- Default prices: RM=R$35, TC=R$25, RX=R$4.50
- Default monthly goal: R$45,000
- Work starts at 08:00
- CSV import mapping: `ag`→TC, `tt`→2×TC

---

## Success Criteria

Before considering any task done:
1. **Tests pass:** `uv run pytest tests/ -v` → 96 passed (or higher if new tests added)
2. **Lint clean:** `uv run ruff check src/ tests/` → no errors
3. **Types check:** `uv run mypy src/` → no new errors (existing warnings may exist)
4. **New functions have tests** — add to the appropriate `tests/test_*.py` file
5. **New public functions have docstrings** — intent + one usage example
6. **No dead code** — check with `rg`/`grep` for unused imports, functions, variables
7. **For deployment changes:** verify Ansible playbooks still pass `ansible-lint` and playbook syntax check
8. **For Dockerfile changes:** verify `hadolint` passes

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
yamllint .                               # All YAML files (respects .yamllint.yml ignores)

# Run the app (manual spot-check)
uv run streamlit run app.py
```

---

## Stop / Escalate Rules

- **Stop and ask** (via `intercom` if available) when:
  - A proposed change would alter the database schema (needs migration)
  - A change affects multiple tabs or the core data flow
  - You need to introduce a new dependency not already in `pyproject.toml`
  - You're unsure whether a design decision is intentional (e.g., why `st.radio` over `st.tabs`)
  - Changing `.streamlit/config.toml` theme values (has visual impact across all tabs)
- **Proceed without asking** when:
  - Adding tests for existing logic
  - Fixing a bug with clear reproduction
  - Adding a new pure calculation function (in `calculations.py`)
  - Adding a new chart factory (in `charts.py` or `charts_analysis.py`)
  - Improving docstrings, type annotations, or error messages
  - Refactoring within a single module (no API changes)
  - Adding or updating Ansible playbooks following existing patterns
  - Updating Dockerfile dependencies (must sync with `pyproject.toml`)
  - Editing `docs/deployment.md` for clarity or accuracy

---

## Resolved Design Decisions (do not revisit)

- **API key lives in DB** (`user_settings`), not in `.env` — do not reintroduce `python-dotenv` or `.env` loading
- **Sidebar does NOT use `st.form`** — the date-dependent pre-fill requires widgets to rerun naturally; keep the imperative save button + spinner pattern
- **Tab navigation uses `st.radio`** (not `st.tabs`) — Material icons render correctly in radio labels
- **Progress gauge uses teal monochrome gradient** (not red/amber/green) — this is a deliberate aesthetic choice
- **No `st.divider()` in the app** — removed intentionally; use spacing and section headers
- **Chart modules have no DB access** — they receive pre-computed data as parameters
- **Streamlit bound to loopback only** — Caddy is the sole public-facing endpoint; do not expose 8501 externally
- **Ansible secrets in `all.yml`** — encrypted inline via `ansible-vault encrypt_string`; do not create separate vault files or `.env`-based secret loading
- **`requirements.txt` has been removed** — `pyproject.toml` + `uv.lock` are the only canonical dependency sources

---

## Assumptions

- Single user, local SQLite, no concurrency at the application layer
- Portuguese locale for all user-facing text
- Cal.com-inspired monochrome design aesthetic
- The `uv` package manager is installed and is the standard toolchain
- `data/telerrad.db` contains actual production data (Jan–Apr 2026); tests use `:memory:` databases
- Deployment target is a clean Debian 12+ or Ubuntu 22.04+ VPS
- SSH agent forwarding is used for private GitHub repo access during deployment

---

## Quick Start

```bash
cd /home/galvani/dev/radtracker
uv sync                          # install deps
uv run pytest tests/ -v          # verify tests pass
uv run streamlit run app.py      # run the app
```

For deployment:
```bash
export VPS_HOST=10.10.10.209
export VPS_USER=galvani
ansible-galaxy collection install -r ansible/requirements.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --ask-vault-pass
```

Read `README.md` for end-user setup instructions. Read `docs/context.md` for exhaustive module-by-module detail. Read `docs/deployment.md` for the complete deployment guide.
