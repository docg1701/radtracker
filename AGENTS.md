# radtracker — AGENTS.md

Personal productivity dashboard for teleradiology.
Streamlit + SQLite + Plotly.

## Documentation map

**Always read `docs/meta-prompt.md` first** — it contains the full project context: tech stack,
database schema, session state, hard constraints, validation commands, style conventions,
color palette, business constants, and stop/ask rules.

Use these when you need more depth:

| File | When |
|------|------|
| `README.md` | Setup, usage, directory structure |
| `docs/context.md` | Exhaustive module-by-module detail, data flow |
| `docs/deployment.md` | Ansible deployment guide |
| `docs/DESIGN.md` | Cal.com design system reference |

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
- `docs/streamlit_extras_guide.md` — Catalog of 56 streamlit-extras components

---

## Code quality

### Future linters

The following linters should be configured as the project gains those file types:

| Format | Tool | Status |
|--------|------|--------|
| YAML (Ansible, compose, CI) | `yamllint` | Not yet configured |
| Markdown (docs, README) | `markdownlint-cli` | Not yet configured |
| SQL | `sqlfluff` | Not yet configured |
| Dockerfile | `hadolint` | Not yet configured |

### Quality gate

Run all configured linters + tests before declaring any task done. See
`docs/meta-prompt.md` § "Validation" for current commands.

As each linter above is added, it must be included in the quality gate — all tools
must pass, not just Python ones.

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

## Implementation tracking

Use `docs/deployment.md` for deployment workflow. For feature work, create tracking
checklists inline in the relevant issue or PR.
