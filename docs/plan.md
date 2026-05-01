# Implementation Plan — radtracker v1.1.0

## Tracking

| Phase | Task | Worker | Review | Done |
|-------|------|--------|--------|------|
| 1     | Dockerfile + .dockerignore | — | — | ⬜ |
| 1     | Caddyfile | — | — | ⬜ |
| 1     | docker-compose.yml + .env.example | — | — | ⬜ |
| 2     | Ansible skeleton (cfg, inventory, group_vars) | — | — | ⬜ |
| 2     | Templates + deploy.yml | — | — | ⬜ |
| 2     | update.yml, health.yml, backup.yml, cleanup.yml | — | — | ⬜ |
| 2     | Integration test (full cycle) | — | — | ⬜ |
| 3     | Verify app for Docker (config.toml, paths) | — | — | ⬜ |
| 4     | Code quality tooling (yamllint, hadolint, ansible-lint) | — | — | ⬜ |
| 4     | docs/deployment.md | — | — | ⬜ |
| 4     | Update .gitignore + README.md | — | — | ⬜ |
| 5     | Full VPS validation (both modes) | — | — | ⬜ |
| 5     | Deployment-specific tests | — | — | ⬜ |
| 5     | Commit, tag v1.1.0, push | — | — | ⬜ |
| 5     | GitHub Release v1.1.0 | — | — | ⬜ |

### Test VPS

| Field | Value |
|-------|-------|
| Hostname | `vps9-radtracker` |
| FQDN | `vps9-radtracker.local` |
| IP | `10.10.10.209` |
| OS | Debian 13 (trixie) |
| User | `galvani` (sudoer) |
| Access | SSH key (`ssh galvani@10.10.10.209`) |
| Mode | LAN (HTTP, no TLS) |

```bash
export VPS_HOST=10.10.10.209
export VPS_USER=galvani
```

---

## Goal

Transform radtracker from a local-only Streamlit app into a self-hosted Docker application deployable to any VPS via SSH using Ansible. The stack: Streamlit in Docker (built from source, no registry push) → Caddy reverse proxy with BasicAuth + Let's Encrypt → SQLite persisted via bind-mount → fail2ban brute-force protection → Ansible for all lifecycle operations. Works both on the internet (with domain + HTTPS) and on a local network (HTTP + IP/hostname).

---

## 0. Implementation Reference

During implementation, use these skills for current, authoritative guidance:

| Skill | When to use |
|-------|-------------|
| `skill:ansible-automation` | Writing/modifying any Ansible playbook, role, inventory, or config |
| `skill:developing-with-streamlit` | Any Streamlit code changes, config, or debugging |
| `skill:find-docs` | Verifying current API versions, syntax, or best practices for any technology |

---

## 1. Architecture Overview

```
Browser (HTTPS or HTTP)
  │
  ▼
Caddy (v2.9) ─── BasicAuth ─── Let's Encrypt (internet) / plain HTTP (LAN)
  │  │
  │  └── Logs auth failures → fail2ban (bans after 5 failures/10min)
  │
  ▼
Streamlit container (port 8501, internal only)
  │
  ▼
SQLite DB (/app/data/telerrad.db → bind-mounted from host /home/user/radtracker/data)
```

### Two deployment modes

| Mode | Domain | TLS | Caddy config |
|------|--------|-----|--------------|
| **Internet** | `radtracker.example.com` | Let's Encrypt (auto) | `radtracker.example.com { basicauth ... reverse_proxy ... }` |
| **LAN** | none (IP:port) | none (plain HTTP) | `:80 { basicauth ... reverse_proxy ... }` |

The Caddyfile template uses the `deployment_mode` variable. When `lan`, Caddy listens on `:80` with HTTP only (no TLS). When `internet`, it uses the domain with automatic Let's Encrypt.

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| Caddy over Traefik/Nginx | HTTPS automático sem config, Caddyfile de 6 linhas, sem Docker socket, sem escaping de `$`, ~30 MB RAM |
| Image built from source (not pushed to registry) | Simplicidade: código no GitHub (privado), build local no VPS via `docker compose build` |
| Source fetched via `git clone` (SSH agent forwarding) | Sem registry, sem rsync; autenticação via chave SSH do dev |
| HTTP mode for LAN | Sem domínio não há como obter certificado; HTTP puro na rede local é aceitável com BasicAuth |
| BasicAuth no Caddy (não streamlit-authenticator) | Zero código Python, uma diretiva no Caddyfile |
| sqlite3 `.backup` (not Litestream) | Adequate for single-user dashboard; cron-based simplicity |
| Single `docker-compose.yml` (not Swarm/K8s) | Single VPS, no orchestration complexity needed |
| Non-root user in container (UID 1000) | Security best practice; bind-mount ownership matches |
| fail2ban no host | Proteção contra brute-force no BasicAuth |
| `.env` file for secrets (not Ansible Vault) | Simplicity; `.env` is `.gitignore`'d and templated from `.env.example` |
| uv for Python package management | Project standard; `uv pip install` for Docker builds |
| VPS user is regular user with sudo (never root) | Security; `become: true` in playbooks for privileged operations |

---

## 2. Files to Create

### 2.1 Docker

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: builder installs deps → runtime copies venv, runs as non-root |
| `.dockerignore` | Exclude .env, .git, data/, venv, caches from build context and final image |
| `Caddyfile` | Reverse proxy config: domain (internet) or `:80` (LAN), basicauth, reverse_proxy to Streamlit |
| `docker-compose.yml` | Caddy + Streamlit services, volumes, healthchecks |
| `.env.example` | Template for deployment secrets (DOMAIN, BASICAUTH_USERS) |

### 2.2 Ansible

| File | Purpose |
|------|---------|
| `ansible/ansible.cfg` | Ansible config: host_key_checking=false, pipelining=true |
| `ansible/inventory.yml` | Single host definition; user is a regular sudoer, never root |
| `ansible/group_vars/all.yml` | Shared variables (paths, domain, mode, repo, secrets, backup retention) |
| `ansible/playbooks/deploy.yml` | Clone repo, install Docker + fail2ban, build image, start containers |
| `ansible/playbooks/update.yml` | Git pull, rebuild image, recreate container only, wait for health |
| `ansible/playbooks/health.yml` | Verify container running, health endpoint responds, assert state, fail2ban check |
| `ansible/playbooks/backup.yml` | `.backup` inside container, copy to host, integrity check, rotate |
| `ansible/playbooks/cleanup.yml` | Stop containers, prune Docker, apt autoremove — preserve `data/` |
| `ansible/templates/Caddyfile.j2` | Jinja2 template for Caddyfile (supports internet + LAN) |
| `ansible/templates/.env.j2` | Jinja2 template for the `.env` file from Ansible vars |

### 2.3 Scripts

*No build/push scripts needed.* The Docker image is built directly from source on the VPS via `docker compose build`. No registry push required.

### 2.4 Documentation

| File | Purpose |
|------|---------|
| `docs/deployment.md` | Step-by-step VPS deployment guide in Brazilian Portuguese (internet + LAN modes) |

---

## 3. Files to Modify

| File | Change |
|------|--------|
| `.gitignore` | Add `/backups/`, `/caddy_data/`, `/caddy_config/`, `/caddy_logs/`, `data/*.db`, `.env` |
| `.dockerignore` | (NEW) Exclude secrets, git, data, caches from Docker build context |
| `pyproject.toml` | Add dev dependency group: `yamllint`, optional `ansible-lint` (pip-installable) |
| `README.md` | Add deployment section |
| `.streamlit/config.toml` | Verify `gatherUsageStats = false` (already present). No changes needed. |
| `app.py` | Path verified — no changes expected. |

---

## 4. Docker Implementation

### 4.1 `Dockerfile`

Multi-stage build with `python:3.12-slim`. Requires `.dockerignore` (see §4.1b).

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install uv for fast, reproducible dependency resolution
RUN pip install uv

# ── Production dependencies (sync with pyproject.toml) ──
RUN uv pip install \
    "streamlit>=1.54.0,<2.0.0" \
    "pandas>=2.0.0" \
    "numpy>=1.24.0" \
    "plotly>=5.18.0" \
    "httpx>=0.27.0" \
    "sqlalchemy>=2.0.0" \
    "streamlit-extras>=1.5.0"

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 1000 streamlit
USER streamlit
WORKDIR /app

COPY --chown=streamlit:streamlit . .

RUN mkdir -p /app/data

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0"]
```

Key points:
- `sqlite3` included in runtime for `.backup` command
- `--chown` on COPY ensures non-root owns all files; `.dockerignore` prevents secrets/caches from entering the image
- `mkdir -p /app/data` for bind-mount target with correct permissions
- HEALTHCHECK uses Streamlit's built-in `/_stcore/health` endpoint

### 4.1b `.dockerignore`

```dockerignore
# Secrets — NEVER copy into the image
.env

# Git — huge, not needed at runtime
.git/
.gitignore

# Data — bind-mounted at runtime, must not be baked in
data/

# Lock files (not needed at runtime)
uv.lock

# Python artifacts
__pycache__/
*.pyc
*.pyo
.venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/

# Dev/test artifacts
temp/
tests/
docs/
.coverage
htmlcov/

# Deployment files (not needed inside the app container)
docker-compose.yml
Caddyfile
.env.example
.streamlit/secrets.toml
ansible/
scripts/

# OS/IDE
.DS_Store
.vscode/
.idea/
*.swp
```

### 4.2 `Caddyfile`

```caddy
{$DOMAIN:localhost} {
    log {
        output file /var/log/caddy/access.log {
            format console
        }
    }
    basicauth * {
        {$BASICAUTH_USERS}
    }
    reverse_proxy streamlit:8501
}
```

Key points:
- `format console` outputs human-readable text (not JSON) so fail2ban can parse the log
- `{$DOMAIN}`: when set to a real domain → Caddy auto-provisions Let's Encrypt; when `localhost` → plain HTTP
- `{$BASICAUTH_USERS}`: variable from `.env`, format `"user hash"` (space-separated, no colon)
- `basicauth *` protege toda a aplicação
- `reverse_proxy` já lida com WebSockets automaticamente
- Let's Encrypt é **zero config** — Caddy provisiona e renova certificados sozinho

### 4.3 `docker-compose.yml`

```yaml
services:
  caddy:
    image: caddy:2.9-alpine
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "./Caddyfile:/etc/caddy/Caddyfile:ro"
      - "./caddy_data:/data"
      - "./caddy_config:/config"
      - "./caddy_logs:/var/log/caddy"
    env_file:
      - .env
    networks:
      - radtracker

  streamlit:
    build: .
    container_name: radtracker
    restart: unless-stopped
    ports:
      - "127.0.0.1:8501:8501"   # loopback only — health checks, never exposed externally
    volumes:
      - "./data:/app/data"
    networks:
      - radtracker
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"

networks:
  radtracker:
    driver: bridge
```

Key points:
- **Nada de Docker socket** — Caddy não precisa, segurança muito maior
- **Nada de labels YAML** — configuração está no Caddyfile, mais limpo
- `streamlit` uses `build: .` — image is built from source on the VPS; no registry needed
- `streamlit` port `127.0.0.1:8501:8501` — loopback only, for Ansible health checks; never exposed to internet
- `caddy_logs` bind-mount para o fail2ban ler os logs de acesso
- `env_file: .env` para Caddy ler `$DOMAIN` e `$BASICAUTH_USERS`

### 4.4 `.env.example`

```bash
# Domain — set to a real domain for internet mode, or leave default for LAN
# LAN mode: Caddy listens on :80 with plain HTTP
# Internet mode: Caddy auto-provisions Let's Encrypt certificate
DOMAIN=localhost

# BasicAuth users: generate hash with:
#   docker run --rm caddy:2.9-alpine caddy hash-password --plaintext "yourpassword"
# Format: "username hash" (space-separated, NO colon, NO $ escaping needed)
BASICAUTH_USERS=admin $2a$14$examplehashhere
```

---

## 5. Ansible Implementation

### Workflow: Configure once, run many times

1. **Edit configuration files once:** `inventory.yml`, `group_vars/all.yml`
2. **Ensure SSH agent is running** (for GitHub clone via `git@`): `ssh-add -l`
3. **Run any playbook** as many times as needed — all idempotent

### 5.1 `ansible/ansible.cfg`

```ini
[defaults]
host_key_checking = false
pipelining = true
stdout_callback = yaml
inventory = inventory.yml

[ssh_connection]
pipelining = true
ssh_args = -o ForwardAgent=yes
```

Setting `ssh_args = -o ForwardAgent=yes` in `ansible.cfg` avoids needing `--ssh-extra-args` on every command.

### 5.2 `ansible/inventory.yml`

```yaml
all:
  hosts:
    radtracker_vps:
      ansible_host: "{{ lookup('env', 'VPS_HOST') }}"
      ansible_user: "{{ lookup('env', 'VPS_USER') | default('ubuntu') }}"
```

Uses env vars `VPS_HOST` and `VPS_USER` (default: `ubuntu` — common cloud image default).
The VPS user is always a regular user with sudo; never root. Playbooks use `become: true` for privileged operations.

### 5.3 `ansible/group_vars/all.yml`

```yaml
---
# Project root on VPS (in the ansible_user's home directory)
radtracker_dir: "/home/{{ ansible_user }}/radtracker"
radtracker_data_dir: "{{ radtracker_dir }}/data"
radtracker_backup_dir: "{{ radtracker_dir }}/backups"

# Deployment mode: "internet" or "lan"
deployment_mode: internet

# Domain (only used in internet mode)
domain: radtracker.example.com

# GitHub private repository (SSH URL for agent-forwarding auth)
github_repo: git@github.com:docg1701/radtracker.git
github_branch: master

# BasicAuth: generate with: docker run --rm caddy:2.9-alpine caddy hash-password --plaintext "password"
# Format: "username bcrypt_hash" (space-separated)
basicauth_users: "admin $2a$14$examplehashhere"

# Backup retention (days)
backup_retention_days: 30
```

This file should be edited once per deployment with actual domain, repo URL, and hash values.

### 5.4 `ansible/templates/Caddyfile.j2`

```jinja2
{% if deployment_mode == "lan" %}
:80 {
{% else %}
{{ domain }} {
{% endif %}
    log {
        output file /var/log/caddy/access.log {
            format console
        }
    }
    basicauth * {
        {{ basicauth_users }}
    }
    reverse_proxy streamlit:8501
}
```

### 5.5 `ansible/templates/.env.j2`

```jinja2
{% if deployment_mode == "lan" %}
DOMAIN=:80
{% else %}
DOMAIN={{ domain }}
{% endif %}
BASICAUTH_USERS={{ basicauth_users }}
```

All variables are defined in `group_vars/all.yml`. No extra vars needed.

### 5.6 Playbook: `deploy.yml`

Bootstrap + deploy in one idempotent playbook. Safe to run on a fresh VPS or to redeploy.

```yaml
---
- name: Deploy radtracker to VPS
  hosts: all
  become: true
  gather_facts: true

  tasks:
    - name: Install prerequisites
      ansible.builtin.apt:
        name:
          - ca-certificates
          - curl
          - gnupg
          - lsb-release
          - git
        state: present
        update_cache: true

    - name: Add Docker GPG key
      ansible.builtin.apt_key:
        url: https://download.docker.com/linux/ubuntu/gpg
        state: present

    - name: Add Docker repository (Ubuntu/Debian)
      ansible.builtin.apt_repository:
        repo: "deb [arch=amd64] https://download.docker.com/linux/{{ ansible_distribution | lower }} {{ ansible_distribution_release }} stable"
        state: present

    - name: Install Docker
      ansible.builtin.apt:
        name:
          - docker-ce
          - docker-ce-cli
          - containerd.io
          - docker-buildx-plugin
          - docker-compose-plugin
        state: present

    - name: Ensure Docker is running
      ansible.builtin.systemd:
        name: docker
        state: started
        enabled: true

    - name: Clone or pull repository
      ansible.builtin.git:
        repo: "{{ github_repo }}"
        dest: "{{ radtracker_dir }}"
        version: "{{ github_branch }}"
        update: true
        accept_hostkey: true
        force: true

    - name: Create persistent directories (preserved across deploys)
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        mode: "0755"
      loop:
        - "{{ radtracker_data_dir }}"
        - "{{ radtracker_backup_dir }}"
        - "{{ radtracker_dir }}/caddy_logs"

    - name: Template Caddyfile
      ansible.builtin.template:
        src: "{{ playbook_dir }}/../templates/Caddyfile.j2"
        dest: "{{ radtracker_dir }}/Caddyfile"
        mode: "0644"

    - name: Template .env file
      ansible.builtin.template:
        src: "{{ playbook_dir }}/../templates/.env.j2"
        dest: "{{ radtracker_dir }}/.env"
        mode: "0600"

    - name: Ensure data directory has correct ownership (uid 1000)
      ansible.builtin.file:
        path: "{{ radtracker_data_dir }}"
        owner: 1000
        group: 1000
        recurse: true

    - name: Install and configure fail2ban
      block:
        - name: Install fail2ban
          ansible.builtin.apt:
            name: fail2ban
            state: present

        - name: Create fail2ban filter for Caddy BasicAuth failures
          ansible.builtin.copy:
            content: |
              [Definition]
              failregex = .*"remote_ip":"<HOST>".*"status":401
              ignoreregex =
            dest: /etc/fail2ban/filter.d/radtracker-caddy.conf
            mode: "0644"

        - name: Create radtracker jail
          ansible.builtin.copy:
            content: |
              [radtracker-caddy]
              enabled = true
              port = http,https
              filter = radtracker-caddy
              logpath = {{ radtracker_dir }}/caddy_logs/access.log
              maxretry = 5
              findtime = 600
              bantime = 3600
            dest: /etc/fail2ban/jail.d/radtracker.conf
            mode: "0644"

        - name: Ensure fail2ban is running
          ansible.builtin.systemd:
            name: fail2ban
            state: restarted
            enabled: true

    - name: Build images and start containers
      community.docker.docker_compose_v2:
        project_src: "{{ radtracker_dir }}"
        state: present
        build: always
        pull: true

    - name: Wait for Streamlit to become healthy
      ansible.builtin.uri:
        url: "http://localhost:8501/_stcore/health"
        status_code: 200
      register: health
      until: health.status == 200
      retries: 15
      delay: 5

    - name: Deployment complete
      ansible.builtin.debug:
        msg: >
          radtracker deployed!
          {% if deployment_mode == "lan" %}
          Access at http://{{ ansible_default_ipv4.address | default('localhost') }}
          {% else %}
          Access at https://{{ domain }}
          {% endif %}
```

**Dependency:** Requires `community.docker` collection (`ansible-galaxy collection install community.docker`).

**SSH agent setup:** The `ansible.cfg` includes `ssh_args = -o ForwardAgent=yes`, so no extra flags needed. Ensure your SSH key is loaded:
```bash
ssh-add -l          # check if key is loaded
ssh-add ~/.ssh/id_ed25519  # load if not
```

### 5.7 Playbook: `update.yml`

Pulls latest source, rebuilds image, recreates container. Data never touched.

```yaml
---
- name: Update radtracker without data loss
  hosts: all
  become: true

  tasks:
    - name: Pull latest source from repository
      ansible.builtin.git:
        repo: "{{ github_repo }}"
        dest: "{{ radtracker_dir }}"
        version: "{{ github_branch }}"
        update: true
        force: true

    - name: Template latest Caddyfile
      ansible.builtin.template:
        src: "{{ playbook_dir }}/../templates/Caddyfile.j2"
        dest: "{{ radtracker_dir }}/Caddyfile"
        mode: "0644"

    - name: Template latest .env
      ansible.builtin.template:
        src: "{{ playbook_dir }}/../templates/.env.j2"
        dest: "{{ radtracker_dir }}/.env"
        mode: "0600"

    - name: Rebuild image and recreate containers
      community.docker.docker_compose_v2:
        project_src: "{{ radtracker_dir }}"
        state: present
        build: always
        pull: true
        remove_orphans: true

    - name: Wait for Streamlit to become healthy
      ansible.builtin.uri:
        url: "http://localhost:8501/_stcore/health"
        status_code: 200
      register: health
      until: health.status == 200
      retries: 15
      delay: 5

    - name: Update complete
      ansible.builtin.debug:
        msg: "radtracker updated successfully"
```

**Why no data loss:** The bind-mount volume `./data:/app/data` is NOT touched during container recreation. Only the container image is rebuilt. `docker compose up -d` with `build: always` rebuilds the image and recreates only containers whose config/image changed.

### 5.8 Playbook: `health.yml`

```yaml
---
- name: Check radtracker health
  hosts: all
  become: true

  tasks:
    - name: Get container info
      community.docker.docker_container_info:
        name: radtracker
      register: container

    - name: Assert container exists
      ansible.builtin.assert:
        that: container.exists
        fail_msg: "Container 'radtracker' does not exist"
        success_msg: "Container exists"

    - name: Assert container is running
      ansible.builtin.assert:
        that: container.container.State.Status == "running"
        fail_msg: "Container is NOT running (state: {{ container.container.State.Status }})"
        success_msg: "Container is running"

    - name: Assert container is healthy
      ansible.builtin.assert:
        that: container.container.State.Health.Status == "healthy"
        fail_msg: "Health check FAILED (status: {{ container.container.State.Health.Status }})"
        success_msg: "Health check passed"

    - name: Check Streamlit health endpoint (bypasses Caddy via localhost:8501)
      ansible.builtin.uri:
        url: "http://localhost:8501/_stcore/health"
        status_code: 200
      register: endpoint

    - name: Assert endpoint responds
      ansible.builtin.assert:
        that: endpoint.status == 200
        fail_msg: "Endpoint returned {{ endpoint.status }}"
        success_msg: "Endpoint healthy"

    - name: Check fail2ban is running
      ansible.builtin.systemd:
        name: fail2ban
      register: fail2ban_status

    - name: Assert fail2ban active
      ansible.builtin.assert:
        that: fail2ban_status.status.ActiveState == "active"
        fail_msg: "fail2ban is not running"
        success_msg: "fail2ban is active"
```

### 5.9 Playbook: `backup.yml`

```yaml
---
- name: Backup radtracker SQLite database
  hosts: all
  become: true

  vars:
    backup_timestamp: "{{ ansible_date_time.date }}_{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}"
    backup_filename: "radtracker-{{ backup_timestamp }}.db"
    backup_path: "{{ radtracker_backup_dir }}/{{ backup_filename }}"

  tasks:
    - name: Ensure backup directory exists
      ansible.builtin.file:
        path: "{{ radtracker_backup_dir }}"
        state: directory
        mode: "0755"

    - name: Create backup inside container
      ansible.builtin.command:
        cmd: >
          docker exec radtracker sqlite3 /app/data/telerrad.db
          ".backup /tmp/{{ backup_filename }}"
      changed_when: true

    - name: Copy backup to host
      ansible.builtin.command:
        cmd: >
          docker cp radtracker:/tmp/{{ backup_filename }}
          {{ backup_path }}
      changed_when: true

    - name: Clean up temp file inside container
      ansible.builtin.command:
        cmd: docker exec radtracker rm /tmp/{{ backup_filename }}
      changed_when: false

    - name: Verify backup integrity
      ansible.builtin.command:
        cmd: sqlite3 {{ backup_path }} "PRAGMA integrity_check;"
      register: integrity
      changed_when: false

    - name: Assert backup is valid
      ansible.builtin.assert:
        that: "'ok' in integrity.stdout"
        fail_msg: "Backup CORRUPTED: {{ backup_path }}"
        success_msg: "Backup integrity OK: {{ backup_filename }}"

    - name: Rotate old backups
      ansible.builtin.shell: |
        find {{ radtracker_backup_dir }} -name "*.db" -mtime +{{ backup_retention_days }} -delete
      changed_when: false

    - name: Get backup size
      ansible.builtin.stat:
        path: "{{ backup_path }}"
      register: backup_stat

    - name: Backup complete
      ansible.builtin.debug:
        msg: >
          Backup saved to {{ backup_path }}
          ({{ (backup_stat.stat.size / 1024) | round(1) | int }} KB)
```

### 5.10 Playbook: `cleanup.yml`

```yaml
---
- name: Cleanup radtracker from VPS
  hosts: all
  become: true

  tasks:
    - name: Stop and remove radtracker containers
      community.docker.docker_compose_v2:
        project_src: "{{ radtracker_dir }}"
        state: absent
        remove_orphans: true
      ignore_errors: true

    - name: Prune unused Docker objects
      community.docker.docker_prune:
        containers: true
        images: true
        networks: true
        builder_cache: true

    - name: Stop and disable fail2ban radtracker jail
      ansible.builtin.file:
        path: /etc/fail2ban/jail.d/radtracker.conf
        state: absent

    - name: Restart fail2ban
      ansible.builtin.systemd:
        name: fail2ban
        state: restarted
      ignore_errors: true

    - name: System package cleanup
      ansible.builtin.apt:
        autoremove: true
        autoclean: true

    - name: Verify data directory preserved
      ansible.builtin.stat:
        path: "{{ radtracker_data_dir }}"
      register: data_dir_stat

    - name: Confirm data is safe
      ansible.builtin.debug:
        msg: "Data directory preserved at {{ radtracker_data_dir }}"
      when: data_dir_stat.stat.exists
```

**Important:** This playbook does NOT delete the `data/` subdirectory — the SQLite database survives cleanup.

---

## 6. Authentication + Security

### Approach: Caddy BasicAuth + fail2ban

**Why this over alternatives:**

| Option | Verdict | Reason |
|--------|---------|--------|
| Caddy BasicAuth | ✅ Chosen | Zero code changes, uma diretiva no Caddyfile, HTTPS automático, sem escaping |
| Traefik BasicAuth | ❌ | Precisa de Docker socket, labels YAML, escaping `$$`, command flags |
| streamlit-authenticator | ❌ | Requires Python code changes, adds dependency, config file to manage |
| Nginx htpasswd | ❌ | Requires nginx config, WebSocket header fix, more config surface |
| OAuth/OIDC (Authelia, Authentik) | ❌ | Too complex, additional services, maintenance burden |
| SaaS (Auth0, Clerk) | ❌ | User explicitly rejected external services/subscriptions |

### Como gerar o hash de senha

```bash
# Usando o próprio Caddy (recomendado):
docker run --rm caddy:2.9-alpine caddy hash-password --plaintext "suasenha"
# Output: $2a$14$...

# O hash usa bcrypt, sem necessidade de ferramenta externa
```

### Formato no .env / Caddyfile

```
# Sintaxe Caddy: "usuário hash" (espaço, não dois-pontos)
BASICAUTH_USERS=admin $2a$14$hashgerado
```

**Nada de escaping `$$`** — diferentemente do Traefik, o Caddy não exige escaping de `$` no docker-compose. O hash bcrypt vai direto.

### Camada extra: fail2ban

O fail2ban monitora o log de acesso do Caddy (`caddy_logs/access.log`) e bloqueia IPs que fazem 5 requisições com erro 401 (BasicAuth falhou) em 10 minutos. O ban dura 1 hora.

```
/etc/fail2ban/filter.d/radtracker-caddy.conf → regex para detectar 401
/etc/fail2ban/jail.d/radtracker.conf          → jail config (maxretry, bantime)
```

Comandos úteis no VPS:
```bash
sudo fail2ban-client status radtracker-caddy   # ver bans ativos
sudo fail2ban-client set radtracker-caddy unbanip <IP>  # desbanir
```

### Caddy + WebSocket compatibility

Caddy's `reverse_proxy` handles WebSocket proxying automatically — the `Upgrade` and `Connection` headers are forwarded transparently. Streamlit's WebSocket-based live reload and widget state work without any special configuration.

---

## 7. Streamlit App Adjustments

### 7.1 Database path verification

Current code in `src/db.py`:
```python
# get_connection() in src/db.py
url="sqlite:///data/telerrad.db"
```

In Docker, `WORKDIR /app`, so `data/telerrad.db` resolves to `/app/data/telerrad.db` — matches the bind-mount target. **No change needed.**

`init_db()` also calls `os.makedirs("data", exist_ok=True)` which creates the directory if missing — this works inside Docker as well.

### 7.2 `.streamlit/config.toml` review

Current config already has `[server] headless = true` and `[browser] gatherUsageStats = false`. Port and address are set via the Dockerfile `ENTRYPOINT` (CLI args override config.toml): `--server.port=8501 --server.address=0.0.0.0`. No config.toml changes needed.

### 7.3 CORS and XSRF

Behind a reverse proxy on the same domain/host, Streamlit's default CORS/XSRF settings work. No changes needed since Caddy proxies on the same domain. If issues arise during testing, add:

```toml
[server]
enableCORS = false
enableXsrfProtection = false
```

But this should NOT be needed with Caddy's same-domain proxy.

### 7.4 Cookie manager verification

`src/cookies.py` uses `streamlit-extras` `cookie_manager`. Behind a reverse proxy:
- Cookies set by Streamlit are scoped to the domain Caddy serves
- The `__Secure-` prefix requires HTTPS — Caddy provides this via Let's Encrypt (internet mode)
- Standard cookies work over HTTP in LAN mode
- No special configuration needed

### 7.5 What does NOT need to change

| Component | Verdict |
|-----------|---------|
| `src/db.py` — CRUD operations | Same SQLite, same code path |
| `src/calculations.py` — Business logic | Pure functions, no path dependency |
| `src/charts.py` / `charts_analysis.py` — Charts | No DB access, data passed as params |
| `src/llm_client.py` — OpenRouter | httpx works inside Docker |
| `src/ui/*` — Tab renderers | No server-dependent logic |
| `src/cookies.py` — Tab persistence | Works behind reverse proxy |
| Test suite (`tests/`) | Uses in-memory SQLite, no Docker dependency |

---

## 8. Build Pipeline

No registry push needed. The image is built directly on the VPS via `docker compose build` as part of the `deploy.yml` and `update.yml` playbooks. Source is fetched from the private GitHub repo via SSH.

### Local development build

```bash
# Build and test locally
docker compose build
docker compose up -d
```

### Versioning

- Git tags (`v1.1.0`) drive releases
- `github_branch` in group_vars controls which branch is deployed (default: `master`)
- No Docker image tags needed (built from source, not published)

---

## 9. Documentation

### 9.1 `docs/deployment.md`

Comprehensive guide in Brazilian Portuguese covering:

1. **Pré-requisitos:** VPS (Ubuntu 22.04/24.04 ou Debian 12/13), domínio com DNS A record (internet) ou acesso IP local (LAN), acesso SSH, chave SSH carregada no agente
2. **Configuração única:** Editar `inventory.yml` e `group_vars/all.yml` com host, domínio, hash da senha, repo URL
3. **Setup SSH:** `ssh-add -l` para verificar chave; `ssh-add ~/.ssh/id_ed25519` para carregar
4. **Gerando a senha:** Como usar `caddy hash-password` para criar o hash bcrypt
5. **Modo internet:** `deployment_mode: internet`, configurar domínio, deploy → acesso HTTPS com Let's Encrypt
6. **Modo LAN:** `deployment_mode: lan`, deploy → acesso HTTP na rede local
7. **Deploy inicial:** `ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml`
8. **Redeploy (idempotente):** mesmo comando — repo atualizado, imagem reconstruída. Dados em `data/` preservados
9. **Atualização:** `ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml`
10. **Backup manual:** `ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml`
11. **Verificação de saúde:** `ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml`
12. **Limpeza completa:** `ansible-playbook -i ansible/inventory.yml ansible/playbooks/cleanup.yml`
13. **Segurança:** Como o fail2ban protege contra brute force, como verificar bans ativos
14. **Solução de problemas:** Falhas comuns e resoluções (clone, SSH agent, portas bloqueadas, DNS)

### 9.2 `README.md` additions

```markdown
## Deploy

radtracker can be deployed to any VPS with Docker + Ansible.
Works both on the internet (HTTPS + domain) and local network (HTTP).

See [docs/deployment.md](docs/deployment.md) for the full guide (in Portuguese).

Stack: Streamlit → Docker → Caddy (BasicAuth + Let's Encrypt) → fail2ban → Ansible
```

---

## 10. Testing Strategy

### 10.1 Local Docker build

```bash
docker build -t radtracker:dev .
docker run -d --name radtracker-test -p 8501:8501 -v $(pwd)/data:/app/data radtracker:dev
curl http://localhost:8501/_stcore/health  # Expected: 200 OK
docker rm -f radtracker-test
```

### 10.2 Docker Compose smoke test (LAN mode)

```bash
cp .env.example .env   # Keep DOMAIN=localhost
docker compose up -d
curl http://localhost:8501/_stcore/health           # Expected: 200
curl -u admin:password http://localhost/_stcore/health  # Expected: 200
curl -I http://localhost/                           # Expected: 401
docker compose down
```

### 10.3 Ansible dry-runs

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --check
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --check -e deployment_mode=lan
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml --check
ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml --check
ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml --check
```

### 10.4 Data persistence test

1. **Deploy** → Access app → Add production data via UI
2. **Run `update.yml`** → Container recreated
3. **Verify** → Production data still present, no loss
4. **Run `backup.yml`** → Backup file appears in `{{ radtracker_backup_dir }}/`
5. **Simulate disaster** → `docker compose down`, delete container, `docker compose up -d`
6. **Verify** → Data intact because `./data` bind-mount was untouched

### 10.5 BasicAuth + fail2ban access control test

```bash
curl -I http://localhost/                               # Expected: 401
curl -u admin:password http://localhost/_stcore/health   # Expected: 200
# Trigger fail2ban (5 bad attempts)
for i in $(seq 1 6); do
  curl -s -o /dev/null -w "%{http_code}\n" -u admin:wrongpass http://localhost/
done
sudo fail2ban-client status radtracker-caddy  # Should show banned IP
```

### 10.6 Code quality checks

```bash
uv run ruff check src/ tests/
uv run mypy src/
yamllint ansible/ docker-compose.yml
docker run --rm -i hadolint/hadolint < Dockerfile
ansible-lint ansible/playbooks/
```

---

## 11. Phase Breakdown

### Phase 1: Docker — 3 tasks

**Task 1:** Create `Dockerfile` and `.dockerignore`
- Files: `Dockerfile`, `.dockerignore`
- Acceptance: `docker build -t radtracker:dev .` succeeds, image < 300 MB, no secrets in image layers

**Task 2:** Create `Caddyfile`
- File: `Caddyfile`
- Acceptance: Syntax valid via `docker run --rm -v $(pwd)/Caddyfile:/etc/caddy/Caddyfile caddy:2.9-alpine caddy validate --config /etc/caddy/Caddyfile`

**Task 3:** Create `docker-compose.yml` and `.env.example`
- Files: `docker-compose.yml`, `.env.example`
- Acceptance: `docker compose up -d` starts both containers, `/_stcore/health` returns 200

### Phase 2: Ansible — 4 tasks

**Task 4:** Create Ansible skeleton
- Files: `ansible/ansible.cfg`, `ansible/inventory.yml`, `ansible/group_vars/all.yml`
- Acceptance: Config is valid; `ansible-inventory --list -i ansible/inventory.yml` outputs correct structure

**Task 5:** Create templates and `deploy.yml`
- Files: `ansible/templates/Caddyfile.j2`, `ansible/templates/.env.j2`, `ansible/playbooks/deploy.yml`
- Acceptance: Both internet and LAN mode deploy a fresh VPS end-to-end

**Task 6:** Create remaining playbooks
- Files: `update.yml`, `health.yml`, `backup.yml`, `cleanup.yml`
- Acceptance: Each playbook passes `ansible-playbook --syntax-check`; completes without errors on target VPS

**Task 7:** Integration test
- Full cycle: deploy → data entry → backup → health check → update → verify data → cleanup
- Acceptance: Data survives update, backup integrity OK, health assertions pass, fail2ban active

### Phase 3: App Adjustments — 1 task

**Task 8:** Verify and adjust app for Docker
- Files: `.streamlit/config.toml`, `app.py` (verify, no changes expected)
- Acceptance: App runs identically in Docker as locally; `uv run pytest tests/ -v` all pass

### Phase 4: Docs + Quality — 3 tasks

**Task 9:** Add code quality tooling
- Update `pyproject.toml` dev dependency group to include: `yamllint`
- Tools:
  - Python: `ruff` (format + lint), `mypy` (type check) — already configured
  - YAML (Ansible, compose): `yamllint` with relaxed config (line-length disabled, Jinja2 templates excluded)
  - Dockerfile: `hadolint` via Docker (`docker run --rm -i hadolint/hadolint < Dockerfile`)
  - Ansible: `ansible-lint` for playbook validation
- Acceptance: All tools run clean

**Task 10:** Create `docs/deployment.md`
- File: `docs/deployment.md`
- Acceptance: Another developer can follow the guide to deploy in both modes

**Task 11:** Update `.gitignore` and `README.md`
- Files: `.gitignore`, `README.md`
- Acceptance: `.env` and caddy/backup dirs are gitignored; README has deploy section

### Phase 5: Testing + Release — 4 tasks

**Task 12:** Full VPS validation
- Deploy to test VPS in both modes, run all playbooks, verify data persistence
- Acceptance: All playbooks pass, app works in browser with BasicAuth, fail2ban bans on brute force

**Task 13:** Add deployment-specific tests
- Tests to cover:
  - docker-compose.yml syntax valid (`docker compose config`)
  - Caddyfile syntax valid (`caddy validate`)
  - Ansible playbook syntax valid (`ansible-playbook --syntax-check`)
  - fail2ban regex matches Caddy console-format 401 lines (test with `fail2ban-regex`)
  - Data persistence: insert data, recreate container, verify data survives
- Acceptance: All deployment tests pass; no regressions in existing test suite

**Task 14:** Commit, tag v1.1.0, push
```bash
git add -A
git commit -m "feat: Docker + Caddy + Ansible deployment for v1.1.0"
git tag -a v1.1.0 -m "v1.1.0: self-hosted deployment with Docker, Caddy, fail2ban, and Ansible"
git push origin master --tags
```

**Task 15:** Create GitHub Release v1.1.0
- Title: `v1.1.0 — Self-Hosted Deployment`
- Body: changelog covering Docker, Caddy, Ansible, fail2ban, dual-mode internet/LAN
- Acceptance: Release page exists at `https://github.com/docg1701/radtracker/releases/tag/v1.1.0`

---

## 12. Dependencies

```
Phase 1 (Docker)
  │
  ├──► Phase 2 (Ansible) — needs Dockerfile + Caddyfile + docker-compose.yml as reference
  │
  ├──► Phase 3 (App adjustments) — independent, can run in parallel
  │
  ├──► Phase 4 (Docs + Quality) — needs Caddyfile/docker-compose, independent of Ansible
  │
  └──► Phase 5 (Testing + Release) — needs all previous phases
```

Phases 2, 3, and 4 can run in parallel after Phase 1 completes.

---

## 13. Risks

| Risk | Mitigation |
|------|------------|
| Caddy + Streamlit WebSocket issue | Caddy's reverse_proxy handles WebSocket by default; test early in Phase 1 |
| UID 1000 mismatch with bind-mount | `deploy.yml` explicitly sets `chown 1000:1000` on data dir; test on Ubuntu 22.04 and 24.04 |
| Git clone fails (private repo, no SSH agent) | `ansible.cfg` has `ForwardAgent=yes`; pre-flight: `ssh-add -l`; fallback: HTTPS + token URL |
| Ports 80/443 blocked by provider | Document in deployment.md; offer LAN-only mode as fallback |
| Let's Encrypt rate limits | Use Caddy's staging CA for testing: `tls { ca https://acme-staging-v02.api.letsencrypt.org/directory }` |
| fail2ban não encontra logs | Deploy.yml cria `caddy_logs/` diretório; logpath usa path absoluto do `radtracker_dir` |
| Cookie session loss after update | Cookies are domain-scoped; verify in Phase 5 |
| Ansible `community.docker` collection version | `docker_compose_v2` module is stable since collection 3.0.0 |
| Docker install fails on Debian vs Ubuntu (different repo paths) | `apt_repository` uses `{{ ansible_distribution \| lower }}` — resolves to `debian` or `ubuntu` automatically |
| Build failure due to Python dependency changes | Dependencies listed explicitly in Dockerfile; multi-stage build isolates venv |
| Backup size grows unbounded | `backup.yml` enforces 30-day rotation |
| LAN mode sem senha forte | Documentar que BasicAuth é obrigatório mesmo em LAN |
| `.dockerignore` missing or incomplete | Verify with `docker history` after build; checklist: `.env`, `data/`, `.git/` excluded |
| DNS A record not propagated | Caddy fails to get TLS cert; wait 1–10 min then run health.yml |
| Docker `COPY . .` includes excluded files | Verify with `docker run --rm radtracker:dev ls -la /app/` |
| ansible-lint errors on first run | Fix incrementally; may flag missing FQCN |
| yamllint false positives on Jinja2 templates | Configure yamllint to skip `ansible/templates/` directory |

---

## 14. Success Criteria

1. `docker compose up -d` starts radtracker + Caddy on local machine
2. `ansible-playbook deploy.yml` provisions a fresh Ubuntu VPS end-to-end in both modes (idempotent)
3. `ansible-playbook update.yml` rebuilds image, recreates container, data intact
4. `ansible-playbook backup.yml` produces a valid `.backup` with passed `PRAGMA integrity_check`
5. `ansible-playbook health.yml` returns all green assertions including fail2ban check
6. `ansible-playbook cleanup.yml` removes everything except the `data/` subdirectory
7. HTTPS access (internet mode) or HTTP access (LAN mode) with BasicAuth working
8. Unauthenticated requests receive 401; authenticated requests pass through
9. fail2ban blocks IP after 5 failed BasicAuth attempts in 10 minutes
10. Existing test suite continues to pass: `uv run pytest tests/ -v`
11. No new Python runtime dependencies beyond what's already in `pyproject.toml`
12. Tag `v1.1.0` created and pushed; GitHub Release published with changelog
13. All code quality checks pass: `ruff`, `mypy`, `yamllint`, `hadolint`, `ansible-lint`
