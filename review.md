# Review: Implementation Plan for Per-Modality Color Customization

**Status: APPROVED with corrections required**

---

## Summary

The plan correctly identifies all files that need changes and proposes a sound architecture:
- DB schema migration via `ALTER TABLE` + `PRAGMA table_info()` check
- Backward-compatible `color_for_modality()` with optional lookup
- `st.color_picker` widget integration in the settings grid
- Propagation of custom colors to all chart factories
- Test coverage for the new behavior

However, **4 blockers must be fixed** before implementation, plus 2 warnings.

---

## Blockers (must fix)

### 1. `save_modality()` — contradictory instructions between Task 6 and Risk #2

**Problem:** Task 6 says:
> "Prefer (a) — always update all 4 fields for simplicity"

But Risk #2 correctly identifies:
> "Existing callers (seeded_conn fixture, migration code) call `save_modality(conn, slug, price, eph, active)` without color. [...] Solution: `color` parameter defaults to `None` and the UPDATE only sets color when it's not None."

These are contradictory. If we "always update all 4 fields", the `seeded_conn` fixture (Task 9) and `_migrate_v1_to_v2()` will overwrite colors with `None`.

**Fix required in plan:**
- Make `color` parameter default to `None`
- Conditionally add `color = :color` to the SET clause only when `color is not None`
- Remove the contradictory "Prefer (a)" sentence

---

### 2. Redundant `modalities` parameter for functions that already receive `active_modalities`

**Problem:** Task 10 proposes adding `modalities: list[dict] | None = None` to:
- `build_wow_comparison_chart()` — already takes `active_modalities: list[dict[str, Any]]`
- `build_modality_mix_evolution()` — already takes `active_modalities: list[dict[str, Any]]`
- `build_monthly_modality_donut()` — already takes `active_modalities: list[dict[str, Any]]`
- `_single_week_chart()` — already takes `active_modalities: list[dict[str, Any]]`

Adding a *second* list parameter with the same data is confusing and violates DRY.

**Fix required in plan:**
- For these 4 functions, do NOT add a new `modalities` parameter
- Instead, use the existing `active_modalities` parameter to look up colors:
  ```python
  color = next(
      (m.get("color", color_for_modality(m["slug"])) for m in active_modalities if m["slug"] == slug),
      color_for_modality(slug)
  )
  ```
- Or simpler: build a `color_lookup` dict from `active_modalities` at the top of each function

---

### 3. `build_progress_gauge()` incorrectly listed as needing `modalities`

**Problem:** Task 11 says:
> `src/ui/month.py` | Pass `modalities=` to `build_progress_gauge()` and `build_monthly_modality_donut()`

`build_progress_gauge()` uses the teal monochrome gradient (`progress_danger`, `progress_warning`, `progress_on_track`, `progress_achieved`) plus `primary` and `track`. It never calls `color_for_modality()`. Passing `modalities` to it is meaningless.

**Fix required in plan:**
- Remove `build_progress_gauge()` from Task 11
- Only `build_monthly_modality_donut()` needs the change (and it already receives `active_modalities`, so see Blocker #2)

---

### 4. `build_monthly_earnings_chart()` incorrectly listed as needing `modalities`

**Problem:** Task 11 (implied by the file list) suggests `month.py` needs to pass `modalities` to chart factories. `build_monthly_earnings_chart()` uses `CHART_COLORS["primary"]`, `CHART_COLORS["muted"]`, and `CHART_COLORS["neutral"]` — all structural colors. No modality colors.

**Fix required in plan:**
- Remove `build_monthly_earnings_chart()` from the propagation list in Task 11

---

## Warnings (should fix)

### 5. 5 columns in settings grid violates layout skill guidance

**Evidence:** The `using-streamlit-layouts` skill explicitly states:
> "Columns: max 4, set alignment"
> "BAD: Too many, cramped — `col1, col2, col3, col4, col5, col6 = st.columns(6)`"

The plan proposes `[3, 2, 2, 1, 1]` (5 columns). While 5 is less than 6, it's still over the recommended maximum and will be cramped on smaller screens.

**Recommendation:**
- Option A: Reduce ratios to `[2.5, 2, 2, 0.8, 0.8]` to squeeze the color and active columns
- Option B: Put the color swatch inline with the label (e.g., a small colored circle before the label text)
- Option C: Use `st.data_editor` instead of manual columns — it handles inline editing more cleanly

---

### 6. Importing `chart_colors` into `db.py` couples layers

**Problem:** Task 2 proposes:
> "Import `MODALITY_COLORS` from `src/chart_colors` and use it to set the value"

This couples the persistence layer (`db.py`) to the presentation layer (`chart_colors.py`). While not a circular dependency (`chart_colors.py` has no imports), it breaks separation of concerns.

**Recommendation:**
- Define default colors directly in `db.py` (e.g., `_DEFAULT_MODALITY_COLORS`) or
- Accept the coupling since `chart_colors.py` is a pure data module with zero dependencies — low risk

---

## Verified Correct ✅

### Streamlit API claims
- **`st.color_picker`** — Valid widget. Parameters `label`, `value` (hex string), `key`, `label_visibility` are all correct per Streamlit API (confirmed via training knowledge; ctx7 search did not return direct docs but the API is stable and well-known)
- **`st.columns([3, 2, 2, 1, 1])`** — Valid API call, though cramped per layout skill
- **`label_visibility="collapsed"`** — Valid parameter value
- **`@st.fragment`** — The `_render_modality_grid` is already decorated with `@st.fragment`; adding 11 color pickers inside it will correctly isolate reruns

### SQLite claims
- **`ALTER TABLE ... ADD COLUMN`** — Correct. SQLite supports this but not `IF NOT EXISTS`
- **`PRAGMA table_info(modalities)`** — Correct approach to check if column exists before ALTERing
- **Default value with `DEFAULT '#64748B'`** — Correct SQLite syntax

### Source file signatures (verified against actual code)
| Function | Current Signature | Plan's Claim | Match |
|---|---|---|---|
| `save_modality()` | `(conn, slug, price, eph, active)` | Add `color=None` | ✅ |
| `load_all_modalities()` | SELECTs 6 columns | Add `color` | ✅ |
| `load_active_modalities()` | SELECTs 6 columns | Add `color` | ✅ |
| `color_for_modality()` | `(slug) -> str` | Add `modalities=None` | ✅ |
| `build_modality_bar()` | `(counts, labels_lookup)` | Add `modalities=None` | ✅ |
| `build_modality_donut()` | `(counts, labels_lookup)` | Add `modalities=None` | ✅ |
| `build_monthly_modality_donut()` | `(df, active_modalities)` | Already has `active_modalities` | ⚠️ see Blocker #2 |
| `build_wow_comparison_chart()` | `(weekly_data, df, active_modalities)` | Already has `active_modalities` | ⚠️ see Blocker #2 |
| `build_modality_mix_evolution()` | `(mix_history, active_modalities)` | Already has `active_modalities` | ⚠️ see Blocker #2 |
| `_single_week_chart()` | `(df, active_modalities)` | Already has `active_modalities` | ⚠️ see Blocker #2 |

### Meta-prompt constraints
| Constraint | Plan Compliance |
|---|---|
| No custom CSS / `unsafe_allow_html=True` | ✅ Uses only `st.color_picker` |
| No deprecated streamlit-extras | ✅ No changes to imports |
| No `st.divider()` | ✅ Not introduced |
| No `st.form` in sidebar | ✅ Changes are in main area (Settings tab) |
| No .env file | ✅ No change |
| Portuguese locale | ✅ Labels remain Portuguese |
| No DB access in chart modules | ✅ Chart modules receive data as parameters |
| Dynamic modalities | ✅ No hardcoded labels |
| All colors from `chart_colors.py` | ✅ Plan preserves this |

---

## Missing Items (add to plan)

1. **`_migrate_v1_to_v2()` in `db.py`** — This function calls `save_modality()` without a `color` parameter. With the Blocker #1 fix (optional `color`), this will continue to work. But the plan should explicitly verify this.

2. **`CHART_COLORS` dict update** — The plan doesn't mention updating `CHART_COLORS` in `chart_colors.py`. Since `CHART_COLORS` does `**MODALITY_COLORS`, it will automatically pick up any color changes. However, the legacy aliases (`rm`, `tc`, `rx`) will also need to stay in sync. Since they reference `MODALITY_COLORS[...]`, they'll auto-update too. No action needed, but worth noting.

3. **`docs/meta-prompt.md` schema update** — Task 16 mentions updating the palette reference, but should also update the `ensure_settings()` state architecture table to note that `all_modalities` and `active_modalities` now include a `"color"` key.

4. **Test for `_migrate_v1_to_v2()`** — If `save_modality` changes signature, any test that calls it with the old signature must still pass. The `seeded_conn` fixture uses the old signature — covered in Task 9, but `_migrate_v1_to_v2` tests should also be checked.

---

## Recommended Execution Order (revised)

```
Task 1 (schema migration)
 ├─ Task 2 (seed color) ── Task 3 (seed insert)
 ├─ Task 4 (load_all SELECT)
 ├─ Task 5 (load_active SELECT)
 ├─ Task 6 (save_modality with optional color)   ← FIX: conditional SET
 └─ Task 8 (FakeConnection schema) ── Task 9 (active_modalities fixture)

Task 7 (color_for_modality optional param) — independent

Task 10 (chart factories) — REVISED:
  - build_modality_bar, build_modality_donut: add optional modalities param
  - build_monthly_modality_donut, build_wow, build_mix, _single_week:
    USE EXISTING active_modalities, no new param

Task 11 (tab renderers pass modalities) — REVISED:
  - today.py: pass to build_modality_bar only
  - month.py: pass to build_monthly_modality_donut only (already has active_mods)
  - analysis.py: already passes active_mods to wow/mix — no change needed

Task 12 (color picker UI) — depends on Tasks 4, 5, 6
  - FIX: address 5-column layout concern

Task 13 (save_modalities unpack color) — depends on Tasks 6, 12

Task 14 (ensure_settings) — no changes needed, as plan correctly notes

Task 15 (tests) — depends on Tasks 8, 9, 10

Task 16 (docs) — depends on all
```

---

## Final Verdict

**The plan is fundamentally sound and well-structured.** The 4 blockers are all fixable by editing the plan text — no architectural changes needed. The 2 warnings are minor UX/code-quality concerns. Once corrected, the plan can proceed to implementation.

**Required edits:**
1. Task 6: make `color` optional with conditional SET clause (remove "always update all 4 fields")
2. Task 10: remove `modalities` param from functions that already have `active_modalities`; use existing param instead
3. Task 11: remove `build_progress_gauge` and `build_monthly_earnings_chart` from propagation list
4. Risk #2 and Task 6: align on the conditional SET approach
5. Task 12: address 5-column layout (recommendation provided)
6. Task 2: decide on coupling vs. inline defaults (recommendation provided)
