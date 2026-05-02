# Code Context — Deploy Key Collision Bug

## Files Retrieved

1. **`ansible/playbooks/deploy.yml`** (lines 56–93) — **Primary target for the fix.** Generates SSH key, reads public key, registers with GitHub API, and clones repo. Contains the hardcoded `title: "radtracker-vps"` that causes collisions.
2. **`ansible/playbooks/update.yml`** (lines 7–13) — Uses the same deploy key for git updates. No API registration, no title issue here.
3. **`ansible/playbooks/cleanup.yml`** (lines 76–85) — Removes deploy key files during cleanup.
4. **`ansible/group_vars/all.yml`** (lines 28–45) — Variables for `deploy_key_path`, `github_pat`, `github_repo`.
5. **`ansible/inventory.yml`** (lines 1–5) — Single host `radtracker_vps`. No `ansible_hostname` or host-specific vars currently.
6. **`docs/deploy-key-collision.txt`** (lines 1–16) — Written description of the bug and the proposed fix.
7. **`docs/deployment.md`** (lines 220–260) — Troubleshooting section referencing the same bug (manual workaround listed).
8. **`docs/context.md`** (lines 619–665) — Architecture docs describing the deploy key system.
9. **`ansible/ansible.cfg`** (line 10) — Confirms `ForwardAgent` removed; deploy key is the sole auth method.
10. **`ansible/requirements.yml`** (lines 1–4) — Collections: `community.docker`, `community.crypto`.

---

## Key Code

### The bug: hardcoded title in `deploy.yml` (line 77)

```yaml
    - name: Register deploy key with GitHub
      ansible.builtin.uri:
        url: "https://api.github.com/repos/docg1701/radtracker/keys"
        method: POST
        headers:
          Authorization: "Bearer {{ github_pat }}"
          Accept: "application/vnd.github+json"
        body:
          title: "radtracker-vps"          # <--- HARDCODED — collides on second VPS
          key: "{{ pubkey_content.content | b64decode }}"
          read_only: true
        body_format: json
        status_code: [201, 422]             # 422 means "already exists" — silently accepted
      register: deploy_key_result
      no_log: true
      become: false
      changed_when: deploy_key_result.status == 201
```

**The problem:** When a second VPS runs the same playbook, it generates a *new* SSH key pair, tries to register it with the same title `"radtracker-vps"`, gets HTTP 422 (title already exists), and treats it as OK — but the registered public key belongs to the *first* VPS. The second VPS's private key doesn't match, so `git clone` fails with authentication error.

### The proposed fix (from `docs/deploy-key-collision.txt`)

```yaml
        body:
          title: "radtracker-vps-{{ inventory_hostname }}"
```

This generates unique titles like `radtracker-vps-radtracker_vps` per host, avoiding the GitHub API collision.

### SSH key generation (deploy.yml, lines 56–59)

```yaml
    - name: Generate deploy key for GitHub access
      community.crypto.openssh_keypair:
        path: "{{ deploy_key_path }}"
        type: ed25519
        comment: "radtracker-deploy"
      become: false
```

Key path: `{{ deploy_key_path }}` → `/home/{{ ansible_user }}/.ssh/radtracker_deploy`.

### Variables (group_vars/all.yml)

```yaml
deploy_key_path: "/home/{{ ansible_user }}/.ssh/radtracker_deploy"
github_repo: git@github.com:docg1701/radtracker.git
github_branch: master
github_pat: !vault |          # Vault-encrypted PAT with 'repo' scope
```

### Inventory (inventory.yml)

```yaml
all:
  hosts:
    radtracker_vps:
      ansible_host: "{{ lookup('env', 'VPS_HOST') }}"
      ansible_user: "{{ lookup('env', 'VPS_USER') | default('ubuntu') }}"
```

Single host. `{{ inventory_hostname }}` would resolve to `radtracker_vps`.

### Git operations using deploy key (deploy.yml lines 85–93, update.yml lines 7–13)

```yaml
    - name: Clone or update repository via deploy key
      ansible.builtin.git:
        repo: "{{ github_repo }}"
        dest: "{{ radtracker_dir }}"
        version: "{{ github_branch }}"
        key_file: "{{ deploy_key_path }}"
        accept_hostkey: true
        force: true
        update: true
      become: false
```

---

## Architecture

1. **Bootstrapping flow (deploy.yml):**
   - Install prerequisites (git, Docker, etc.)
   - Generate ed25519 SSH keypair on VPS → `~/.ssh/radtracker_deploy` + `.pub`
   - Read public key via `slurp`
   - Register public key as a GitHub deploy key via REST API (POST `/repos/.../keys`)
   - Clone/update repo using the deploy key (`key_file` in git module)
   - Build Docker images, start containers, health check

2. **Update flow (update.yml):**
   - Pull latest code via deploy key (same `key_file`)
   - Re-template config files
   - Rebuild and restart containers

3. **Cleanup (cleanup.yml):**
   - Removes `{{ deploy_key_path }}` and `{{ deploy_key_path }}.pub`

4. **Deploy key lifecycle:**
   - PAT (`github_pat`) is used **only** for the initial API registration
   - After registration, PAT can expire — git operations use SSH key auth only
   - The SSH key is generated *on the VPS* during `deploy.yml` — never stored in the repo

---

## Start Here

Open **`ansible/playbooks/deploy.yml`** (line 77). That's the single line that needs to change:

```yaml
title: "radtracker-vps-{{ inventory_hostname }}"
```

This is a one-line fix. No other files need changes.

---

## Risks & Constraints

| Risk | Mitigation |
|------|------------|
| `inventory_hostname` contains dots or special chars | GitHub API accepts any string ≤ 255 chars. Use `{{ inventory_hostname \| regex_replace('[^a-zA-Z0-9_-]', '_') }}` if concerned. |
| Existing keys named `"radtracker-vps"` on GitHub orphaned | They'll remain but won't be overwritten. Each VPS registers its own unique title. Old keys can be manually cleaned from repo Settings > Deploy keys. |
| `ansible_hostname` vs `inventory_hostname` | `inventory_hostname` is the inventory alias (`radtracker_vps`). `ansible_hostname` is the host's actual hostname (collected via facts). Either works; the doc example uses `inventory_hostname`. |
| Second deploy on existing VPS gets a new title | The `changed_when: deploy_key_result.status == 201` handles idempotency — if the key with that title exists, it returns 422 and no change. But if the SSH key was regenerated (e.g., `cleanup.yml` was run but the old GitHub key wasn't manually deleted), the new private key won't match the old registered public key. See troubleshooting in `docs/deployment.md`. |
