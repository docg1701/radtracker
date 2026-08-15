# radtracker — Project Context

Module map, data flow, and auth flow. Lean — details live in the code; constraints
and decisions live in `docs/meta-prompt.md`.

## 1. Purpose

Personal productivity dashboard for teleradiology: daily exam counts per modality,
monthly revenue vs goal, historical analysis, and an LLM chat (RAG over production
data). Single user, single-page Streamlit app, SQLite persistence, PT-BR UI.

## 2. Architecture

```
Browser ──HTTPS──> Caddy ──HTTP──> Streamlit (127.0.0.1:8501) ──> SQLite data/telerrad.db
                                      └──> OpenRouter (Chat IA)
Auth: login/TOTP gate (src/ui/login.py) ──> data/auth.json
Session: HMAC-signed cookie (src/cookies.py + src/auth_crypto.py)
```

### 2.1 Directory structure

```
app.py                     entry point: gate → sidebar → tab radio → tab renderer
.streamlit/config.toml     theme
src/
  auth_crypto.py           scrypt, TOTP (RFC 6238), otpauth URI, HMAC tokens
  auth_store.py            auth.json load/save/validate + gate helpers
  auth_bootstrap.py        non-interactive bootstrap (Ansible)
  cookies.py               one-way CCv2 cookie components + session-token helpers
  db.py                    schema + CRUD + migrations
  calculations.py          earnings/hours/MA/projections (pure + DB-dependent)
  chart_colors.py          palette + color_for_modality()
  charts.py                Plotly factories (Today/Month)
  charts_analysis.py       Plotly factories (Analysis)
  formatting.py            fmt_brl(), md_escape(), MONTHS_PT
  insights_rules.py        rule-based PT insights
  llm_client.py            OpenRouter one-shot + SSE streaming + RAG context
  ui/
    login.py               auth gate, login/TOTP forms, sidebar header/footer, logout
    sidebar.py             greeting, date row, modality inputs, Salvar
    today.py               KPI cards, modality bar, sparkline
    month.py               gauge, line chart, rhythm alert, celebration
    analysis.py            rule insights + 4 charts
    chat.py                RAG chat with SSE streaming
    settings.py            modality CRUD, LLM config, danger zone
scripts/manage_auth.py     SSH auth CLI (radtracker-auth)
tests/                     one test module per src module
ansible/                   playbooks, inventory, vault-secured all.yml, templates
data/                      telerrad.db + auth.json (both gitignored)
```

### 2.2 Data flow

1. Every rerun: `app.py` loads `auth.json`, runs the gate, boots `st.connection("telerrad")`.
2. Every tab renderer calls `ensure_settings(conn)` → session state
   (`active_modalities`, `goal`, `user_name`, ...) from DB.
3. Sidebar save → `upsert_daily_items` (zero = DELETE) → toast → `st.rerun()`;
   clears `historical_cache`.
4. Tabs render from DB queries (`ttl=0`, no caching) + pure calculations.
5. Chat IA streams from OpenRouter with RAG context built from production history.

### 2.3 Auth flow

- **Restore:** signed cookie present → verify HMAC (username + expiry) → session.
  Runs once per server session (key presence in session state gates it).
- **Login:** form (username/password) → scrypt verify → optional TOTP step →
  `_COOKIE_WRITER` sets the signed cookie (Secure flag from `session_cookie_secure`).
- **Logout:** clears cookie (writer), sets `auth_authenticated=False` (key never removed).
- **2FA:** enabled/disabled only via SSH `radtracker-auth`; `totp_required` re-read
  from `auth.json` every run.
- **Cookie components:** `_COOKIE_READER` publishes its snapshot once per server
  session; `_COOKIE_WRITER` never publishes; writer rendered only inside the gate.

## 3. Database (SQLite, 5 tables)

| Table | Key | Purpose |
|-------|-----|---------|
| `modalities` | slug | label, price, exams_per_hour, active, color (soft-delete preserves history) |
| `daily_production_items` | (date, slug) | exam counts |
| `modality_prices` | (slug, effective_from) | price vigencies — past never recomputed |
| `monthly_goals` | year_month | carry-forward; 45000.0 fallback only if never recorded |
| `user_settings` | key | user_name, api_key, llm_prompt, llm_model, migration flags |

`init_db()` runs idempotent auto-migrations (color column, defaults, price-vigency
backfill, v1 table cleanup). All queries use `ttl=0`.

## 4. The 5 seeded modalities

Angiotomografia, Radiografia, Ressonância Magnética, TC Geral, TC Abdome Total —
seeded with production values in `_MODALITY_SEED`; user-editable and extensible
via Settings.

## 5. Module notes (non-obvious facts)

- **`src/db.py`** — `save_modality` opens a new price vigency on real price change.
  `slugify()` runs once at creation; slugs immutable afterwards.
- **`src/calculations.py`** — production counted in dias corridos; `days_worked`
  display-only.
- **`src/chart_colors.py`** — DB-stored per-modality color via `color_for_modality`;
  legacy aliases (rm/tc/rx) kept for history.
- **`src/charts*.py`** — no DB access; data in, fig out.
- **`src/formatting.py`** — BRL via `fmt_brl()`; `$` must be escaped in markdown.
- **`src/insights_rules.py`** — Portuguese rule-based insights, dynamic modalities.
- **`src/llm_client.py`** — OpenRouter; one-shot 15s timeout, streaming 30s;
  SSE parser uses safe accessor chains.
- **`src/cookies.py`** — reader/writer contract above; tab cookie stores last tab.
- **`src/ui/login.py`** — the ONLY `st.form` usage (login/TOTP, main area).
- **`src/ui/sidebar.py`** — imperative save (no form), date label beside the box.
- **`src/ui/chat.py`** — history capped at 15 pairs; both `$` escaping rules apply.
- **`src/ui/settings.py`** — modality grid with add/deactivate/color_picker;
  danger zone for data resets.

## 6. Theme & branding

Cal.com-inspired; full palette in `src/chart_colors.py` and
`.streamlit/config.toml`. Dark mode primaryColor Teal-700 `#0F766E` (Streamlit
renders white text on primaryColor — light primary would be white-on-white).

## 7. Dependencies

`pyproject.toml` is authoritative (runtime + dev). Deployment-layer linters
(yamllint, hadolint, sqlfluff, markdownlint) not yet configured — see AGENTS.md.

## 8. Tests

294 tests, one module per `tests/test_*.py`. Infrastructure in `tests/conftest.py`:
`FakeConnection` (SQLite :memory:), `conn`, `seeded_conn`, `default_prices` fixtures;
`@respx.mock` for HTTP. New public function → test; bug fix → regression test first.

## 9. Deployment

See `docs/deployment.md` (Vault secrets, playbooks, troubleshooting) and AGENTS.md
"Deployment & auth critical facts" (LAN update flags, RADTRACKER_MODE).
