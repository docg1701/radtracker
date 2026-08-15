# radtracker — Meta-Prompt for LLM Sessions

**Purpose:** Re-establish project context for any LLM session, fast. Lean by design —
see AGENTS.md "Documentation rule".

## Goal

**radtracker** — personal productivity dashboard for a teleradiology physician.
Streamlit single-page app, SQLite persistence, PT-BR UI. Production: Oracle Cloud
Free Tier via Docker + Caddy + fail2ban + Ansible. LAN dev VPS: 10.10.10.209.

## Tech Stack

| Layer | Tech |
|-------|------|
| Framework | Streamlit ≥1.54 (wide layout, `st.connection` for DB) |
| Database | SQLite via SQLAlchemy + `st.connection` — `data/telerrad.db` (gitignored) |
| Charts | Plotly — factories in `src/charts.py`, `src/charts_analysis.py` |
| Data | Pandas |
| HTTP | httpx — OpenRouter (one-shot + SSE streaming) |
| Extras | streamlit-extras: `rain`, `star_rating`, `stoggle` only (never `skeleton`, `cookie_manager`) |
| Auth | stdlib scrypt + TOTP (RFC 6238) + HMAC signed cookie — `data/auth.json` |
| Package mgr | uv — `pyproject.toml` + `uv.lock` are the only canonical sources |
| Tests | pytest + resppx — 294 passing |
| Lint/types | ruff (E,F,I,UP, line-length 100), mypy |
| Container | Docker multi-stage, non-root uid 1000, `qrencode` for TOTP QR |
| Proxy | Caddy 2 — TLS + Let's Encrypt; NO BasicAuth (auth is app-level) |
| Automation | Ansible (Vault-encrypted secrets in `all.yml`) |
| Security | fail2ban sshd jail |

## Key Files

- **`app.py`** — entry point: page config, auth gate, cookie components, DB boot, tabs
- **`src/auth_crypto.py`** — scrypt hashing, TOTP, otpauth URI, HMAC session tokens
- **`src/auth_store.py`** — `auth.json` load/save/validate (atomic 0600) + gate helpers
- **`src/auth_bootstrap.py`** — non-interactive bootstrap run by Ansible
- **`src/cookies.py`** — one-way CCv2 components (`_COOKIE_READER`/`_COOKIE_WRITER`) + session-token helpers
- **`src/db.py`** — schema (v1+v2) + CRUD + auto-migrations
- **`src/calculations.py`** — pure business logic (earnings, projections)
- **`src/chart_colors.py`** — palette + `color_for_modality()`
- **`src/charts.py` / `src/charts_analysis.py`** — Plotly factories (no DB access)
- **`src/formatting.py`** — `fmt_brl()`, `md_escape()`, `MONTHS_PT`
- **`src/insights_rules.py`** — rule-based PT insights
- **`src/llm_client.py`** — OpenRouter client + RAG context
- **`src/ui/login.py`** — auth gate, login/TOTP forms, sidebar header/footer, logout
- **`src/ui/sidebar.py`** — greeting, date row, modality inputs, Salvar
- **`src/ui/{today,month,analysis,chat,settings}.py`** — the 5 tabs
- **`scripts/manage_auth.py`** — SSH auth CLI (wrapper `radtracker-auth`): 2FA QR/activate/disable, password, username, status, repair
- **`.streamlit/config.toml`** — theme (dark primaryColor Teal-700 `#0F766E`)

## Database Schema (SQLite, 5 tables)

- **`modalities`** — slug PK, label, price, exams_per_hour, active, color, sort_order. Soft-delete (`active=0`) preserves history; re-adding reactivates.
- **`daily_production_items`** — PK (date, modality_slug); zero-count = DELETE, non-zero = UPSERT.
- **`modality_prices`** — price vigencies PK (slug, effective_from); a reajust never recomputes past faturamento.
- **`monthly_goals`** — PK year_month; missing month carries forward the most recent prior goal (45000.0 only when none ever recorded).
- **`user_settings`** — key/value (user_name, api_key, llm_prompt, llm_model, migration flags).

Auto-migrations run by `init_db()` are idempotent; legacy v1 tables dropped once.

## Session State

| Key | Source | Notes |
|-----|--------|-------|
| `all_modalities` / `active_modalities` / `prices` / `goal` / `user_name` | DB via `ensure_settings(conn)` | loaded lazily by every tab renderer |
| `auth_authenticated` | cookie restore / login | presence triggers cookie restore once per server session; logout sets False, never removes |
| `auth_username` | login | display-only |
| `auth_awaiting_totp` | login flow | transient between password and TOTP steps |
| `_auth_cookie_secure` | auth.json | drives Set-Cookie Secure flag |
| `active_tab_idx` | tab cookie | radio `key="main_tabs"` MUST stay (see constraints) |
| `historical_cache` | analysis tab | `{"key", "stats"}` invalidated on goal/modality change |
| `messages`, `chat_suggestions` | chat tab | history capped at 15 pairs |
| `goal_celebrated_YYYY-MM` | month tab | celebration rain once per month |

## Hard Constraints

- Python ≥ 3.12; Streamlit ≥ 1.54; PT-BR for all user-facing text.
- **No custom CSS / `unsafe_allow_html`** — theming via `.streamlit/config.toml`.
  Two narrow owner-approved exceptions: one CSS rule for tab font size (no font API
  exists), and `st.html()` for chat avatar colors.
- **Never import:** `skeleton`, `cookie_manager`, `add_vertical_space`, `app_logo`,
  `colored_header`, `row`, `stylable_container`, `tags` from streamlit-extras.
- **No emojis as functional icons** — `:material/` only (rain is fine).
- **No `st.form` in sidebar** — breaks date-dependent pre-fill. Login/TOTP forms in
  the main area are the only `st.form` usage.
- **No DB access in chart modules** — data as parameters.
- **Dynamic modalities** — never hardcode slugs/labels/prices in UI code.
- **`md_escape()`** on all LLM/BRL text rendered via markdown; `safe_stream` wrapper
  for `st.write_stream()`; both $ escaping rules per `docs/markdown-escaping-guide.md`.
- **Streamlit on loopback only** (127.0.0.1:8501) — Caddy is the sole public endpoint.
- **Auth state in `data/auth.json`** (gitignored) — stdlib crypto, no new deps.
- **Never log credentials** (passwords, TOTP codes, session secrets).
- **Tab radio requires `key="main_tabs"`** — without it, changing `index` discards
  the next click's delta (tab pings back). Tab row = `st.container(horizontal=True)`
  + radio + `st.space("stretch")` + natural-width Sair.
- **Cookie architecture:** `_COOKIE_READER` publishes once per server session (its
  `default` key needs `on_snapshot_json_change=lambda: None`, else
  `BidiComponentInvalidDefaultKeyError`); `_COOKIE_WRITER` never publishes; render
  the writer ONLY inside `render_login_gate` (duplicate render →
  `StreamlitDuplicateElementId`).
- **Sidebar footer is dynamic:** version from `pyproject.toml` (tomllib, cached per
  session), mode from `RADTRACKER_MODE` env (lan→local, internet→web), 2FA status
  re-read from `auth.json` every run.
- **"Radtracker"** capitalized in every user-visible string; code identifiers
  lowercase (`radtracker-session`, `radtracker-auth`).

## Style

- Functions 4–20 lines; files under 500 lines; early returns; max 2 indent levels.
- Explicit types (no `Any` except Streamlit API); docstrings on public functions.
- Charts: colors only via `color_for_modality()` / `CHART_COLORS` — no inline hex.
- Currency: `fmt_brl()` (Decimal HALF_UP).

## Business Constants

- Seeded modalities and production values in `_MODALITY_SEED` (src/db.py).
- Default monthly goal R$45.000 (fallback only; carry-forward otherwise).
- Production counted in dias corridos; `days_worked` is display-only, never in math.
- Chat: `_MAX_MESSAGE_PAIRS = 15`; streaming timeout 30s vs 15s one-shot.
- Colors: modality palette in DB `color` column; chart palette in `src/chart_colors.py`.

## Validation

```bash
uv run pytest tests/ -q                     # 294 passing
uv run ruff check src/ app.py scripts/ tests/
uv run mypy src/
ansible-lint ansible/                       # deployment changes
hadolint Dockerfile                         # Dockerfile changes
```

## Stop / Escalate

Ask before: DB schema changes, cross-tab or core-data-flow changes, new dependencies,
theme changes in `.streamlit/config.toml`, touching the chat streaming pipeline.

Proceed: tests, clear bug fixes, new pure functions or chart factories, docstrings,
refactors within one module, docs editing, new `MODALITY_COLORS` entries.

## Resolved Decisions (do not revisit)

- **App-level single-user auth** (scrypt password + optional TOTP) in `auth.json`; stdlib only.
- **Signed cookie session (HMAC-SHA256, 30 days)** — F5 must not re-login; cookie
  expiry is the re-auth interval; password change rotates `session_secret`, username
  change invalidates; no app-level rate limiting (TOTP is the anti-robot barrier).
- **One-way CCv2 cookie components** — CookieManager republishing caused rerun races.
- **2FA via SSH only** (`radtracker-auth`, QR in terminal) — secret never touches web.
- **fail2ban sshd jail** (Caddy 401 jail died with BasicAuth).
- **Bootstrap idempotent** — Ansible creates `auth.json` once from vault vars; redeploys
  never overwrite. `auth.json` deliberately not backed up (repair via CLI or redeploy).
- **Sidebar layout (owner-approved):** `# Radtracker` h1; greeting; `Data:` + date box
  on one row; stacked modality inputs; `Salvar` (natural width, secondary style);
  divider; footer captions `Radtracker v<ver> · <local|web>` + `2FA ativado./desativado.`.
- **Sair in the main tab row**, right-aligned via `st.space("stretch")`, natural width.
- **Dark mode:** primaryColor Teal-700 `#0F766E` — Streamlit always renders white text
  on primaryColor, so a light primary = white-on-white buttons.
- **Tab font-size CSS rule** — the single CSS exception (14px radio vs 16px text).
- **Version source of truth = `pyproject.toml`** — sidebar reads it at runtime; docs
  must not pin versions (removed deliberately).
- **`requirements.txt` removed** — `pyproject.toml` + `uv.lock` only.
- **AI insights live in Chat IA tab only** (Analysis AI section removed in 1.5.0).
- **Modality slugs immutable** after creation; label edits keep the slug.
- **Git deploy key** — ed25519 key auto-generated on VPS, registered via GitHub API.
- **API key in DB (`user_settings`)**, never `.env`/python-dotenv.

## Quick Start

```bash
cd /home/galvani/dev/radtracker
uv sync && uv run pytest tests/ -q && uv run streamlit run app.py
```

Deploy:
```bash
export VPS_HOST=10.10.10.209 VPS_USER=galvani   # LAN dev VPS
# or VPS_HOST=129.151.4.89                       # Oracle prod (internet mode)
ansible-galaxy collection install -r ansible/requirements.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml \
  --vault-password-file ansible/.vault_pass -e deployment_mode=lan
```

**LAN update always needs `-e deployment_mode=lan -e github_branch=<branch>`** —
without it the playbook switches the VPS to internet mode (Caddy ACME for the prod
domain).

Local dev scratch auth:
```bash
python -c "from src.auth_store import create_bootstrap_auth; print(create_bootstrap_auth('dev', 'dev-password-123', 'data/auth.json', cookie_secure=False))"
```

Read `docs/context.md` for module/data flow, `docs/deployment.md` for the full
deployment guide, `docs/markdown-escaping-guide.md` for `$` rules.
