# Implementation Plan — App-level Authentication with TOTP 2FA

Status: **approved, ready to implement**. All design decisions are locked (see
§13). Do not re-litigate them. Follow the TDD cycle from `AGENTS.md` and the
project conventions in `docs/meta-prompt.md`.

---

## 1. Goal

Replace Caddy BasicAuth with app-level authentication: username + password
(scrypt) plus optional TOTP 2FA (RFC 6238), for a **single user**.

- Credentials are created at **deploy time by Ansible** (bootstrap) from vault
  vars — the deployer's personal data, already the project's pattern.
- **2FA setup/reset is an SSH-only CLI script** (`manage_auth.py`, KIAUH-style
  menu). The TOTP secret and QR code **never touch the web** — QR is rendered
  in the terminal (`qrencode -t ANSIUTF8`) and scanned with the phone camera.
- SSH is the trust anchor. If you can read the server, you can read
  `auth.json`; 2FA here protects the **web login** against credential theft,
  not the server itself.

## 2. Scope boundaries — what we are NOT building

Critical. Do not drift into any of these:

- ❌ No new Python dependencies. **stdlib only** (`hashlib.scrypt`, `hmac`,
  `base64`, `struct`, `secrets`, `getpass`). `qrencode` is a system binary in
  the container (apt), not a Python dep.
- ❌ No DB schema change. No `users` table. Auth state lives in one JSON file:
  `data/auth.json`. (This keeps us clear of the "database schema" stop rule.)
- ❌ No email/SMTP, no registration, no forgot-password, no recovery tokens.
- ❌ No server-side session store. Session persistence is one signed,
  expiring cookie (HMAC-SHA256) via the existing `src/cookies.py` pattern —
  the only client-side auth state.
- ❌ No Authelia, no external IdP, no OAuth.
- ❌ No changes to tabs, data flow, SQLite, or the Chat IA pipeline.

## 3. Architecture

```
Browser ──https──> Caddy (TLS only, no basic_auth) ──> Streamlit
                                                          │
                                              render_login_gate (src/ui/login.py)
                                              │ reads/writes data/auth.json
                                                          │
SSH ──> /usr/local/bin/radtracker-auth ──> docker compose exec
              streamlit python -m scripts.manage_auth
```

| Concern | Where |
|---------|-------|
| Create user/password (bootstrap) | Ansible deploy → `src/auth_bootstrap.py` in container |
| Manage 2FA (QR, validation, resets) | SSH script `scripts/manage_auth.py` |
| Verify password + TOTP + session cookie | App gate (`src/ui/login.py` + helpers in `src/auth_store.py`) |
| Password hashing | `hashlib.scrypt` in `src/auth_crypto.py` (stdlib) |
| TOTP | RFC 6238, HMAC-SHA1, 6 digits, in `src/auth_crypto.py` (stdlib) |

## 4. Files

| File | Action |
|------|--------|
| `src/auth_crypto.py` | **new** — pure crypto (scrypt, TOTP, otpauth URI). No I/O, no Streamlit. |
| `src/auth_store.py` | **new** — `auth.json` load/save/validate + pure gate-logic helpers. No Streamlit. |
| `src/cookies.py` | **modify** — add session-cookie helpers (get/set/delete `radtracker_session`) using `CookieManager.set(..., max_age, secure)` / `delete()` — the existing dict-style helpers don't expose expiry/secure flags. |
| `src/auth_bootstrap.py` | **new** — non-interactive bootstrap (run by Ansible in container). |
| `src/ui/login.py` | **new** — Streamlit gate UI: session restore, login, TOTP step, banner, logout. |
| `scripts/manage_auth.py` | **new** — interactive KIAUH-style CLI (SSH). |
| `app.py` | **modify** — insert gate after `st.set_page_config`, before `get_connection()`. |
| `tests/test_auth_crypto.py` | **new** |
| `tests/test_auth_store.py` | **new** |
| `tests/test_auth_bootstrap.py` | **new** — tmp_path fixtures, `python -m src.auth_bootstrap` via subprocess (§11) |
| `Dockerfile` | **modify** — add `qrencode` to runtime stage apt install. |
| `Caddyfile` + `ansible/templates/Caddyfile.j2` | **modify** — remove `basic_auth` block. |
| `ansible/templates/.env.j2` | **modify** — remove `BASICAUTH_USERS` line. |
| `ansible/group_vars/all.yml` | **modify** — add `auth_username`/`auth_password` (vault). **Keep** `basicauth_users` until the production cutover is validated (§16); remove in a follow-up. |
| `ansible/playbooks/deploy.yml` | **modify** — bootstrap task, fail2ban → sshd jail, stale-file cleanup. |
| `ansible/playbooks/cleanup.yml` | **modify** — replace radtracker jail/filter removal with sshd jail. |
| `ansible/playbooks/health.yml` | **modify** — keep fail2ban check (no jail-specific assertion needed). |
| `docs/meta-prompt.md`, `docs/deployment.md`, `docs/context.md`, `README.md` | **modify** — reflect new auth (context.md is the module-by-module doc — new modules must be documented there). |
| `.gitignore` | **modify** — add `data/auth.json` and `data/.auth_creds` (see §15). |

`docker-compose.yml`: **no change** (`.env` still supplies `DOMAIN`/`TZ`; the
`data` bind mount already covers `auth.json`).

---

## 5. `src/auth_crypto.py` — pure crypto (spec)

All functions pure, no Streamlit, no filesystem. Explicit types (mypy runs on
`src/`).

### Password hashing (stdlib `hashlib.scrypt`)

Format string (single source of truth, used by app AND bootstrap):

```
scrypt$16384$8$1$<salt_hex>$<hash_hex>
```

- Params: `n=16384`, `r=8`, `p=1`, `dklen=32`, salt = `secrets.token_bytes(16)`.
- `hash_password(password: str) -> str` — returns the format string above.
- `verify_password(password: str, stored: str) -> bool` — parse params from
  `stored`, recompute, compare with `hmac.compare_digest`. Return `False` on
  malformed `stored` (never raise).

### TOTP (RFC 6238)

- `new_totp_secret() -> str` — `secrets.token_bytes(20)` → base32 without
  padding (`base64.b32encode(...).rstrip(b"=")`), 32 chars.
- `totp_code(secret_b32: str, t: int | None = None) -> str` — HMAC-SHA1,
  6 digits, step 30s hard-coded in this function; `t` in **seconds** (for
  tests). Formula: counter = `t // step`; `struct.pack(">Q", counter)`;
  dynamic truncation per RFC 4226 §5.3; result `f"{code % 1_000_000:06d}"`.
- `verify_totp(secret_b32: str, code: str, *, step_seconds: int = 30,
  window_steps: int = 1, now: int | None = None) -> bool` — accept if `code`
  matches any counter in `[now//step - window_steps, now//step + window_steps]`.
  Constant-time compare per candidate. Returns `False` (never raises) for any
  malformed input: empty/mis-padded base32 secret, non-numeric code.
- `otpauth_uri(secret_b32: str, username: str, issuer: str = "radtracker") -> str`
  — `otpauth://totp/{issuer}:{quoted}?secret={secret}&issuer={issuer}` where
  `quoted` is the username URL-encoded (`urllib.parse.quote`).

### Session token (signed cookie value)

- `new_session_secret() -> str` — `secrets.token_hex(32)`.
- `sign_session(username: str, secret_hex: str, expires: int) -> str` —
  `f"{expires}.{hmac_hex}"` where `hmac_hex` is HMAC-SHA256 of
  `f"radtracker-session:{username}:{expires}"` keyed by
  `bytes.fromhex(secret_hex)`.
- `verify_session(username: str, secret_hex: str, token: str, now: int)
  -> bool` — split on `.`, require exactly 2 parts, `int(expires)` must be
  `> now`, recompute and compare with `hmac.compare_digest`. Returns `False`
  (never raises) for any malformed token or bad secret.

### Reference vectors (must pass — RFC 6238 Appendix B, SHA1, 6-digit)

Secret: `base64.b32encode(b"12345678901234567890")` (i.e. ASCII 20 bytes).

| T (seconds) | 6-digit code |
|-------------|--------------|
| 59 | 287082 |
| 1111111109 | 081804 |
| 1111111111 | 050471 |
| 1234567890 | 005924 |
| 2000000000 | 279037 |
| 20000000000 | 353130 |

---

## 6. `src/auth_store.py` — auth.json + gate logic (spec)

### Path convention

`AUTH_PATH = "data/auth.json"` — relative to cwd, matching `src/db.py`
(`sqlite:///data/telerrad.db`) and `scripts/import_csv.py`. In the container
`WORKDIR=/app` → resolves to the bind-mounted `data/`. Tests always pass an
explicit tmp path.

### Schema (versioned)

```json
{
  "version": 1,
  "username": "admin",
  "password_hash": "scrypt$16384$8$1$<salt_hex>$<hash_hex>",
  "totp_secret": null,
  "totp_required": false,
  "totp_step_seconds": 30,
  "totp_window_steps": 1,
  "session_secret": "<64 hex chars>",
  "session_days": 30,
  "session_cookie_secure": true
}
```

- `totp_required: false` until `manage_auth.py` activates 2FA.
- `session_secret` is generated at bootstrap and signs the session cookie.
  Changing the password rotates it (§9 option 3) — invalidating all cookies.
- `session_cookie_secure: false` only when the site is really served over
  plain HTTP (browsers refuse `Secure` cookies over HTTP). Both deploy modes
  end up on HTTPS (Caddy redirects HTTP→HTTPS even in LAN mode, with a
  self-signed cert), so Ansible always writes `true` — the flag exists for
  hypothetical plain-HTTP setups (§8, §10).

### Functions

- `class AuthError(Exception)` — message must include the offending value and
  expected shape (project error convention).
- `load_auth(path: str) -> dict` — read JSON, validate schema (all keys,
  correct types). Raise `AuthError` on missing file, invalid JSON, or invalid
  schema. **Fail loud — never a silent default.**
- `save_auth(auth: dict, path: str) -> None` — atomic: write to
  `path + ".tmp"`, `os.chmod(tmp, 0o600)` **before** `os.replace` (chmod
  after replace leaves a window with umask perms — 0644 exposes the password
  hash and TOTP secret).
- `create_bootstrap_auth(username: str, password: str, path: str) -> str` —
  **idempotent**: if `path` exists → return `"exists"` (no-op, never
  overwrite — the user may have changed things via the SSH script). Else write
  bootstrap (2FA off, defaults above) and return `"created"`. Raise
  `AuthError` if `password` has fewer than 8 chars — same floor as
  `manage_auth.py` option 3; a weak vault password would otherwise become a
  weak web login with no network-level rate limit (§15).
- Pure gate helpers (no `st`, unit-testable):
  - `verify_login(auth: dict, username: str, password: str) -> bool`
  - `is_totp_required(auth: dict) -> bool`
  - `verify_totp_code(auth: dict, code: str, now: int) -> bool` — uses
    `auth["totp_secret"]`, `totp_step_seconds`, `totp_window_steps`; returns
    `False` (never raises) when `totp_secret` is `None` or empty.
  - `new_session_token(auth: dict, now: int) -> str` —
    `sign_session(auth["username"], auth["session_secret"],
    now + auth["session_days"] * 86400)`.
  - `verify_session_token(auth: dict, token: str, now: int) -> bool` —
    wraps `verify_session` with the stored username/secret; `False` (never
    raises) for `None`/empty/malformed tokens.

### Session-state keys (used by the gate)

`auth_authenticated` (present from the first run on: `True`/`False`, never
removed — absence is what triggers the cookie restore), `auth_username`,
`auth_awaiting_totp` (transient, between the password and TOTP steps).
Everything else lives in the signed cookie — no failed-attempt counters,
no re-auth timestamps (§13).

---

## 7. `app.py` + `src/ui/login.py` — the web gate

Insertion point in `app.py`: **immediately after `st.set_page_config`**,
before `get_connection()` / `init_db()` / sidebar / tabs. `set_page_config`
must stay the first Streamlit command.

```python
# top of app.py, with the existing imports
# (imports after st.set_page_config() trip ruff E402 — keep them at the top)
from src.auth_store import AUTH_PATH, AuthError, load_auth
from src.cookies import get_cookie_manager
from src.ui.login import render_login_gate, render_logout_button

# ... st.set_page_config(...) stays the first Streamlit command ...

# exactly one CookieManager construction per run (a second one raises
# StreamlitDuplicateElementKey); every run's render flushes queued writes
cookie_mgr = get_cookie_manager()

# immediately after set_page_config, before get_connection()
try:
    auth = load_auth(AUTH_PATH)
except AuthError as exc:
    st.error(f"Autenticação não configurada: {exc}")
    st.markdown("Execute o deploy Ansible ou o script `radtracker-auth` via SSH.")
    st.stop()

render_login_gate(auth, cookie_mgr)
render_logout_button(cookie_mgr)
# gate calls st.stop() internally while not authenticated

# existing code below unchanged (get_connection, init_db, sidebar, tabs)
```

### `render_login_gate(auth: dict)` — states (all text PT-BR)

0. **Session restore** — before any form: read the `radtracker_session`
   cookie (`src/cookies.py` helpers); `verify_session_token` → set
   `auth_authenticated=True` + `auth_username` and continue, no prompt. This
   is what keeps F5/new tabs logged in. If the cookie manager is not ready
   yet (component sync on first run), fall through to the login form — same
   quirk as the tab cookie, accepted.
1. **Login form** (`st.form`, `text_input(type="password")` for password):
   - Submit → `verify_login`. Wrong → generic "Usuário ou senha inválidos."
     (no counter, no lockout — §13).
   - Correct → if `is_totp_required(auth)` → state 2; else establish the
     session (below) and continue.
2. **TOTP step** — "Código do autenticador" (`text_input(type="password")`,
   `max_chars=6`), submit → `verify_totp_code`; wrong →
   "Código inválido ou expirado". Correct → establish session.
   - **Establish session** = `auth_authenticated=True`, `auth_username`, and
     persist `new_session_token(auth, now)` as the `radtracker_session`
     cookie (`max_age = session_days * 86400`, `secure` per
     `session_cookie_secure`, `samesite="lax"`).
3. **2FA-off banner** — when `auth_authenticated` and `not is_totp_required`:
   amber banner at top: "⚠️ 2FA desativada — rode `radtracker-auth` no servidor
   para ativar." Visible in the sidebar area or top of main; either is fine,
   keep it constant.
4. **Missing auth.json** — handled in `app.py` (fail loud, never open).

### `render_logout_button()`

Small button in the sidebar (before `render_sidebar`'s own content): clears
`auth_authenticated`/`auth_username`, deletes the `radtracker_session`
cookie, then `st.rerun()`. Call it from `app.py` right after
`render_login_gate(auth)`.

### Implementation notes (Streamlit specifics)

- Use `st.form` for login/TOTP (Enter submits; no rerun per keystroke).
  This is the **only** `st.form` usage in the project — intentional, since the
  gate is a state machine; note it in a comment.
- **CookieManager: exactly one construction per run**, in `app.py`, passed
  down to the gate and the tab-cookie helpers. `cookie_manager()` called
  twice in one run raises `StreamlitDuplicateElementKey` — and since
  `set()`/`delete()` are only queued until the component renders, every run
  must render it exactly once or queued writes never reach the browser.
  (Found in implementation: the first version let the gate and
  `set_session_token` construct their own managers; the queued login cookie
  was silently never written.)
- **Session restore runs once per server session** — only when
  `auth_authenticated` is absent from `st.session_state`. Logout sets it to
  `False` (never removes the key), so the asynchronous cookie delete cannot
  immediately re-authenticate the session from a stale snapshot.
- Give every widget a unique `key=` per state (login form and TOTP form can
  render at different times on the same run — avoid duplicate-widget-ID
  errors).
- **Never log, print, or write passwords or TOTP codes** (project logging is
  structured JSON; credentials are exempt).
- The Streamlit healthcheck `/_stcore/health` (loopback, used by compose and
  the playbook) is **unaffected** by the gate — do not touch it.

Accepted behaviors (do not "fix"): the session cookie is a signed **bearer
token** — any browser holding a valid cookie is in until expiry (default 30
days), explicit logout, or password change (rotates `session_secret`); each
browser/device logs in independently (cookies are not shared); the first
load may briefly show the login form while the cookie component syncs (same
quirk as the tab cookie).

---

## 8. `src/auth_bootstrap.py` — Ansible bootstrap (non-interactive)

- Entry: `python -m src.auth_bootstrap` (run inside the container by Ansible,
  cwd `/app`).
- Reads credentials from `data/.auth_creds` (**relative** — same convention as
  `AUTH_PATH`; line 1 = username, line 2 = password, optional line 3 =
  `cookie_secure:true|false`; Ansible creates and later deletes this file).
  Missing line 3 → `true`. Ansible always writes `true`: Caddy serves HTTPS
  in both modes (LAN gets a self-signed cert), so `Secure` cookies work
  everywhere.
- Bootstrap writes the §6 defaults, including a fresh `session_secret`
  (`new_session_secret()`), `session_days: 30`, and `session_cookie_secure`
  from the creds flag.
- Calls `create_bootstrap_auth(...)`; prints `created` or `exists` (stdout —
  Ansible keys `changed_when` off it).
- Missing creds file **and** missing auth.json → exit 1 with a clear message
  (fail loud in the playbook).

---

## 9. `scripts/manage_auth.py` — SSH management CLI (KIAUH-style)

Interactive menu (plain `input()`/`getpass`, ASCII box, PT-BR). Must work with
a TTY (`docker compose exec` without `-T`).

```
┌──────────────────────────────────────────┐
│ radtracker — Gestão de autenticação      │
├──────────────────────────────────────────┤
│ 1) Ativar / reconfigurar 2FA (QR code)   │
│ 2) Desativar 2FA                         │
│ 3) Trocar senha                          │
│ 4) Trocar usuário                        │
│ 5) Status                                │
│ 6) Reparar auth.json                     │
│ 0) Sair                                  │
└──────────────────────────────────────────┘
```

Behavior per option (all writes via `auth_store.save_auth`, atomic, 0600):

1. **2FA**: `new_totp_secret()` → build URI → if `shutil.which("qrencode")`,
   `subprocess.run(["qrencode", "-t", "ANSIUTF8", uri])` (prints scannable
   half-block QR to the terminal); always also print the `otpauth://` URI as
   fallback. Prompt "Digite o código atual do Google Authenticator" →
   `verify_totp` with the configured step/window → only on success set
   `totp_secret` + `totp_required=true` and save.
2. **Disable 2FA**: confirm, set `totp_required=false` (keep secret for
   potential re-enable).
3. **Change password**: `getpass` twice (no echo), require match, min 8 chars,
   save new hash **and rotate `session_secret`** (invalidates all existing
   session cookies — stolen password changed → old sessions die).
4. **Change username**: plain prompt, non-empty, save.
5. **Status**: username, 2FA on/off, step/window, session days, cookie
   secure flag, auth.json path + mode — **never print the password hash,
   TOTP secret, or session secret**.
6. **Repair**: if auth.json missing or `load_auth` raises → offer to re-init
   (username + password, 2FA off). If present → say so and exit.

On `load_auth` failure at startup, offer option 6 immediately.

---

## 10. Ansible & deployment changes

### `ansible/group_vars/all.yml`

- Add (vault-encrypted, same pattern as `basicauth_users`):
  `auth_username: !vault |` and `auth_password: !vault |`.
- Remove `basicauth_users: !vault |` (no longer used anywhere).
- **Workflow** (the vault password file `ansible/.vault_pass` exists locally,
  gitignored):
  1. Encrypt each value:
     `ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --name auth_username '<value>'`
     (same for `auth_password`; read from stdin to avoid shell history).
  2. Paste the `!vault |` output blocks into `all.yml` via
     `ansible-vault edit --vault-password-file ansible/.vault_pass ansible/group_vars/all.yml`.
  3. Do not commit the plaintext values anywhere.

### Templates

- `ansible/templates/Caddyfile.j2` and root `Caddyfile`: delete the
  `basic_auth * { ... }` block. Keep TLS, headers, log, reverse_proxy.
- `ansible/templates/.env.j2`: delete the `BASICAUTH_USERS=...` line. Keep
  `DOMAIN` + `TZ`. The `$$` escaping convention in `docs/meta-prompt.md`
  becomes obsolete for this var — leave the note only if still relevant.

### `Dockerfile`

Runtime stage apt install: add `qrencode` to the existing
`curl sqlite3` line.

### `ansible/playbooks/deploy.yml`

1. In the fail2ban block, **replace** the "Create fail2ban filter for Caddy
   BasicAuth failures" + "Create radtracker jail" tasks with:
   - `file: state=absent` for `/etc/fail2ban/jail.d/radtracker.conf` and
     `/etc/fail2ban/filter.d/radtracker-caddy.conf` (stale-file cleanup so
     upgrades are idempotent).
   - `copy` task writing `/etc/fail2ban/jail.d/sshd.conf`:
     `[sshd] enabled = true, port = ssh, logpath = %(sshd_backend)s,
     maxretry = 5, findtime = 600, bantime = 3600`.
   - Keep: whitelist `local.conf`, `apt: fail2ban`, ensure running.
2. **Remove** the "Create Caddy access log file (fail2ban requires it)" task
   (Caddy creates its own log file; the `caddy_logs` volume stays for the
   access log).
3. **After** the "Run DB migrations" task, add the auth bootstrap block —
   wrapped in `block:`/`always:` so the creds cleanup runs **even when the
   bootstrap fails** (a failed bootstrap must never leave the plaintext
   password on disk):
   - `block:`
     - `copy` task: `/app/data/.auth_creds` equivalent on host =
       `{{ radtracker_data_dir }}/.auth_creds`, content
       `{{ auth_username }}\n{{ auth_password }}\ncookie_secure:true\n`,
       `owner: 1000, group: 1000,
       mode: "0600"`, `no_log: true`. (Caddy serves HTTPS in both modes —
       LAN uses a self-signed cert — so `Secure` cookies work everywhere.)
     - `community.docker.docker_compose_v2_exec`: `service: streamlit`,
       `command: python -m src.auth_bootstrap`,
       `register: auth_bootstrap`, `changed_when:
       auth_bootstrap.stdout is search("created")`.
   - `always:` → `file: state=absent` for the creds file.
4. "Deployment complete" message: append a hint to run
   `radtracker-auth` via SSH to enable 2FA.

### `ansible/playbooks/cleanup.yml`

Replace "Remove fail2ban radtracker jail" + "Remove fail2ban radtracker
filter" tasks with a single "Remove fail2ban sshd jail" task
(`/etc/fail2ban/jail.d/sshd.conf` absent).

### `ansible/playbooks/health.yml`

Keep the fail2ban active check as-is (still valid). No jail-specific
assertion needed.

### Host wrapper (SSH entry point)

Ansible `copy` task creating `/usr/local/bin/radtracker-auth` (mode 0755):

```sh
#!/bin/sh
exec docker compose --project-directory {{ radtracker_dir }} \
  exec streamlit python -m scripts.manage_auth
```

(`manage_auth.py` is in the image via the existing `COPY . .`. **Must run as
`-m scripts.manage_auth`**: the container `WORKDIR` is `/app`, and
`python /app/scripts/manage_auth.py` would set `sys.path[0]=/app/scripts`,
making `import src.*` fail. The `-m` form puts `/app` on `sys.path`;
`scripts/` works as a namespace package, no `__init__.py` needed.)

- Requires a TTY (interactive menu + QR) — fine under SSH; do **not** add `-T`.
- Requires the container running; if it is not, let Docker's own error message
  surface (do not mask it).

---

## 11. Tests

`tests/test_auth_crypto.py`:
- RFC 6238 vectors from §5 (six rows, explicit `t`).
- `verify_totp`: current code True; wrong code False; code from
  `window_steps` away True; beyond window False.
- `new_totp_secret`: 32-char base32; two calls differ.
- `otpauth_uri`: exact format; username with spaces/`@` is URL-encoded.
- `hash_password`/`verify_password`: roundtrip True; wrong password False;
  tampered stored string (flip a char in hash hex) False; malformed stored
  string False (no exception).
- `sign_session`/`verify_session`: roundtrip True (fixed
  username/secret/expires/now); wrong secret False; tampered token False;
  `now >= expires` False; malformed token False (no exception).
- `new_session_secret`: 64 hex chars; two calls differ.

`tests/test_auth_bootstrap.py` (tmp_path fixtures, invokes `python -m` via
`subprocess` with env `PYTHONPATH` pointing at the repo, or calls `main()`
directly with `sys.argv` monkeypatched — either is fine, assert on exit code
and stdout):
- bootstrap with no creds file and no auth.json → exit 1, clear message.
- bootstrap with creds file → creates auth.json (`created`), 2FA off,
  defaults (incl. `session_secret` 64-hex, `session_days` 30,
  `session_cookie_secure` true), mode 0600.
- bootstrap with creds line 3 `cookie_secure:false` → schema reflects `false`.
- bootstrap with existing auth.json → exit 0, `exists`, file untouched
  (modify it first, assert unchanged).

`tests/test_auth_store.py` (tmp_path fixtures):
- `create_bootstrap_auth` creates file with defaults; second call returns
  `"exists"` and does not overwrite a modified file.
- `load_auth` on missing file → `AuthError`; invalid JSON → `AuthError`;
  missing/renamed key → `AuthError`; valid file roundtrip.
- `save_auth` produces mode 0600.
- `verify_login` correct/wrong; `is_totp_required` reflects schema.
- `new_session_token`/`verify_session_token`: roundtrip True; tampered
  signature False; expired `now` False; rotated `session_secret` False;
  malformed token (no dot, non-int expires, empty) False — never raises.
  Username change (option 4) invalidates old tokens.

Gate UI is thin; all branch logic lives in the pure helpers above (tested).
No Streamlit mocking required.

---

## 12. Validation (quality gate — all must pass)

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run mypy src/
ansible-lint ansible/
hadolint Dockerfile
yamllint .
```

Manual spot-check: `uv run streamlit run app.py` locally with a scratch
`data/auth.json` (create via `python -m src.auth_bootstrap` with a temp creds
file, or a small python snippet using `src.auth_store`). Then, in the built
container: `docker compose exec streamlit python -m scripts.manage_auth`
→ verify QR prints with ANSI half-blocks and the scan + code validation loop
closes.

## 13. Locked decisions (traceability — do not reopen)

- Single user; no multi-tenant; no data isolation.
- Bootstrap user/password from Ansible vault (fixed password, user's
  responsibility). No interactive prompts in Ansible.
- 2FA setup/reset strictly via SSH script; QR rendered in terminal
  (`qrencode -t ANSIUTF8`); `otpauth://` URI printed as fallback.
- Session persistence: signed session cookie (HMAC-SHA256, `session_days`
  default 30) — F5/new tab stay logged in; logout and password change
  (rotates `session_secret`) revoke it. The cookie expiry **is** the re-auth
  interval — there is no separate TOTP re-prompt.
- No lockout / rate limiting in the app. A per-session lockout is cosmetic
  against scripts (fresh session = fresh counter) and hostile to humans —
  removed. Anti-robot protection = TOTP; on the final Cloudflare domain,
  edge rate limiting (free tier) adds the network-level layer (§16).
- fail2ban: Caddy 401 jail removed (Streamlit never returns 401); sshd jail
  enabled instead.
- No new Python dependencies (stdlib + `qrencode` system binary).
- Caddy keeps TLS/no-cache headers; `basic_auth` removed.

## 14. Sequencing & commits

TDD order (each step green before the next):

1. `src/auth_crypto.py` + `tests/test_auth_crypto.py`
2. `src/auth_store.py` + `tests/test_auth_store.py`
3. `src/ui/login.py` + `app.py` gate
4. `scripts/manage_auth.py` + `src/auth_bootstrap.py` (manual spot-check)
5. `Dockerfile`, Caddyfile(s), `.env.j2`, ansible playbooks + vault vars
6. Docs (`meta-prompt.md`, `deployment.md`, `README.md`)
7. Full quality gate (§12)

Conventional commits, one per logical unit, e.g.:
`feat: app-level login with scrypt + TOTP 2FA`,
`feat: ssh auth management script (manage_auth)`,
`chore: ansible auth bootstrap and fail2ban sshd jail`,
`docs: authentication architecture`.

**Do not tag or release** — version bump + tag is Galvani's step per
`AGENTS.md` release checklist.

## 15. Risks & edge cases (handle, don't ignore)

- **Corrupt/missing auth.json** → app shows explicit error + recovery hint;
  `manage_auth.py` option 6 repairs. Never auto-create from the app.
- **Server clock drift** > window → TOTP rejects valid codes. `window_steps`
  default 1 covers small drift; status option shows nothing clock-related —
  note in deployment docs to keep NTP enabled (standard Ubuntu default).
- **Upgrade path**: servers deployed before this change still have the old
  jail/filter files — the playbook removes them (idempotent upgrade). Existing
  `basicauth_users` vault var is removed; `.env` regenerated without it.
- **TOTP replay within the 30s window** — standard TOTP behavior, accepted.
- **Accidental commit of secrets** — `.gitignore` must gain `data/auth.json`
  (password hash + TOTP secret) and `data/.auth_creds` (plaintext password)
  **in the same commit** as the auth modules. Currently only `data/*.db` and
  `data/app.log` are ignored.
- **Web brute force after basic_auth removal** — the fail2ban 401 jail dies
  with basic_auth and the app has **no rate limiting at all**. TOTP is the
  barrier, and it is **off until the SSH activation step** — activate 2FA
  immediately after every deploy (§16). On the final Cloudflare domain, a
  free-tier rate-limit rule restores network-level protection (§16 phase 4).
- **Session cookie is a bearer token** — whoever holds a valid cookie is in
  until expiry. Mitigations: 30-day expiry, logout deletes it, password
  change rotates `session_secret` (kills all cookies), username change
  invalidates it (the signature binds the username). `streamlit-extras` sets
  cookies via a component, so `HttpOnly` is not guaranteed — accepted: the
  project forbids `unsafe_allow_html` (the usual XSS vector), so token theft
  via injected JS is out of scope.
- **`auth.json` is not backed up** — deliberate, not a gap: `backup.yml`
  exports only `telerrad.db`, keeping password hashes and TOTP/session
  secrets out of backup rotation. Documented here so nobody "fixes" it by
  adding secrets to backups. Losing `data/` costs only the credentials:
  re-init via SSH (`manage_auth.py` option 6) or a redeploy.

---

## 16. Rollout — dev VPS first, production only after validation

Two live targets share one inventory (host from `VPS_HOST`/`VPS_USER` env):
production `radtracker.duckdns.org` (Oracle) and the LAN dev VPS
`10.10.10.209` (`deployment_mode=lan`; Caddy serves HTTPS with a self-signed
cert even on LAN — the gate works the same).
Order is mandatory:

1. **Implement + quality gate locally** (§12).
2. **Dev VPS 10.10.10.209** — full `deploy.yml` with the vault auth vars
   (`VPS_HOST=10.10.10.209 VPS_USER=galvani ... -e deployment_mode=lan`).
   The site is served over HTTPS with a self-signed cert (Caddy redirects
   HTTP→HTTPS) — accept the browser warning once. Validate before touching
   production:
   - gate blocks the app; login works; wrong password → generic error;
   - **F5 and new tab keep the session** (Secure cookie round-trip over
     HTTPS proves `session_cookie_secure=true` took effect);
   - `radtracker-auth` via SSH: QR renders, phone scans, code activates 2FA;
   - TOTP login; logout button (cookie deleted → next F5 shows the form);
   - fail2ban: sshd jail active, old radtracker jail/filter gone;
   - `health.yml` green; Caddy serves without basic_auth.
3. **radtracker.duckdns.org (Oracle)** — full `deploy.yml` (default
   deployment_mode), then **immediately** SSH in and enable 2FA
   (`radtracker-auth` option 1). Until that step the app is password-only
   with no network-level brute-force protection (§15).
4. **Real production domain (Cloudflare free tier)** — only after duckdns is
   perfect. Same `deploy.yml` with `domain` set to the real domain.
   Cloudflare specifics:
   - DNS record **proxied** (orange cloud); SSL/TLS mode **Full (strict)** —
     Caddy keeps terminating TLS on the origin with its own Let's Encrypt
     cert, Cloudflare terminates at the edge. Never "Flexible" (edge-only
     TLS sends credentials to the origin over plain HTTP).
   - WebSockets pass through Cloudflare free — Streamlit requires them; no
     extra config.
   - Cookie behavior unchanged (`session_cookie_secure=true`; Cloudflare
     forwards cookies transparently).
   - **Recommended**: a free-tier rate-limit rule on the app and/or Bot
     Fight Mode — this restores the network-level anti-robot layer that
     basic_auth + fail2ban used to provide (§15).

**Never use `update.yml` for this cutover.** It re-templates the Caddyfile
and `.env` and rebuilds, but runs no bootstrap, creates no `radtracker-auth`
wrapper, and touches no fail2ban config — on an unprepared server it strips
basic_auth while the new app stops at "Autenticação não configurada". The app
stays blocked (no data exposure), but it is down until `deploy.yml` runs.

**Rollback compat:** old Caddyfile/.env templates reference `basicauth_users`.
Keep that vault var in `all.yml` until the production cutover is validated;
remove it afterwards in a follow-up chore.
