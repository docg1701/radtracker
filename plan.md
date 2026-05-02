# Implementation Plan — Fix Deploy Key Collision Bug

## Goal

Prevent SSH deploy key collision when multiple VPS instances run the same Ansible playbook, by making each key's GitHub title unique per host (`radtracker-vps-{{ ansible_host }}` instead of the hardcoded `"radtracker-vps"`).

---

## Tasks

### 1. Fix the hardcoded title in `ansible/playbooks/deploy.yml`
   - **File:** `ansible/playbooks/deploy.yml`
   - **Line:** 77
   - **Change:** `title: "radtracker-vps"` → `title: "radtracker-vps-{{ ansible_host }}"`
   - **Result:** Each VPS registers its key with a distinct name tied to its actual hostname/IP (set via `VPS_HOST`). Two VPSes with different IPs get different titles, no collision.
   - **Acceptance:** `grep -F 'title: "radtracker-vps"' ansible/playbooks/deploy.yml` returns nothing (bare string gone). `grep 'ansible_host' ansible/playbooks/deploy.yml` returns the new line.

### 2. Update troubleshooting section in `docs/deployment.md`
   - **File:** `docs/deployment.md`
   - **Line:** 244 (reference to `"radtracker-vps"` in the troubleshooting block)
   - **Change:** Update the instruction "Delete `"radtracker-vps"` e re-rode" to reference the new unique naming scheme. Either:
     - Generalize to: "Delete any stale deploy key named `radtracker-vps-*` on the repo settings page", or
     - Show how to list/delete by the new pattern.
   - **Acceptance:** No stale reference to the old bare title remains.

### 3. Update deploy key documentation in `docs/context.md`
   - **File:** `docs/context.md`
   - **Lines:** Section 11.2 (Git Authentication — Deploy Key) **and all other code blocks referencing the old title** (~lines 31, 42, 48, 51, 134, 146).
   - **Change:** Replace all occurrences of the bare `"radtracker-vps"` with the new `"radtracker-vps-{{ ansible_host }}"` pattern, and explain why the host-based suffix prevents multi-VPS collisions.
   - **Acceptance:** `grep -F '"radtracker-vps"' docs/context.md` returns nothing.

### 4. Add deploy key cleanup to `cleanup.yml` (optional improvement)
   - **File:** `ansible/playbooks/cleanup.yml`
   - **Change:** Add a task (after removing local key files) that deletes the deploy key from GitHub via the API, using `DELETE /repos/docg1701/radtracker/keys/:id`. This requires fetching the key ID by title first (2-step: `GET` to list keys, filter by `title`, then `DELETE` if found).
   - **Note:** This is a nice-to-have and can be deferred. Mark it as `ignore_errors: true` since the PAT may have expired by cleanup time.
   - **Acceptance:** Running `cleanup.yml` removes the GitHub deploy key as well as local files.

### 5. Syntax validation
   - **Command:** `uv run ansible-lint ansible/playbooks/deploy.yml`
   - **Also:** `uv run yamllint ansible/playbooks/deploy.yml`
   - **Acceptance:** Both pass with zero errors after the change.

### 6. Idempotency verification (real run against test repo)
   - **Method:** Run `deploy.yml` for real against a test GitHub repo (or the production repo with a dry-run flag on the URI task).
   - **Why not `--check`:** `openssh_keypair` does not create the key file in check mode (breaks `slurp`), and `uri` does not make real HTTP requests in check mode (status codes unobservable).
   - **What to verify:**
     1. First run on VPS 1: `deploy_key_result.status == 201` → `changed`.
     2. Re-run on VPS 1: `deploy_key_result.status == 422` (key with `{{ ansible_host }}` title already exists) → `ok`.
     3. First run on VPS 2 (different `VPS_HOST` → different `ansible_host`): `201` → `changed`, different title, no collision.
   - **Acceptance:** All three scenarios pass on real infrastructure.

### 7. Manual verification steps
   1. Deploy to VPS 1: `export VPS_HOST=X.X.X.X; ansible-playbook ... deploy.yml`
   2. Visit `https://github.com/docg1701/radtracker/settings/keys` — verify a key named `radtracker-vps-radtracker_vps` exists (or whatever the inventory hostname is).
   3. Deploy to VPS 2 (different `VPS_HOST` → different `ansible_host`): verify a **second** key exists with a different name, and the second VPS can clone the repo.
   4. Re-run deploy on VPS 1: verify the playbook treats 422 as `ok` (idempotent re-run on same host).
   5. Run `update.yml` on both VPSes: verify `git pull` works via the deploy key.

---

## Files to Modify

| File | Line(s) | Change |
|------|---------|--------|
| `ansible/playbooks/deploy.yml` | 77 | `title: "radtracker-vps"` → `title: "radtracker-vps-{{ ansible_host }}"` |
| `docs/deployment.md` | 244 | Update troubleshooting reference from bare `"radtracker-vps"` to the new naming pattern |
| `docs/context.md` | Section 11.2 | Document the hostname-suffixed naming convention and multi-VPS rationale |
| `ansible/playbooks/cleanup.yml` | (after line ~83) | Optionally add GitHub API key deletion task |

## New Files

None.

---

## Dependencies

- Task 1 must be done first (the actual code fix).
- Tasks 2 and 3 (docs) can proceed in parallel after task 1.
- Task 4 (cleanup.yml) is independent — can be done after, or deferred.
- Tasks 5–7 (validation) follow task 1.

---

## Risks

1. **Existing orphaned keys on GitHub** — Before this fix, if a second VPS already deployed (and silently failed auth), there's an orphaned key on GitHub with the old fixed name that corresponds to the **first** VPS only. After applying the fix and re-deploying the second VPS, the old key remains. This is harmless (the second VPS now has its own correctly-named key) but worth cleaning up manually.

2. **`ansible_host` changing** — If a VPS gets a new IP and the deploy is re-run with `VPS_HOST` pointing to the new IP, a new deploy key will be registered with the new title while the old one stays orphaned. This is harmless (the VPS can still clone with its own key) but orphaned keys accumulate. Manual cleanup on GitHub Settings → Deploy keys is recommended.

3. **422 handling remains permissive** — The playbook still treats HTTP 422 as success (`status_code: [201, 422]`). Post-fix this is correct: if the same VPS re-runs the playbook, its uniquely-named key already exists and 422 means "nothing to do." However, if GitHub returns 422 for a *different* reason (malformed key, rate limiting), we'd silently swallow it. This is a pre-existing issue, not introduced by this fix. Consider adding a `failed_when` check in a future PR that inspects the response body for specific error messages.

4. **PAT lifecycle** — If the PAT has expired, the key registration task fails with 401 (not in `status_code`), so it errors out loudly. This is the correct behavior and requires no change.
