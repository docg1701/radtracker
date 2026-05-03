# Implementation Plan

## Goal
Add per-modality `st.color_picker` to the Settings tab, persisting custom colors in the `modalities` table. Default colors (current cool palette) are preserved when the user never touches them. All chart factories use the DB-stored color via an optional parameter — no DB access in chart modules.

---

## Tasks

### 1. Schema migration: add `color` column to `modalities`
- **File**: `src/db.py` — `init_db()` function
- **Changes**:
  - After existing `CREATE TABLE IF NOT EXISTS modalities`, add an `ALTER TABLE` migration that adds `color TEXT NOT NULL DEFAULT '#64748B'` if the column doesn't already exist.
  - Use a try/except around `ALTER TABLE ... ADD COLUMN color TEXT ... DEFAULT '#64748B'` — SQLite will throw if the column exists; that's fine, catch and ignore.
  - Set the default per-modality colors via a follow-up `UPDATE` only for rows where `color IS NULL` or `color = '#64748B'` (one-time backfill from `MODALITY_COLORS` in `chart_colors.py`).
- **Acceptance**: After migration, `SELECT slug, color FROM modalities` returns 11 rows, each with its palette color (e.g. `radiografia` → `#2563EB`).

### 2. Update `_MODALITY_SEED` to include `color`
- **File**: `src/db.py` — the `_MODALITY_SEED` constant
- **Changes**: Add `"color"` key to each of the 11 dicts. Import `MODALITY_COLORS` from `src/chart_colors` and use it to set the value (`m["color"] = MODALITY_COLORS[m["slug"]]`).
- **Acceptance**: Each seed entry has a `color` field matching the current palette.

### 3. Update `_seed_modalities()` to insert `color`
- **File**: `src/db.py` — `_seed_modalities()` function
- **Changes**: In the `INSERT OR IGNORE INTO modalities` statement, add `, color` to the column list and `, :color` to the VALUES list. Pass `color=m["color"]` in the params.
- **Acceptance**: Fresh database init seeds 11 modalities with correct colors.

### 4. Update `load_all_modalities()` to SELECT `color`
- **File**: `src/db.py` — `load_all_modalities()`
- **Changes**: Add `color` to the SELECT clause: `SELECT slug, label, price, exams_per_hour, active, sort_order, color`.
- **Acceptance**: Returned dicts include `"color"` key.

### 5. Update `load_active_modalities()` to SELECT `color`
- **File**: `src/db.py` — `load_active_modalities()`
- **Changes**: Same SELECT change as above: add `color`.
- **Acceptance**: Active modality dicts include `"color"` key.

### 6. Update `save_modality()` to persist `color`
- **File**: `src/db.py` — `save_modality()` function
- **Changes**:
  - Add `color` parameter: `def save_modality(conn, slug, price, exams_per_hour, active, color=None)`.
  - In the UPDATE statement, add `color = :color` only when `color is not None`, otherwise skip it (backward compat for calls that don't pass color, e.g. `seeded_conn` fixture and `_migrate_v1_to_v2()`).
- **Acceptance**: Calling `save_modality(conn, "radiografia", 4.5, 75.0, 1, "#FF0000")` persists the color.

### 7. Update `color_for_modality()` to accept optional lookup
- **File**: `src/chart_colors.py` — `color_for_modality()`
- **Changes**:
  - Add optional parameter: `def color_for_modality(slug: str, modalities: list[dict] | None = None) -> str`.
  - When `modalities` is provided, iterate to find `m["slug"] == slug` and return `m.get("color", "#64748B")`.
  - When `modalities` is None, fall back to `MODALITY_COLORS.get(slug, "#64748B")` (current behavior).
  - Update docstring to show both usage patterns.
- **Acceptance**:
  - `color_for_modality("radiografia")` → `#2563EB` (hardcoded fallback, no param).
  - `color_for_modality("radiografia", [{"slug": "radiografia", "color": "#FF0000"}])` → `#FF0000`.
  - `color_for_modality("desconhecido", [...])` → `#64748B`.

### 8. Update `FakeConnection` schema in tests
- **File**: `tests/conftest.py` — `FakeConnection.__init__()` schema strings
- **Changes**: In the `CREATE TABLE IF NOT EXISTS modalities` string, add `color TEXT NOT NULL DEFAULT '#64748B'` before `sort_order`.
- **Acceptance**: All existing tests using `FakeConnection` still pass (the column is added with a default, existing inserts work).

### 9. Update `active_modalities` fixture
- **File**: `tests/conftest.py` — `active_modalities()` fixture
- **Changes**: Add `"color"` key to each of the 3 dicts, matching the current palette: RM → `#7C3AED`, TC Geral → `#6366F1`, Radiografia → `#2563EB`.
- **Acceptance**: Tests that iterate over `active_modalities` and access `color` work correctly.

### 10. Propagate color lookup to chart factories
- **Files**: `src/charts.py` and `src/charts_analysis.py`
- **For `build_modality_bar()` and `build_modality_donut()`** — these take `(counts, labels_lookup)`:
  - Add optional `modalities: list[dict] | None = None` parameter.
  - Change `color_for_modality(slug)` → `color_for_modality(slug, modalities)`.
- **For `build_monthly_modality_donut()`** — already takes `active_modalities`:
  - Use existing `active_modalities` param for color lookup. Build a slug→color dict at the top of the function from `active_modalities`.
- **For `build_wow_comparison_chart()`, `build_modality_mix_evolution()`, `_single_week_chart()`** — already take `active_modalities`:
  - Use existing `active_modalities` param for color lookup. No new parameter needed.
- **Acceptance**: When `modalities=None` (or `active_modalities` has no `color` key), falls back to hardcoded `MODALITY_COLORS`. When colors are present, uses them.

### 11. Pass modalities list from tab renderers
- **Files**: `src/ui/today.py`
  - Pass `modalities=st.session_state.active_modalities` to `build_modality_bar()`.
- **Files**: `src/ui/month.py`
  - `build_monthly_modality_donut()` already receives `active_mods` (the tab renderer passes `active_modalities=active_mods`). No change needed — it will use them for color lookup per Task 10.
  - `build_progress_gauge()` and `build_monthly_earnings_chart()` — **no change needed**, they don't use modality colors.
- **Files**: `src/ui/analysis.py`
  - `build_wow_comparison_chart()` and `build_modality_mix_evolution()` already receive `active_modalities`. No change needed — they will use them for color lookup per Task 10.
- **Acceptance**: Charts render with colors from DB (or defaults if user never changed them).

### 12. Add `st.color_picker` to settings UI
- **File**: `src/ui/settings.py` — `_render_modality_grid()`
- **Changes**:
  - Change header row columns from `[3, 2, 2, 1]` to `[2.5, 2, 2, 0.8, 0.8]` with a new `"**Cor**"` label (5 columns — color and active squeezed to fit).
  - Change row columns from `[3, 2, 2, 1]` to `[2.5, 2, 2, 0.8, 0.8]`.
  - Between `col_eph` and `col_active`, add `col_color`:
    ```python
    with col_color:
        color = st.color_picker(
            f"Cor {slug}",
            value=str(m.get("color", "#64748B")),
            key=f"mod_color_{slug}",
            label_visibility="collapsed",
        )
    ```
  - Track `color` in the `changed` detection: add `or color != str(m.get("color", "#64748B"))`.
  - Include `color` in the `updated` dict: `updated[slug] = (price, eph, active, color)`.
- **Acceptance**: Color picker appears between Exames/h and Ativo. Default shows current palette color. Changing a color and clicking "Salvar modalidades" persists it.

### 13. Update `_save_modalities()` to pass `color`
- **File**: `src/ui/settings.py` — `_save_modalities()`
- **Changes**:
  - Unpack tuple as `(price, eph, active, color)` instead of `(price, eph, active)`.
  - Pass `color=color` to `save_modality()`.
- **Acceptance**: Saving a color change persists to DB.

### 14. Update `ensure_settings()` to handle `color` in session state
- **File**: `src/ui/settings.py` — `ensure_settings()`
- **Changes**: No changes needed — `load_all_modalities()` and `load_active_modalities()` already return `color` after Task 4/5. The `prices` dict and other state variables don't need color.
- **Acceptance**: `st.session_state.all_modalities[0]` includes `"color"` key.

### 15. Add tests for color functionality
- **File**: `tests/test_chart_colors.py` (extend existing)
- **Changes**:
  - `test_color_for_modality_with_lookup`: verifies lookup param overrides hardcoded.
  - `test_color_for_modality_with_lookup_fallback`: unknown slug in lookup → `#64748B`.
  - `test_color_for_modality_without_lookup_unchanged`: existing tests already cover this.
- **File**: `tests/test_db.py` (extend existing)
- **Changes**:
  - `test_save_modality_with_color`: save with custom color, load back, verify.
  - `test_seed_modalities_has_color`: after seed, every modality has a non-default color.
- **File**: `tests/test_charts.py` (new file)
- **Changes**:
  - `test_build_modality_bar_with_custom_colors`: build bar chart with a modalities list containing custom colors, verify bar marker colors match.
  - `test_build_modality_bar_without_modalities`: build bar chart without modalities param, verify uses hardcoded colors.
- **Acceptance**: All tests pass. `uv run pytest tests/ -v` shows no regression and new tests are green.

### 16. Update `docs/meta-prompt.md`
- **File**: `docs/meta-prompt.md`
- **Changes**:
  - In the "Color palette reference" section, note that colors are now customizable per-modality via Settings.
  - In the "Database Schema" section, add `color` to the `modalities` column list.
  - Add `color` to the `_MODALITY_SEED` reference.
- **Acceptance**: Documentation matches current implementation.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/db.py` | Add `color` column via ALTER TABLE migration; update `_MODALITY_SEED`, `_seed_modalities()`, `load_all_modalities()`, `load_active_modalities()`, `save_modality()` |
| `src/chart_colors.py` | `color_for_modality()` accepts optional `modalities` param |
| `src/charts.py` | 3 functions accept optional `modalities` param |
| `src/charts_analysis.py` | 3 functions (2 public + 1 private) accept optional `modalities` param |
| `src/ui/settings.py` | `_render_modality_grid()` adds color picker column; `_save_modalities()` unpacks color |
| `src/ui/today.py` | Pass `modalities=` to `build_modality_bar()` |
| `src/ui/month.py` | `build_monthly_modality_donut()` already receives `active_mods` — uses them for color per Task 10 |
| `src/ui/analysis.py` | `build_wow_comparison_chart()` and `build_modality_mix_evolution()` already receive `active_modalities` — uses them for color per Task 10 |
| `tests/conftest.py` | Add `color` column to `FakeConnection` schema; add `color` to `active_modalities` fixture |
| `tests/test_chart_colors.py` | Add 2 new tests for `color_for_modality` with lookup param |
| `tests/test_db.py` | Add 2 tests for color persistence and seed |
| `tests/test_charts.py` | New file — 2 tests for bar chart with/without modalities color |
| `docs/meta-prompt.md` | Update palette reference and schema docs |

---

## New Files

- `tests/test_charts.py` — Chart factory tests (bar chart with custom colors)

---

## Dependencies

```
Task 1 (schema migration)
 ├─ Task 2 (seed color) ── Task 3 (seed insert)
 ├─ Task 4 (load_all SELECT)
 ├─ Task 5 (load_active SELECT)
 ├─ Task 6 (save_modality signature)
 └─ Task 8 (FakeConnection schema) ── Task 9 (active_modalities fixture)

Task 7 (color_for_modality optional param) — independent

Task 10 (chart factories use color lookup) — depends on Task 7
Task 11 (tab renderers pass modalities)    — depends on Task 10
Task 12 (color picker UI)                  — depends on Tasks 4, 5, 6
Task 13 (save_modalities unpack color)     — depends on Tasks 6, 12
Task 14 (ensure_settings)                  — depends on Tasks 4, 5
Task 15 (tests)                            — depends on Tasks 8, 9, 10
Task 16 (docs)                             — depends on all

**Additional verifications:**
- `_migrate_v1_to_v2()` calls `save_modality()` without `color` — still works (color param defaults to None, SET clause skipped).
- `CHART_COLORS` dict auto-updates via `**MODALITY_COLORS` — no code change needed.
```

**Recommended execution order**: 1 → 2/3/4/5/6/8/9 → 7 → 10 → 11 → 12/13/14 → 15 → 16

---

## Risks

1. **ALTER TABLE in SQLite** — SQLite's `ALTER TABLE ... ADD COLUMN` doesn't support `IF NOT EXISTS`. We'll wrap in try/except and catch `OperationalError` with "duplicate column name". This is resilient but ugly. Alternative: use `PRAGMA table_info(modalities)` to check for the column before ALTERing. **Safer to use PRAGMA check** — avoids try/except on expected path.

2. **`save_modality` backward compatibility** — Existing callers (seeded_conn fixture, migration code) call `save_modality(conn, slug, price, eph, active)` without color. If we make `color` required, those break. Solution: `color` parameter defaults to `None` and the UPDATE only sets color when it's not None. Or: always set it but use the current DB value as default by reading it first. **Simplest**: make `color` default to `None` and skip the SET clause when None.

3. **chart_modalities parameter pollution** — Only `build_modality_bar()` and `build_modality_donut()` need the new optional `modalities` parameter. The other 4 chart functions (`build_monthly_modality_donut`, `build_wow_comparison_chart`, `build_modality_mix_evolution`, `_single_week_chart`) already receive `active_modalities` — they reuse that existing parameter for color lookup without any signature change. This minimizes parameter pollution.

4. **Existing tests** — 108 tests must pass. The `active_modalities` fixture needs color keys. The `FakeConnection` schema needs the column. If either is missing, tests will fail with "no such column: color". These are mechanical changes — low risk if done carefully.

5. **User changes default palette then reseeds** — If a user customizes colors, then deletes all data (Danger Zone), the re-seed resets to default palette. This is correct behavior (Danger Zone destroys everything). No special handling needed.

6. **Streamlit `st.color_picker` behavior** — `st.color_picker` opens the native OS color dialog. On Linux, this can be inconsistent across desktop environments. This is a UX concern, not a blocker. The widget is well-supported in Streamlit ≥1.54.

---

## Validation

After all tasks:
```bash
uv run pytest tests/ -v          # 108+ tests pass
uv run ruff check src/ tests/    # no errors
uv run mypy src/                 # no new errors
uv run streamlit run app.py      # manual spot-check: color picker works, charts reflect custom colors
```
