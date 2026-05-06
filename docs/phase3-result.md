# Phase 3 Result — Frontend (settings.py)

**Status:** ✅ Complete  
**File:** `src/ui/settings.py`

## Changes Made

| # | Feature | Lines | Description |
|---|---------|-------|-------------|
| 1 | Imports | 8-21 | Added `add_modality`, `delete_modality`, `slugify` |
| 2 | Editável label | 133-144 | `st.text_input` replaces `st.write(label)`; slug caption below |
| 3 | Delete per row | 175-197 | 🗑️ button → `confirm_delete_slug` → inline Confirm/Cancel |
| 4 | Add modality | 217-278 | "+" button → inline form with slug auto-generation, Salvar/Cancelar |
| 5 | `_reload_modalities()` | 88-95 | Extracted helper: cache clear + reload all_modalities + active_modalities + prices |
| 6 | `_save_modalities()` | 281-293 | Now passes `label=label` to `save_modality()`; delegates reload to helper |
| 7 | Header row | 119-131 | Extra column for delete button |

## Verification

```
$ uv run ruff check src/ui/settings.py
All checks passed!

$ uv run python -c "from src.ui.settings import render_settings_tab; print('OK')"
OK

$ uv run python -c "from src.db import add_modality, delete_modality, slugify; print('OK')"
OK
```

## Design Decisions

- **`@st.fragment` preserved** on `_render_modality_grid` — isolates reruns within the fragment
- **6-column grid** — added a 7th column (0.7fr) for delete button; price/eph narrowed from 2fr to 1.5fr
- **`_reload_modalities()` extracted** — avoids copy-paste between `_save_modalities()`, delete confirm, and add success paths
- **`updated` tuple extended** — now `(label, price, eph, active, color)` instead of `(price, eph, active, color)`
- **Slug caption on every row** — `st.caption(f"Slug: {slug}")` makes immutability clear
- **Add form disabled without label** — `disabled=not new_label` prevents empty submits
- **Duplicate slug handled** — `add_modality()` returns `False`; UI shows `st.warning` suggesting different name
