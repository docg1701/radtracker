# Phase 1 (Backend) Review — v1.4.0

**Reviewer:** Nonatinho  
**File reviewed:** `src/db.py`  
**Date:** 2026-05-05  
**Plan reference:** `docs/plan-v1.4.0.md`

---

## Executive Summary

All 8 Phase 1 checklist items are **correctly implemented** in `src/db.py`. Production values match the specification exactly. Transaction handling, migration idempotency, and `init_db` ordering are all sound.

**Blockers:** 0  
**Warnings:** 0  
**Notes:** 3 (pre-existing migration interaction, stale legacy fallback, cosmetic slug inconsistency)

---

## Checklist Verification

### 1. `slugify(label) → str` ✅

**Location:** `src/db.py:112–125`

| Requirement | Evidence |
|-------------|----------|
| `unicodedata.normalize("NFKD", ...)` | Line 122 |
| Lowercase + ASCII encode/decode | Line 122–123 |
| Underscore separator | Line 124 (`re.sub(r"[^a-z0-9]+", "_", ...)`) |
| Strip leading/trailing underscores | Line 124 (`.strip("_")`) |
| Fallback `"modalidade"` if empty | Line 125 (`return value or "modalidade"`) |

**Verified:** The implementation matches the spec precisely.

---

### 2. `_MODALITY_SEED` — 5 entries, hardcoded colors ✅

**Location:** `src/db.py:27–33`

| # | slug | label | sort_order | color |
|---|------|-------|------------|-------|
| 1 | `angiotomografia` | Angiotomografia | 1 | `#0D9488` |
| 2 | `radiografia` | Radiografia | 2 | `#2563EB` |
| 3 | `ressonancia_magnetica` | Ressonância Magnética | 3 | `#7C3AED` |
| 4 | `tc_geral` | TC Geral | 4 | `#6366F1` |
| 5 | `tc_abdome_total` | TC de Abdome Total | 5 | `#0891B2` |

**Verified:** Exactly 5 entries. No `MODALITY_COLORS` lookup — colors are literal hex strings.

---

### 3. `_seed_modalities()` — production values, empty-table guard ✅

**Location:** `src/db.py:395–418`

- Empty-table guard at line 397–398: `SELECT COUNT(*) ...` → early `return` if `cnt > 0`.
- Iterates `_MODALITY_SEED` and pulls values from `_PRODUCTION_DEFAULTS` (lines 401–405).
- Inserts `active = 1`, correct `price` and `exams_per_hour` for all 5 defaults.
- Uses a single `with conn.connect()` transaction with `db_conn.commit()` at the end.

**Verified:** Seed logic is correct and safe.

---

### 4. `add_modality(conn, slug, label, price, exams_per_hour, active, color) → bool` ✅

**Location:** `src/db.py:175–219`

- Duplicate-slug check: `SELECT COUNT(*) ... WHERE slug = :slug` (lines 195–200). Returns `False` if found.
- `sort_order` auto-calculation: `COALESCE(MAX(sort_order), 0) + 1` (lines 202–206).
- Single transaction: `INSERT` and `commit` inside one `with conn.connect()` block (lines 207–218).
- Return value: `False` on duplicate, `True` on success.
- Default color: `#64748B` (line 176).

**Verified:** Signature and behavior match the plan.

---

### 5. `delete_modality(conn, slug) → bool` ✅

**Location:** `src/db.py:222–252`

- Existence check first (lines 234–240) → returns `False` if missing.
- **DELETE order is correct:**
  1. `DELETE FROM daily_production_items WHERE modality_slug = :slug` (line 246)
  2. `DELETE FROM modalities WHERE slug = :slug` (line 250)
- Single explicit transaction: both deletions + `commit()` inside one `with conn.connect()` (lines 232–251).
- Returns `True` on success.

**Verified:** Cascade order and transaction boundaries are correct.

---

### 6. `save_modality()` — optional `label=None` ✅

**Location:** `src/db.py:143–172`

- New signature includes `label: str | None = None` (line 146).
- `label` is added to `SET` clauses **only** when `label is not None` (lines 160–162).
- Same pattern applied to optional `color` (lines 163–164), which aligns with the plan’s intent.

**Verified:** Signature and conditional update logic are correct.

---

### 7. `_migrate_v1_3_to_v1_4_defaults(conn)` — idempotent, scoped update ✅

**Location:** `src/db.py:444–464`

- Updates **only** rows matching `WHERE slug = :slug AND price = 0.0 AND active = 0` (lines 457–459).
- Sets `label`, `price`, `exams_per_hour`, and `active = 1` for the 5 standard slugs (lines 453–456).
- Idempotent: after first run, `price > 0` or `active = 1`, so subsequent runs are no-ops.

**Verified:** Migration scope and idempotency are correct.

---

### 8. `init_db()` — correct migration order ✅

**Location:** `src/db.py:56–109`

Order of calls inside `init_db`:

1. `_add_color_column(conn)` — line 101
2. `_seed_modalities(conn)` — line 103
3. `_migrate_v1_3_to_v1_4_defaults(conn)` — line 105
4. `_migrate_v1_to_v2(conn)` — line 106

**Verified:** The v1.4 migration runs **after** `_seed_modalities()` and **after** `_add_color_column()`, exactly as required.

---

## Production Values Verification

Values in `_PRODUCTION_DEFAULTS` (`src/db.py:36–42`) match the specification perfectly:

| slug | label | price | exams_per_hour | active |
|------|-------|-------|----------------|--------|
| `angiotomografia` | Angiotomografia | 30.00 | 4.0 | 1 |
| `radiografia` | Radiografia | 4.00 | 80.0 | 1 |
| `ressonancia_magnetica` | Ressonância Magnética | 35.00 | 8.0 | 1 |
| `tc_geral` | TC Geral | 30.00 | 10.0 | 1 |
| `tc_abdome_total` | TC de Abdome Total | 60.00 | 5.0 | 1 |

Both `_seed_modalities()` and `_migrate_v1_3_to_v1_4_defaults()` consume these values correctly.

---

## Notes

### NOTE-1: `_migrate_v1_to_v2()` can clobber production defaults for direct v1 → v1.4 upgrades

**Location:** `src/db.py:466–527`

`_migrate_v1_to_v2()` runs **after** `_migrate_v1_3_to_v1_4_defaults()` in `init_db`. For a user upgrading directly from v1 (with legacy daily data but no `exam_prices`), `_migrate_v1_to_v2()` unconditionally updates `ressonancia_magnetica`, `tc_geral`, and `radiografia` with fallback values from `DEFAULT_PRICES` and hardcoded `exams_per_hour` (7.5 / 75.0). This overwrites the production defaults that `_migrate_v1_3_to_v1_4_defaults()` just applied:

| Field | Production default | `_migrate_v1_to_v2` fallback |
|-------|-------------------|------------------------------|
| `tc_geral` price | 30.00 | 25.00 (`DEFAULT_PRICES`) |
| `radiografia` price | 4.00 | 4.50 (`DEFAULT_PRICES`) |
| `tc_geral` eph | 10.0 | 7.5 (hardcoded) |
| `ressonancia_magnetica` eph | 8.0 | 7.5 (hardcoded) |
| `radiografia` eph | 80.0 | 75.0 (hardcoded) |

**Impact:** Narrow — only affects direct v1 → v1.4 upgrades where `exam_prices` is empty. Existing v2 users are unaffected because `_migrate_v1_to_v2()` returns early when `daily_production_items` already has data.

**Suggested fix:** Update `_migrate_v1_to_v2()` to use `_PRODUCTION_DEFAULTS` as the fallback source instead of the stale `DEFAULT_PRICES` and hardcoded eph values.

---

### NOTE-2: `DEFAULT_PRICES` contains stale legacy values

**Location:** `src/db.py:18–22`

```python
DEFAULT_PRICES = {
    "ressonancia_magnetica": 35.0,   # matches production
    "tc_geral": 25.0,                # ❌ production = 30.00
    "radiografia": 4.5,              # ❌ production = 4.00
}
```

These are only used as a fallback in `load_prices()` when no active modalities exist. Since the seed and migration set active modalities with correct values, this fallback rarely triggers. Still worth aligning to avoid confusion.

---

### NOTE-3: Seed slug `tc_abdome_total` does not match `slugify()` output for its label

**Location:** `src/db.py:33`

- Seed label: `"TC de Abdome Total"`
- Seed slug (hardcoded): `"tc_abdome_total"`
- `slugify("TC de Abdome Total")` → `"tc_de_abdome_total"`

This is harmless because the seed bypasses `slugify()`, but it creates a minor inconsistency: if a user manually types "TC de Abdome Total" into the add-modality form, they will get a different slug (`tc_de_abdome_total`) than the seeded one. Not a functional bug — just a UX quirk.

---

## Conclusion

**Phase 1 backend implementation is complete and correct.** All required functions, seeds, migrations, and orchestration logic are present and match the plan. No blockers or warnings. The three notes above are non-blocking follow-ups, with NOTE-1 being the most impactful for edge-case upgrade scenarios.
