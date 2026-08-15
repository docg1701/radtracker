# radtracker — AGENTS.md

Personal productivity dashboard for teleradiology.
Streamlit + SQLite + Plotly.

## Documentation map

**Always read `docs/meta-prompt.md` first** — it contains the project context: tech stack,
hard constraints, session state, validation commands, and resolved decisions.

| File | When |
|------|------|
| `README.md` | Setup, usage, directory structure |
| `docs/context.md` | Module map, data flow, auth flow |
| `docs/deployment.md` | Ansible deployment guide |
| `docs/DESIGN.md` | Cal.com design system reference |

Documentation rule: keep docs lean — only what keeps the project sane and research
relevant to future phases. No file counts, no version pins (pyproject.toml is the
single source), no duplicated facts across docs.

---

## Deployment & auth critical facts

- **LAN VPS update ALWAYS needs `-e deployment_mode=lan -e github_branch=<branch>`.**
  Without `deployment_mode=lan` the playbook switches the VPS to internet mode and
  Caddy tries ACME for the production domain. Never run update.yml without both vars.
- **`RADTRACKER_MODE` follows `deployment_mode`** (ansible `.env` template):
  `lan` → sidebar shows `local`; internet → `web`. No hardcode.
- **Version lives only in `pyproject.toml`** — sidebar reads it at runtime (tomllib).
  Never pin versions in docs; bump = `pyproject.toml` + `uv lock` only.
- **Auth state:** `data/auth.json` (gitignored, single user), stdlib crypto only;
  managed via SSH `radtracker-auth` (scripts/manage_auth.py). 2FA state is re-read
  every run. No app-level rate limiting (TOTP is the anti-robot barrier).
- **UX conventions:** "Radtracker" capitalized in all user-visible strings, code
  identifiers lowercase; PT-BR UI; Material icons only, no emojis as icons;
  Sair button = main tab row right-aligned (`st.space("stretch")`), natural width;
  Salvar = secondary style (no primary fill).

---

## Toolchain

Always use **uv** for package management. Never use raw `pip`.

```bash
uv sync                          # install dependencies
uv add <package>                 # add runtime dependency
uv add --dev <package>           # add dev dependency
uv run streamlit run app.py      # run the app
uv run pytest tests/ -v          # run tests
```

Dependencies must be added to `pyproject.toml` via `uv add` — commit both `pyproject.toml`
and `uv.lock`. Never install a package without recording it. The `requirements.txt` is
stale; `pyproject.toml` is authoritative.

---

## Available skills

Invoke these skills when relevant (they provide specialized instructions):

| Skill | When to use |
|-------|------------|
| `find-docs` | Look up current API/docs for Streamlit, Plotly, Pandas, SQLAlchemy, httpx |
| `developing-with-streamlit` | Any Streamlit task — widgets, theming, components, charts |
| `ansible-automation` | Deployment tasks, playbooks, inventory, Jinja2 templates |

Local references (read before relevant tasks):

- `docs/streamlit_pro_tips.md` — 25+ best practices from Streamlit's co-founder
- Sem streamlit-extras — `st.balloons()` (celebração), `st.expander` (raw-data toggles),
  estrelas via markdown; cookies usam CCv2 próprio (`src/cookies.py`)

---

## Code quality

### Future linters

No pending linters. `sqlfluff` foi descartado: não há arquivos `.sql` no repo —
todo o SQL vive embutido em strings Python (`src/db.py`) e é coberto por testes.

### Quality gate

Run everything below before declaring any task done — all tools must pass, not
just Python ones. `hadolint` is installed at `~/.local/bin/hadolint` (on PATH).

```bash
uv run pytest tests/ -q
uv run ruff check src/ app.py scripts/ tests/
uv run mypy src/
hadolint Dockerfile
uv run yamllint ansible/ .github/ docker-compose.yml
actionlint .github/workflows/ci.yml
markdownlint '**/*.md'
```

Ansible changes additionally require `ansible-lint ansible/`.

---

## Testing

### TDD cycle

1. **Red** — Write a failing test using the existing fixtures
2. **Green** — Write the minimum code to pass
3. **Refactor** — Clean up, run the full suite

### Test infrastructure (use these, don't reinvent)

| Resource | Location | When to use |
|----------|----------|------------|
| `FakeConnection` | `tests/conftest.py` | Tests for DB-dependent functions — SQLite `:memory:`, zero Streamlit dependency |
| `conn` fixture | `tests/conftest.py` | Connection with full schema initialized |
| `default_prices` fixture | `tests/conftest.py` | Default price dictionary |
| `@respx.mock` | `tests/test_llm_client.py` | HTTP call tests (OpenRouter) |
| `_make_stats()` factory | `tests/test_insights.py` | Build stats dicts for insights tests |

### Rules

- **New public function → test.** Add to the matching `tests/test_*.py` file.
- **Bug fix → regression test first.** Reproduce the bug in a test, then fix.
- **Mock only external dependencies** (HTTP, filesystem). Never mock internal logic.
- **Test behavior, not implementation.** Assert on outputs, not internal calls.
- **Descriptive test names:** `test_<function>_<scenario>_<expected_outcome>`.

---

## Releases

### CI workflow

Push a **tag** to trigger it: `.github/workflows/ci.yml`

1. Runs `pytest` on Python 3.12 + 3.13, lints the Dockerfile with `hadolint`,
   and lints Markdown with `markdownlint`.
2. If tests pass **and** the pushed ref is a tag matching `v*.*.*`, the `release` job
   auto-generates a GitHub Release with grouped changelog (feat/fix/chore) from the
   commits since the previous tag.

### Release checklist

After merging/committing to master:

```bash
# 1. Bump version in pyproject.toml
uv lock   # syncs uv.lock
# 2. Commit: "chore: bump version X.Y.Z -> X.Y.Z+1"
# 3. Push to master

# 4. Create annotated tag (first line becomes release subtitle, rest is body)
git tag -a vX.Y.Z <commit-hash> -m "vX.Y.Z: one-line summary" \
    -m "Longer description. Bug fixes, features, breaking changes."

# 5. Push the tag — this triggers CI
   git push --tags
```

Then wait for the GitHub Actions run on the tag. If CI passes, the release
appears automatically at <https://github.com/docg1701/radtracker/releases>.

### Changelog grouping

CI groups commits into **Added** (`feat:`), **Fixed** (`fix:`), and **Changed**
(everything else: `chore:`, `docs:`, `ci:`, `refactor:`, `test:`). Use
conventional commit prefixes consistently.
