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
- ❌ No session cookies / "remember me". Session lives in `st.session_state`.
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
              streamlit python /app/scripts/manage_auth.py
```

| Concern | Where |
|---------|-------|
| Create user/password (bootstrap) | Ansible deploy → `src/auth_bootstrap.py` in container |
| Manage 2FA (QR, validation, resets) | SSH script `scripts/manage_auth.py` |
| Verify password + TOTP + re-auth | App gate (`src/ui/login.py` + helpers in `src/auth_store.py`) |
| Password hashing | `hashlib.scrypt` in `src/totp.py` (stdlib) |
| TOTP | RFC 6238, HMAC-SHA1, 6 digits, in `src/totp.py` (stdlib) |

## 4. Files

| File | Action |
|------|--------|
| `src/totp.py` | **new** — pure crypto (scrypt, TOTP, otpauth URI). No I/O, no Streamlit. |
| `src/auth_store.py` | **new** — `auth.json` load/save/validate + pure gate-logic helpers. No Streamlit. |
| `src/auth_bootstrap.py` | **new** — non-interactive bootstrap (run by Ansible in container). |
| `src/ui/login.py` | **new** — Streamlit gate UI: login, TOTP step, re-auth, banner, logout. |
| `scripts/manage_auth.py` | **new** — interactive KIAUH-style CLI (SSH). |
| `app.py` | **modify** — insert gate after `st.set_page_config`, before `get_connection()`. |
| `tests/test_totp.py` | **new** |
| `tests/test_auth_store.py` | **new** |
| `Dockerfile` | **modify** — add `qrencode` to runtime stage apt install. |
| `Caddyfile` + `ansible/templates/Caddyfile.j2` | **modify** — remove `basic_auth` block. |
| `ansible/templates/.env.j2` | **modify** — remove `BASICAUTH_USERS` line. |
| `ansible/group_vars/all.yml` | **modify** — add `auth_username`/`auth_password` (vault); remove `basicauth_users`. |
| `ansible/playbooks/deploy.yml` | **modify** — bootstrap task, fail2ban → sshd jail, stale-file cleanup. |
| `ansible/playbooks/cleanup.yml` | **modify** — replace radtracker jail/filter removal with sshd jail. |
| `ansible/playbooks/health.yml` | **modify** — keep fail2ban check (no jail-specific assertion needed). |
| `docs/meta-prompt.md`, `docs/deployment.md`, `docs/context.md`, `README.md` | **modify** — reflect new auth (context.md is the module-by-module doc — new modules must be documented there). |
| `.gitignore` | **modify** — add `data/auth.json` and `data/.auth_creds` (see §15). |

`docker-compose.yml`: **no change** (`.env` still supplies `DOMAIN`/`TZ`; the
`data` bind mount already covers `auth.json`).

---

## 5. `src/totp.py` — pure crypto (spec)

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
  "reauth_interval_hours": 24
}
```

- `totp_required: false` until `manage_auth.py` activates 2FA.
- `reauth_interval_hours: 0` = never re-prompt.

### Functions

- `class AuthError(Exception)` — message must include the offending value and
  expected shape (project error convention).
- `load_auth(path: str) -> dict` — read JSON, validate schema (all keys,
  correct types). Raise `AuthError` on missing file, invalid JSON, or invalid
  schema. **Fail loud — never a silent default.**
- `save_auth(auth: dict, path: str) -> None` — atomic: write to
  `path + ".tmp"`, `os.replace`, then `os.chmod(path, 0o600)`.
- `create_bootstrap_auth(username: str, password: str, path: str) -> str` —
  **idempotent**: if `path` exists → return `"exists"` (no-op, never
  overwrite — the user may have changed things via the SSH script). Else write
  bootstrap (2FA off, defaults above) and return `"created"`.
- Pure gate helpers (no `st`, unit-testable):
  - `verify_login(auth: dict, username: str, password: str) -> bool`
  - `is_totp_required(auth: dict) -> bool`
  - `verify_totp_code(auth: dict, code: str, now: int) -> bool` — uses
    `auth["totp_secret"]`, `totp_step_seconds`, `totp_window_steps`; returns
    `False` (never raises) when `totp_secret` is `None` or empty.
  - `should_reauth(auth: dict, last_code_ts: int, now: int) -> bool` —
    `False` if `not is_totp_required(auth)` **or** `reauth_interval_hours == 0`;
    else `now - last_code_ts >= reauth_interval_hours * 3600`. (Without the
    `totp_required` guard: 2FA disabled + interval set would demand a code the
    app cannot verify — `totp_secret` is `None`.)
  - `lockout_status(attempts: int, lockout_until: int, now: int) -> tuple[bool, int]`
    — returns `(locked, seconds_remaining)`; lockout when
    `now < lockout_until`.

### Session-state keys (used by the gate)

`auth_authenticated`, `auth_username`, `auth_last_code_ts`,
`auth_failed_attempts`, `auth_lockout_until`.

---

## 7. `app.py` + `src/ui/login.py` — the web gate

Insertion point in `app.py`: **immediately after `st.set_page_config`**,
before `get_connection()` / `init_db()` / sidebar / tabs. `set_page_config`
must stay the first Streamlit command.

```python
# after set_page_config
from src.auth_store import AUTH_PATH, load_auth, AuthError
from src.ui.login import render_login_gate, render_logout_button

try:
    auth = load_auth(AUTH_PATH)
except AuthError as exc:
    st.error(f"Autenticação não configurada: {exc}")
    st.markdown("Execute o deploy Ansible ou o script `radtracker-auth` via SSH.")
    st.stop()

render_login_gate(auth)
# gate calls st.stop() internally while not authenticated

# existing code below unchanged (get_connection, init_db, sidebar, tabs)
```

### `render_login_gate(auth: dict)` — states (all text PT-BR)

1. **Login form** (`st.form`, `text_input(type="password")` for password):
   - Submit → `verify_login`. Wrong → increment `auth_failed_attempts`; if
     `lockout_status` says locked, disable form and show
     "Muitas tentativas. Tente novamente em Xs." Lockout: 5 attempts → 15 min
     (`auth_lockout_until = now + 900`).
   - Correct → if `is_totp_required(auth)` → state 2; else set
     `auth_authenticated=True`, `auth_last_code_ts=now`, continue.
2. **TOTP step** — "Código do autenticador" (`text_input(type="password")`,
   `max_chars=6`), submit → `verify_totp_code`; wrong →
   "Código inválido ou expirado" (also counts as a failed attempt). Correct →
   `auth_authenticated=True`, `auth_last_code_ts=now`.
3. **Re-auth** — when `should_reauth(...)` is true, block content and show
   only the TOTP code field ("Sessão expirada — confirme o código"). Password
   is **not** re-asked. On success refresh `auth_last_code_ts`.
4. **2FA-off banner** — when `auth_authenticated` and `not is_totp_required`:
   amber banner at top: "⚠️ 2FA desativada — rode `radtracker-auth` no servidor
   para ativar." Visible in the sidebar area or top of main; either is fine,
   keep it constant.
5. **Missing auth.json** — handled in `app.py` (fail loud, never open).

### `render_logout_button()`

Small button in the sidebar (before `render_sidebar`'s own content): clears
`auth_authenticated`/`auth_last_code_ts`, then `st.rerun()`. Call it from
`app.py` right after `render_login_gate(auth)`.

### Implementation notes (Streamlit specifics)

- Use `st.form` for login/TOTP/re-auth (Enter submits; no rerun per keystroke).
  This is the **only** `st.form` usage in the project — intentional, since the
  gate is a state machine; note it in a comment.
- Give every widget a unique `key=` per state (login form, TOTP form, re-auth
  form render at different times on the same run — avoid duplicate-widget-ID
  errors).
- **Never log, print, or write passwords or TOTP codes** (project logging is
  structured JSON; credentials are exempt).
- The Streamlit healthcheck `/_stcore/health` (loopback, used by compose and
  the playbook) is **unaffected** by the gate — do not touch it.

Accepted behaviors (do not "fix"): each browser tab is its own session and
logs in independently; no remember-me; a wrong TOTP counts toward the lockout.

---

## 8. `src/auth_bootstrap.py` — Ansible bootstrap (non-interactive)

- Entry: `python -m src.auth_bootstrap` (run inside the container by Ansible,
  cwd `/app`).
- Reads credentials from `data/.auth_creds` (**relative** — same convention as
  `AUTH_PATH`; line 1 = username, line 2 = password; Ansible creates and later
  deletes this file).
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
   save new hash.
4. **Change username**: plain prompt, non-empty, save.
5. **Status**: username, 2FA on/off, step/window, reauth interval, auth.json
   path + mode — **never print the password hash or TOTP secret**.
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
3. **After** the "Run DB migrations" task, add the auth bootstrap block:
   - `copy` task: `/app/data/.auth_creds` equivalent on host =
     `{{ radtracker_data_dir }}/.auth_creds`, content
     `{{ auth_username }}\n{{ auth_password }}\n`, `owner: 1000, group: 1000,
     mode: "0600"`, `no_log: true`.
   - `community.docker.docker_compose_v2_exec`: `service: streamlit`,
     `command: python -m src.auth_bootstrap`,
     `register: auth_bootstrap`, `changed_when:
     auth_bootstrap.stdout is search("created")`.
   - `file: state=absent` for the creds file (cleanup, always).
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
  exec streamlit python /app/scripts/manage_auth.py
```

(`manage_auth.py` is in the image via the existing `COPY . .`.)

- Requires a TTY (interactive menu + QR) — fine under SSH; do **not** add `-T`.
- Requires the container running; if it is not, let Docker's own error message
  surface (do not mask it).

---

## 11. Tests

`tests/test_totp.py`:
- RFC 6238 vectors from §5 (six rows, explicit `t`).
- `verify_totp`: current code True; wrong code False; code from
  `window_steps` away True; beyond window False.
- `new_totp_secret`: 32-char base32; two calls differ.
- `otpauth_uri`: exact format; username with spaces/`@` is URL-encoded.
- `hash_password`/`verify_password`: roundtrip True; wrong password False;
  tampered stored string (flip a char in hash hex) False; malformed stored
  string False (no exception).

`tests/test_auth_bootstrap.py` (tmp_path fixtures, invokes `python -m` via
`subprocess` with env `PYTHONPATH` pointing at the repo, or calls `main()`
directly with `sys.argv` monkeypatched — either is fine, assert on exit code
and stdout):
- bootstrap with no creds file and no auth.json → exit 1, clear message.
- bootstrap with creds file → creates auth.json (`created`), 2FA off,
  defaults, mode 0600.
- bootstrap with existing auth.json → exit 0, `exists`, file untouched
  (modify it first, assert unchanged).

`tests/test_auth_store.py` (tmp_path fixtures):
- `create_bootstrap_auth` creates file with defaults; second call returns
  `"exists"` and does not overwrite a modified file.
- `load_auth` on missing file → `AuthError`; invalid JSON → `AuthError`;
  missing/renamed key → `AuthError`; valid file roundtrip.
- `save_auth` produces mode 0600.
- `verify_login` correct/wrong; `is_totp_required` reflects schema.
- `should_reauth`: interval 0 → always False; just-under threshold False;
  at threshold True.
- `lockout_status`: before lockout (False, 0); during (True, seconds > 0);
  expired (False, 0).

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
container: `docker compose exec streamlit python /app/scripts/manage_auth.py`
→ verify QR prints with ANSI half-blocks and the scan + code validation loop
closes.

## 13. Locked decisions (traceability — do not reopen)

- Single user; no multi-tenant; no data isolation.
- Bootstrap user/password from Ansible vault (fixed password, user's
  responsibility). No interactive prompts in Ansible.
- 2FA setup/reset strictly via SSH script; QR rendered in terminal
  (`qrencode -t ANSIUTF8`); `otpauth://` URI printed as fallback.
- Re-auth: TOTP-only, every `reauth_interval_hours` (default 24, 0 = off).
- Lockout: 5 failed attempts → 15 min, per session (accepted limitation;
  TOTP is the real barrier).
- fail2ban: Caddy 401 jail removed (Streamlit never returns 401); sshd jail
  enabled instead.
- No new Python dependencies (stdlib + `qrencode` system binary).
- Caddy keeps TLS/no-cache headers; `basic_auth` removed.

## 14. Sequencing & commits

TDD order (each step green before the next):

1. `src/totp.py` + `tests/test_totp.py`
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
- **Per-session lockout** can be bypassed with fresh sessions — accepted;
  TOTP is the actual protection.
- **Accidental commit of secrets** — `.gitignore` must gain `data/auth.json`
  (password hash + TOTP secret) and `data/.auth_creds` (plaintext password)
  **in the same commit** as the auth modules. Currently only `data/*.db` and
  `data/app.log` are ignored.
