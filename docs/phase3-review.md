# Phase 3 (Frontend) Review — v1.4.0

**File reviewed:** `src/ui/settings.py` (full)  
**Reference:** `docs/plan-v1.4.0.md` — Phase 3 checklist + delete/add/save/edge-case requirements  
**Date:** 2026-05-05

---

## Correct — all Phase 3 requirements implemented

| # | Requirement | Evidence (line numbers in `src/ui/settings.py`) |
|---|-------------|------------------------------------------------|
| 1 | **Label editable** — `st.text_input` per row | `new_label = st.text_input(..., key=f"mod_label_{slug}", ...)` — **lines 117-121** |
| 2 | **Caption "Slug: {slug}"** below label | `st.caption(f"Slug: {slug}")` — **line 122** |
| 3 | **Button "➕ Adicionar modalidade"** at bottom | `st.button("➕ Adicionar modalidade", type="secondary")` — **line 166** |
| 4 | **New-modality row inline** with label, price, eph, color, Save, Cancel | Rendered when `st.session_state.new_modality_pending` is `True` — **lines 168-211** |
| 5 | **Auto slug** — generated from label via `slugify()` | `new_slug = slugify(new_label)` shown as caption — **lines 174-177** |
| 6 | **🗑️ button per row** | `st.button("🗑️", key=f"mod_del_btn_{slug}", ...)` — **lines 139-143** |
| 7 | **Inline confirmation** — warning + Confirm/Cancel, not a dialog | `st.warning(...)` + `st.button("Confirmar", key=f"mod_del_confirm_{slug}")` + `st.button("Cancelar", key=f"mod_del_cancel_{slug}")` — **lines 146-160** |
| 8 | **Save modalities** persists labels via `save_modality(labels=...)` | `_save_modalities()` passes `label=label` to `save_modality(...)` — **lines 206-211** |
| 9 | **`_reload_modalities()` helper** extracted | Defined at **lines 99-108**; called after save, delete and add flows |
| 10 | **Imports** — `add_modality`, `delete_modality`, `slugify` from `src.db` | `from src.db import ..., add_modality, delete_modality, ..., slugify` — **lines 17-28** |
| 11 | **Fragment preserved** — `@st.fragment` still on grid | `@st.fragment` decorator on `_render_modality_grid` — **line 111** |

### Delete cascade flow
- `delete_modality(conn, slug)` called — **line 153**. Verified in `src/db.py:273-307` that it deletes from `daily_production_items` first, then `modalities`, inside an explicit transaction.
- `_reload_modalities(conn)` refreshes session state — **line 154**.
- `confirm_delete_slug = None` and `st.rerun()` — **lines 155-156**.

### Add flow
- Save button disabled when label empty: `disabled=not new_label` — **line 192**.
- `add_modality()` result checked: `success = add_modality(...)` — **line 194**.
- Warning on duplicate slug: `st.warning(f"Slug '{new_slug}' já existe...")` — **lines 203-205**.
- Session state cleared on success (`new_modality_pending = False` — **line 197**) and on cancel (`new_modality_pending = False` — **line 209**).

### Save flow
- `_save_modalities()` receives the `updated` dict built in the loop.
- In the loop, `new_label` is captured directly from the `st.text_input` widget return value (**line 117**).
- The `changed` comparison (**lines 158-163**) correctly detects label edits and stores the new label in `updated[slug]`.
- `_save_modalities` unpacks `(label, price, eph, active, color)` and passes `label=label` to `save_modality` — **lines 206-211**.

### Key uniqueness
All widget keys are unique and deterministic:
- Existing rows: `mod_label_{slug}`, `mod_price_{slug}`, `mod_eph_{slug}`, `mod_color_{slug}`, `mod_active_{slug}`, `mod_del_btn_{slug}`, `mod_del_confirm_{slug}`, `mod_del_cancel_{slug}`
- New row: `mod_new_label`, `mod_new_price`, `mod_new_eph`, `mod_new_color`, `mod_new_save`, `mod_new_cancel`

Because `slug` is the database primary key, no collisions are possible.

---

## Fixed

*No issues required correction during this review.*

---

## Blocker

*None found.*

All functional requirements from the Phase 3 checklist are present and wired correctly. The fragment state management, DB imports, and CRUD callbacks are coherent.

---

## Warning

### 1. New-modality widget state not reset on Cancel
**Location:** `src/ui/settings.py` — **lines 208-210**

When the user clicks **Cancelar**, only `new_modality_pending` is set to `False`. The widget values for `mod_new_label`, `mod_new_price`, `mod_new_eph`, and `mod_new_color` remain in `st.session_state`. On the next click of **"➕ Adicionar modalidade"**, the previous (possibly partially filled) values reappear.

**Recommendation:** Pop or reset the widget keys in session state inside the Cancel handler:

```python
for key in ("mod_new_label", "mod_new_price", "mod_new_eph", "mod_new_color"):
    st.session_state.pop(key, None)
```

### 2. Delete confirmation message uses unsaved label value
**Location:** `src/ui/settings.py` — **line 147**

```python
st.warning(f"Remover **{new_label}**? Dados de produção serão perdidos.")
```

`new_label` is the current value of the `st.text_input` widget. If the user typed a new label but has not yet saved, the confirmation message displays the *edited* (unsaved) name instead of the original DB label. This is slightly misleading because the deletion operates on the slug, not the pending label change.

**Recommendation:** Use the original `label` variable (read from `m["label"]` at **line 116**) in the warning text:

```python
st.warning(f"Remover **{label}**? Dados de produção serão perdidos.")
```

---

## Note

### 1. Missing UI-level tests for the fragment
The plan lists `tests/test_settings.py` for UI add/remove/rename tests. No such file exists. While `tests/test_db.py` thoroughly covers the backend CRUD (`add_modality`, `delete_modality`, `slugify`, `save_modality_with_label`, etc.), the Streamlit fragment logic in `settings.py` is untested. Given the complexity of session-state callbacks inside a fragment, even a small set of behavioural assertions (e.g., ensuring `_reload_modalities` is called after delete) would improve regression safety.

### 2. Grid ordering may "jump" after renaming
`load_all_modalities` in `src/db.py` orders by `label COLLATE NOCASE`. If a user renames a modality (e.g., "TC Geral" → "Zzz Tomografia"), the row will move to the bottom of the grid on the next reload. This is expected behaviour, but worth noting as a UX quirk.

### 3. No guard against deleting the last modality
There is no explicit check preventing the user from deleting every modality. If `all_mods` becomes empty, the grid simply renders no rows and the "Salvar modalidades" button disappears. The app remains functional, and the user can still add a new modality via the **"+"** button. This is acceptable but leaves the settings page in a potentially confusing empty state.

### 4. Danger zone uses hardcoded raw SQLite connection (pre-existing, out of scope)
`_render_danger_zone` → `_delete_all_data` opens `sqlite3.connect("data/telerrad.db")` directly instead of using the injected `conn` object. This is unrelated to Phase 3 but is an architectural inconsistency.

---

## Verdict

✅ **Phase 3 is functionally complete.** All checklist items are implemented, imports are correct, the fragment decorator is preserved, and the save/delete/add flows behave as specified. No blockers. The two warnings above are minor UX improvements that can be addressed in a follow-up polish pass or left as-is if deemed acceptable.
