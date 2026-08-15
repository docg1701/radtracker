# App-Level Authentication — Implementation Record

Status: **implemented and deployed** (branch `feat/app-auth`). Decisions live in
`docs/meta-prompt.md`; module docs in `docs/context.md`. This file keeps the
remaining research/planning notes relevant to future phases.

## What was built

Username + scrypt password + optional TOTP 2FA replacing Caddy BasicAuth:

- `src/auth_crypto.py` — scrypt (`scrypt$n$r$p$salt$hash`), RFC 6238 TOTP
  (window ±1, SHA1), `otpauth://` URI, HMAC-SHA256 session tokens.
- `src/auth_store.py` — `data/auth.json` (gitignored, atomic 0600 writes, versioned
  schema), gate helpers, idempotent bootstrap.
- `src/cookies.py` — one-way CCv2 cookie components (reader publishes once per
  server session; writer never publishes) + signed session-cookie helpers.
- `src/ui/login.py` — gate (restore → login form → TOTP step), sidebar header/footer,
  logout. 30-day session; password change rotates `session_secret`, username change
  invalidates.
- `scripts/manage_auth.py` / `radtracker-auth` — SSH CLI: activate/disable 2FA with
  terminal QR (`qrencode`), password, username, status, repair.
- Ansible: vault-secured `auth_username`/`auth_password`, bootstrap step, sshd
  fail2ban jail (Caddy 401 jail removed with BasicAuth), Docker `qrencode`.

## Key trade-offs (why)

- **Signed cookie instead of per-session lockout/re-auth**: F5 re-login and session
  locks were rejected as hostile to the single human user; the cookie expiry IS the
  re-auth interval.
- **No app-level rate limiting**: TOTP is the anti-robot barrier. Cloudflare
  free-tier rate limit is planned for the final domain.
- **One-way cookie components**: the extras CookieManager republished its snapshot
  on every cookie change, causing rerun races.
- **TOTP secret never touches the web**: setup/reset is SSH-only (terminal QR).

## Future phases (research notes)

- **Production cutover** (Oracle `radtracker.duckdns.org`): deploy.yml with internet
  mode; validate before switching. VPS dev already validated end-to-end.
- **Cloudflare free tier** (final domain): rate limiting at the edge, DNS, TLS.
- **2FA activation** on the LAN VPS: `radtracker-auth` option 1 with the owner's
  phone (QR).
- **Vault/SSH credential rotation**: the vault password and VPS password shared
  during bootstrap should be rotated.
