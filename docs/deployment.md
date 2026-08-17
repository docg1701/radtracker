# Deployment Guide — radtracker

## Prerequisites

- Clean VPS running **Debian 12+ or Ubuntu 22.04+**
- SSH access as a regular user with `sudo`
- GitHub Personal Access Token (classic) with the `repo` scope
- Domain with an A record pointing to the VPS IP (internet mode)
- IP or hostname reachable on the local network (LAN mode)

## File layout

```text
ansible/
├── ansible.cfg                  # Pipelining, host key check disabled
├── inventory.yml                # VPS_HOST + VPS_USER via env vars
├── requirements.yml             # community.docker + community.crypto collections
├── group_vars/
│   └── all.yml                  # Shared variables (sensitive values Vault-encrypted)
├── templates/
│   ├── Caddyfile.j2             # Caddy template (LAN or internet)
│   └── .env.j2                  # .env template (DOMAIN + TZ)
└── playbooks/
    ├── deploy.yml               # Idempotent bootstrap + deploy
    ├── update.yml               # Update without data loss
    ├── health.yml               # Health check
    ├── backup.yml               # SQLite backup
    └── cleanup.yml              # Full VPS reset
```

## 1. One-time configuration

### 1.1 Secrets (Ansible Vault encrypt_string)

Sensitive values (`deployment_mode`, `auth_username`, `auth_password`,
`github_pat`) are encrypted directly in `all.yml` using
`ansible-vault encrypt_string`:

```bash
# Encrypt a value (the vault password file lives at ansible/.vault_pass)
printf '%s' "lan" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name deployment_mode

printf '%s' "galvani" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name auth_username

printf '%s' "WEB_LOGIN_PASSWORD" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name auth_password

printf '%s' "ghp_YOUR_TOKEN_HERE" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name github_pat
# Paste each output (!vault | ...) into all.yml
```

`auth_username`/`auth_password` are the **web login** credentials of radtracker
(created by the bootstrap on first deploy — minimum 8 characters).

`all.yml` looks like this (sensitive values encrypted, everything else plaintext):

```yaml
---
radtracker_dir: "/home/{{ ansible_user }}/radtracker"
deployment_mode: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
auth_username: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
auth_password: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
github_pat: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
deploy_key_path: "/home/{{ ansible_user }}/.ssh/radtracker_deploy"
```

**Note:** `all.yml` can be committed — only the `!vault` values are encrypted.

To edit encrypted values:

```bash
ansible-vault edit --vault-password-file ansible/.vault_pass ansible/group_vars/all.yml
```

### 1.2 Create the GitHub access token (PAT)

The PAT is used exactly once: to register the VPS SSH key as a deploy key.

1. Go to [GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Name: `radtracker-deploy`
4. Expiration: per your policy (90 days recommended)
5. Scope: **repo** (private repository access + deploy key management)
6. Copy the generated token (e.g. `ghp_xxxx`)
7. Encrypt it:

   ```bash
   ansible-vault encrypt_string "ghp_xxxx" --name github_pat
   ```

8. Replace the `github_pat: !vault |` block in `all.yml` with the output

**Note:** After the deploy key is registered, the PAT can expire without impact —
git auth switches to the SSH key.

### 1.3 Web login password

The web login password is **not hashed manually** — the bootstrap runs
`hashlib.scrypt` the first time the container starts (`python -m src.auth_bootstrap`,
invoked by `deploy.yml`). The vault `auth_password` is the plaintext password;
minimum 8 characters. To change it later, use `radtracker-auth` option 3 (see §4).

### 1.4 Internet mode — domain

In `all.yml`, edit the encrypted `deployment_mode` value:

```yaml
deployment_mode: !vault | ...  # encrypted value = "internet"
```

And edit `all.yml`:

```yaml
domain: radtracker.drgalvanimd.com
```

DNS/Cloudflare setup for the production domain is covered in §8.

### 1.5 Environment

```bash
export VPS_HOST=129.151.4.89         # VPS IP (Oracle Cloud Free Tier)
export VPS_USER=ubuntu               # SSH user
```

### 1.6 Vault password file

Create a file with the Ansible Vault password (already in `.gitignore`):

```bash
echo -n "your_vault_password" > ansible/.vault_pass
chmod 600 ansible/.vault_pass
```

This avoids the interactive password prompt in every command below.

## 2. Initial deploy

```bash
# Install collections (once)
ansible-galaxy collection install -r ansible/requirements.yml

# Deploy (--vault-password-file avoids the interactive prompt)
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --vault-password-file ansible/.vault_pass
```

The playbook runs in order:

1. Installs base packages (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`, `python3-requests`)
2. Adds the Docker repository (Ubuntu or Debian, auto-detected)
3. Installs Docker Engine + Compose plugin
4. Generates an ed25519 SSH key on the VPS and registers it as a GitHub deploy key (uses the vault `github_pat`)
5. Creates persistent directories (`data/`, `backups/`, `caddy_logs/`)
6. Fetches templates from the VPS clone, renders `Caddyfile` and `.env` from them
7. Fixes permissions (`chown 1000:1000` on `data/`)
8. Installs and configures fail2ban (local network whitelist + sshd jail)
9. Builds the image and starts the containers (`docker compose up --build`)
10. Waits for the Streamlit health check
11. Runs the auth bootstrap in the container (creates `data/auth.json` from the vault credentials)
12. Installs the `/usr/local/bin/radtracker-auth` SSH wrapper
13. Prints the access URL + a reminder to enable 2FA

**The deploy is idempotent** — safe to run as many times as you want. The
bootstrap **never overwrites** an existing `auth.json` (change password/2FA
via `radtracker-auth`).

> ⚠️ **Auth cutover:** this deploy removes Caddy BasicAuth.
> Always use `deploy.yml` (never `update.yml`) on the first run after the change —
> `update.yml` does not run the bootstrap nor create the wrapper. Once `auth.json`
> exists, `update.yml` is safe again.

## 3. Verification

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml --vault-password-file ansible/.vault_pass
```

Checks:

- `radtracker` container: exists, running, healthy
- Streamlit endpoint: `/_stcore/health` → 200
- `caddy` container: exists, running
- Caddy serving: Radtracker login page (no more BasicAuth 401)
- fail2ban: active

## 4. Access

**Oracle Cloud Free Tier (production):**

```text
https://radtracker.drgalvanimd.com
```

(Let's Encrypt certificate at the origin; Cloudflare proxy in front — see §8)

Shape: VM.Standard.E2.1.Micro — 1 AMD OCPU, 1 GB RAM, 50 GB boot
Domain: radtracker.drgalvanimd.com → 129.151.4.89 (Cloudflare-proxied)

**Local VPS (LAN):**

```text
https://10.10.10.209
```

(HTTPS with a self-signed certificate — accept the security warning on first
access; Caddy redirects HTTP→HTTPS automatically)

**Internet mode (with your own domain):**

```text
https://radtracker.example.com
```

### Authentication (web login + 2FA)

First access asks for username and password (defined in the vault, §1.1).
Without 2FA, an amber warning appears in the app. To enable 2FA:

```bash
ssh galvani@10.10.10.209    # (or the production host)
radtracker-auth             # wrapper for the management menu
# Option 1: Enable / reconfigure 2FA — scan the QR with your phone and enter the code
```

Full `radtracker-auth` menu:

| Option | Action |
|--------|--------|
| 1 | Enable / reconfigure 2FA (terminal QR + URI fallback; generates a NEW secret on every run — re-scan the QR) |
| 2 | Disable 2FA |
| 3 | Change password (ends all web sessions) |
| 4 | Change username (ends all web sessions) |
| 5 | Web session (days, 1–365) — changing it rotates the secret and ends all sessions immediately |
| 6 | Repair `auth.json` |
| 7 | Status (2FA, TOTP, session, file — never shows secrets) |
| 8 | Language / Idioma (EN) — CLI language, stored separately from the web UX language |
| 0 | Exit |

- The web session lasts 30 days by default (signed cookie), configurable via
  option 5; changing the password, username or duration revokes all sessions.
- `auth.json` is not part of the backups (only `telerrad.db`) — if `data/` is
  lost, re-initialize with option 6 or a redeploy.
- **Enable 2FA immediately after every deploy**: until then the app relies
  only on the password, with no network-level attempt limiting.

## 5. Updating

```bash
# Local VPS (LAN) — BOTH overrides are MANDATORY here:
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
  --vault-password-file ansible/.vault_pass \
  -e deployment_mode=lan -e github_branch=<branch>

# Production (vault internet mode) — no deployment_mode override:
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
  --vault-password-file ansible/.vault_pass -e github_branch=<branch>
```

**Production flow (Oracle), in order:**

```bash
# 1. ALWAYS back up before updating
ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml --vault-password-file ansible/.vault_pass
# copy the backup from the VPS to the repository (gitignored):
scp ubuntu@129.151.4.89:~/radtracker/backups/radtracker-*.db backups/

# 2. Update
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
  --vault-password-file ansible/.vault_pass -e github_branch=master

# 3. Verify
ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml --vault-password-file ansible/.vault_pass
```

- Updates the repository via the SSH deploy key (`git` module) on the given branch
- Re-renders `Caddyfile` and `.env` from the VPS clone templates
  (without `deployment_mode=lan`, a LAN VPS switches to internet mode and
  Caddy tries ACME for the production domain)
- `RADTRACKER_MODE` in `.env` follows `deployment_mode`: lan → `local`, internet → `web` (sidebar footer)
- Rebuilds the image and recreates the container
- Waits for the health check

**Playbook interrupted?** Re-run the SAME command — the playbooks are idempotent
(e.g. the auth bootstrap only creates `auth.json` if missing). Never fix the
server by hand; a re-run repairs any partial state.

**Data preserved:** the `data/` bind mount is never touched. SQLite survives updates.

## 6. Backup

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml --vault-password-file ansible/.vault_pass
```

- Creates a `.backup` inside the container with `sqlite3`
- Copies it to the host under `backups/`
- Verifies integrity with `PRAGMA integrity_check`
- Rotates old backups (>30 days)

## 7. Cleanup

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/cleanup.yml --vault-password-file ansible/.vault_pass
```

- Stops and removes containers
- Docker prune (images, volumes, networks, build cache)
- Removes Docker (packages, GPG key, APT repository)
- Removes fail2ban (sshd jail, package)
- Removes the `/usr/local/bin/radtracker-auth` wrapper
- Removes the project directory
- Removes prerequisites (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`, `python3-requests`)

## 8. Cloudflare (production)

The production domain `radtracker.drgalvanimd.com` is managed by Cloudflare
(`drgalvanimd.com` zone). This is the only network-level brute-force protection
on the login — **never disable the proxy nor remove the rate-limiting rule**.

### 8.1 DNS record

- Type `A`, name `radtracker`, IPv4 `129.151.4.89` (Oracle IP), TTL Auto,
  **Proxy: Proxied** (orange cloud — required for rate limiting).
- Zone SSL/TLS: **Full (strict)**. The origin (Caddy) has its own Let's
  Encrypt certificate issued via HTTP-01 through the proxy; Flexible breaks
  the flow (Caddy loops on HTTP→HTTPS redirects).

### 8.2 Rate limiting (WAF → Rate limiting rules)

Single rule covering the whole login:

| Field | Value |
|-------|-------|
| Name | `radtracker-login` |
| Expression | `http.host eq "radtracker.drgalvanimd.com" and http.request.method eq "POST" and http.request.uri.path eq "/"` |
| Limit | 10 requests / 10 seconds |
| Action | Block (10 seconds) |

> On the Free plan, period and block duration are **fixed at 10 seconds** —
> larger values require a paid plan. The rule throttles brute-force bursts;
> spaced-out attempts are contained by scrypt + TOTP.

Why this expression: the Streamlit login form and TOTP step are the only
`POST` requests to `/` — the authenticated app runs over a single websocket
(`GET /_stcore/stream`), which the rule does not count. It blocks brute force
against the password and TOTP code without touching legitimate sessions.

### 8.3 Logs behind the proxy

Caddy sees the Cloudflare edge IP (not the client) — the real IP arrives in
the `Cf-Connecting-Ip` header. Current fail2ban only covers the sshd jail, so
there is no impact; if an HTTP jail is added someday, filter by that header,
not by the connection's source IP.

## Troubleshooting

### Deploy key fails to register on GitHub

If the deploy fails at the "Register deploy key with GitHub" task:

```bash
# 1. Check that github_pat is valid (not expired)
ansible-vault view ansible/group_vars/all.yml --vault-password-file ansible/.vault_pass | grep github_pat

# 2. Test the PAT manually:
curl -H "Authorization: Bearer YOUR_PAT" https://api.github.com/repos/docg1701/radtracker/keys

# 3. If the PAT expired, generate a new one at https://github.com/settings/tokens
#    and re-encrypt:
ansible-vault encrypt_string "ghp_NEW_TOKEN" --name github_pat
#    Replace the block in all.yml

# 4. If the key exists but is corrupted, remove it manually:
#    Go to https://github.com/docg1701/radtracker/settings/keys
#    Delete "radtracker-vps-<IP>" (or any obsolete radtracker-vps-* key) and re-run deploy.yml
#    Each VPS registers its own key with a unique name based on ansible_host (the VPS IP)

# 5. To force-regenerate the SSH key on the VPS:
ssh galvani@VPS "rm ~/.ssh/radtracker_deploy*"
# Re-run deploy.yml — the openssh_keypair task recreates the key
```

### fail2ban won't start

```bash
sudo tail -50 /var/log/fail2ban.log
sudo fail2ban-client status sshd   # the active jail is sshd (journald)
```

### Docker won't install (Debian)

The playbook uses `signed-by=/etc/apt/keyrings/docker.asc` (the modern method).
Works on Debian 12+ and Ubuntu 22.04+. No `apt-key` dependency (removed in Debian 13).

### Port 80/443 already in use

```bash
sudo lsof -i :80
sudo lsof -i :443
sudo systemctl stop nginx apache2   # stop conflicting servers
```

### Let's Encrypt fails (internet mode)

- Check DNS: `dig +short radtracker.example.com` must return the VPS IP
- Wait for propagation (1–10 minutes)
- Test with the staging CA before production:

  ```caddy
  tls {
      ca https://acme-staging-v02.api.letsencrypt.org/directory
  }
  ```

### Wrong password / password reset

```bash
# Connect via SSH and use the management menu:
radtracker-auth
# Option 3: Change password (minimum 8 characters, ends all web sessions)
# Option 6: Repair auth.json (if the file is missing/corrupted)
```

Re-running `deploy.yml` does **not** change the password — the bootstrap is
idempotent and never overwrites an existing `auth.json`.
