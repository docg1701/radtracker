# Implementation Plan

## Goal
Eliminate local file dependency in Ansible playbooks so templates are read from the VPS clone (`{{ radtracker_dir }}/ansible/templates/`) instead of the control node. Any machine with Ansible + vault password can deploy, and the VPS always uses the latest template versions from GitHub.

## Strategy
Use `ansible.builtin.fetch` to pull templates from the VPS clone to a local temp directory, then use the standard `ansible.builtin.template` module with the fetched copies. Clean up temp files afterward. This guarantees the templates match what's on the VPS (which was just cloned from GitHub).

## Tasks

1. **Create local temp directory for fetched templates**
   - File: `ansible/playbooks/deploy.yml`
   - Changes: Add a task after "Clone or update repository via deploy key" that creates `/tmp/radtracker_fetched_templates/` on localhost via `delegate_to: localhost` with `run_once: true`
   - Acceptance: Directory exists before fetch tasks run

2. **Fetch templates from VPS clone to local temp**
   - File: `ansible/playbooks/deploy.yml`
   - Changes: Replace the two `ansible.builtin.template` tasks (lines 110–117) with:
     a. `ansible.builtin.fetch` loop pulling `Caddyfile.j2` and `.env.j2` from `{{ radtracker_dir }}/ansible/templates/` to `/tmp/radtracker_fetched_templates/` with `flat: true`
     b. Two `ansible.builtin.template` tasks using `/tmp/radtracker_fetched_templates/Caddyfile.j2` and `/tmp/radtracker_fetched_templates/.env.j2` as `src`
   - Acceptance: Caddyfile and .env are generated from templates sourced from VPS clone

3. **Clean up local temp files after templating**
   - File: `ansible/playbooks/deploy.yml`
   - Changes: Add a task after templating to remove `/tmp/radtracker_fetched_templates/` on localhost via `delegate_to: localhost` with `run_once: true`
   - Acceptance: No leftover temp files after playbook completes

4. **Apply same pattern to update.yml**
   - File: `ansible/playbooks/update.yml`
   - Changes: Same three-task pattern (create temp dir → fetch → template → cleanup) after "Update repository via deploy key", replacing the two existing `ansible.builtin.template` tasks (lines 20–29)
   - Acceptance: Updates work identically but templates come from VPS clone

5. **Remove ansible-lint exception**
   - File: `.ansible-lint.yml`
   - Changes: Remove the `no-relative-paths` entry from `skip_list` (line 4)
   - Acceptance: `ansible-lint` passes without the exception since we no longer use `{{ playbook_dir }}/../` paths

6. **Update deployment documentation**
   - File: `docs/deployment.md`
   - Changes: Under §2 "Deploy inicial" and §5 "Atualização", update step 6 description from "Gera `Caddyfile` e `.env` a partir dos templates" to reflect that templates are now read from the VPS clone
   - Also update the "Estrutura de arquivos" ASCII diagram if it still mentions local template dependency
   - Acceptance: Docs accurately describe the new flow

## Files to Modify

- `ansible/playbooks/deploy.yml` — Replace two `template` tasks with fetch+template+cleanup sequence
- `ansible/playbooks/update.yml` — Same replacement
- `.ansible-lint.yml` — Remove `no-relative-paths` from skip_list
- `docs/deployment.md` — Update step descriptions in §2 and §5

## New Files
None.

## Detailed Task Specifications

### deploy.yml changes

**Insert after the "Clone or update repository via deploy key" task (~line 98):**

```yaml
    - name: Create local temp directory for fetched templates
      ansible.builtin.file:
        path: "/tmp/radtracker_fetched_templates"
        state: directory
        mode: "0755"
      delegate_to: localhost
      run_once: true
```

**Replace the two template tasks (lines 109–117):**

Before:
```yaml
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
```

After:
```yaml
    - name: Fetch templates from VPS clone
      ansible.builtin.fetch:
        src: "{{ radtracker_dir }}/ansible/templates/{{ item }}"
        dest: "/tmp/radtracker_fetched_templates/{{ item }}"
        flat: true
      loop:
        - Caddyfile.j2
        - .env.j2
      become: false

    - name: Template Caddyfile from fetched copy
      ansible.builtin.template:
        src: "/tmp/radtracker_fetched_templates/Caddyfile.j2"
        dest: "{{ radtracker_dir }}/Caddyfile"
        mode: "0644"

    - name: Template .env from fetched copy
      ansible.builtin.template:
        src: "/tmp/radtracker_fetched_templates/.env.j2"
        dest: "{{ radtracker_dir }}/.env"
        mode: "0600"

    - name: Clean up local temp files
      ansible.builtin.file:
        path: "/tmp/radtracker_fetched_templates"
        state: absent
      delegate_to: localhost
      run_once: true
```

### update.yml changes

**Insert before the template tasks (after "Update repository via deploy key", ~line 18):**

```yaml
    - name: Create local temp directory for fetched templates
      ansible.builtin.file:
        path: "/tmp/radtracker_fetched_templates"
        state: directory
        mode: "0755"
      delegate_to: localhost
      run_once: true
```

**Replace lines 19–29 (existing template tasks) with same pattern as deploy.yml:**

```yaml
    - name: Fetch templates from VPS clone
      ansible.builtin.fetch:
        src: "{{ radtracker_dir }}/ansible/templates/{{ item }}"
        dest: "/tmp/radtracker_fetched_templates/{{ item }}"
        flat: true
      loop:
        - Caddyfile.j2
        - .env.j2
      become: false

    - name: Template Caddyfile from fetched copy
      ansible.builtin.template:
        src: "/tmp/radtracker_fetched_templates/Caddyfile.j2"
        dest: "{{ radtracker_dir }}/Caddyfile"
        mode: "0644"

    - name: Template .env from fetched copy
      ansible.builtin.template:
        src: "/tmp/radtracker_fetched_templates/.env.j2"
        dest: "{{ radtracker_dir }}/.env"
        mode: "0600"

    - name: Clean up local temp files
      ansible.builtin.file:
        path: "/tmp/radtracker_fetched_templates"
        state: absent
      delegate_to: localhost
      run_once: true
```

### .ansible-lint.yml changes

Remove this line from `skip_list`:
```yaml
  - no-relative-paths    # Template src paths use {{ playbook_dir }}/../templates/ — intentional
```

The `ignore-errors` and `command-instead-of-module` entries remain unchanged.

### docs/deployment.md changes

In §2 "Deploy inicial", update item 6:
- Before: `6. Gera `Caddyfile` e `.env` a partir dos templates`
- After: `6. Busca templates do clone VPS, gera `Caddyfile` e `.env` a partir deles`

In §5 "Atualização", update:
- Before: `- Regenera `Caddyfile` e `.env``
- After: `- Regenera `Caddyfile` e `.env` a partir dos templates do clone VPS`

## Dependencies

- Task 1 must complete before Task 2 (fetch needs the temp directory)
- Task 3 must complete after template tasks
- Tasks 1–3 (deploy.yml) and Task 4 (update.yml) are independent of each other
- Task 5 (.ansible-lint.yml) can be done anytime
- Task 6 (docs) should be done last to capture the final state

## Risks

1. **`fetch` module and `flat: true` behavior**: The `fetch` module with `flat: true` writes directly to the specified `dest` file path. The parent directory must exist (handled by the temp dir creation task). If the loop runs for multiple items and dest paths differ only by filename, each fetch targets a different file — no collision. Verified by Ansible docs.

2. **`become: false` on fetch**: The VPS clone is under `{{ ansible_user }}` home directory (not root). The `fetch` task uses `become: false` to read as the normal user, matching the git clone task's privilege level. Template tasks (writing to `{{ radtracker_dir }}`) keep `become: true` (inherited from playbook level) since they write config files that may need root.

3. **`delegate_to: localhost` and connection plugins**: Tasks delegated to localhost use the local connection by default. The `file` module (for temp dir and cleanup) and `template` module both work fine with local connection. The `ansible.builtin.template` tasks themselves do NOT use `delegate_to` — they run on the remote host normally (template module reads `src` locally on control node, but the task itself executes in the remote context for writing `dest`).

4. **Multiple hosts edge case**: If the inventory ever targets multiple VPS hosts, `run_once: true` on the temp dir creation and cleanup ensures we don't race on the shared local temp directory. The `fetch` task without `run_once` runs per-host, which is correct — each VPS may have a slightly different clone state.

5. **Cleanup on failure**: If the playbook fails between fetch and cleanup, `/tmp/radtracker_fetched_templates/` lingers on the control node. This is acceptable — `/tmp` is ephemeral and the directory is tiny (two small text files). A second run will recreate and re-clean it.

6. **Validation**: After implementation, run the full ansible-lint gate:
   ```bash
   uv run ansible-lint ansible/playbooks/deploy.yml ansible/playbooks/update.yml
   ```
   Confirm it passes without the `no-relative-paths` exception.
