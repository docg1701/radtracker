# Ponytail audit — 2026-07-21

Whole-repo over-engineering audit. Scope: complexity only — correctness,
security, and performance are out of scope. Findings ranked biggest cut first.

Legend: `delete` (dead code/speculative), `native` (platform already does it),
`yagni` (unneeded abstraction/config), `shrink` (same logic, fewer lines).

## Status

| # | Finding | Status |
|---|---------|--------|
| 1–2, 4–13 | All deletes, trims, refactors | **done** |
| 3 | src/cookies.py → st.context.cookies | **skipped** — Streamlit 1.57 `st.context.cookies` is read-only; no native write API exists. Keeping cookie_manager. Deleting the tab-persistence feature entirely is the only remaining cut — product decision, not made. |

---

## 1. `delete` — temp/ directory

- **What:** `temp/debug_weekly.py`, `temp/parse_exams.py`, `temp/import_historical.py`,
  8 CSVs (`assemed-2026`, `radiplan-2026`), `extracted_exams.json`.
- **Why:** one-shot historical import artifacts. The import already ran; the
  maintained tool is `scripts/import_csv.py`. Data files don't belong in git.
- **Replacement:** nothing. If the CSVs matter, keep them outside the repo.
- **Impact:** ~230 lines + 9 data files.
- **Risk:** none (verified: no references to `temp/` in README/docs/src).

## 2. `delete` — build_modality_donut

- **What:** `src/charts.py:103-160` (~55 lines).
- **Why:** zero callers anywhere (src, app.py, tests). Docstring itself says
  "kept for backward compatibility". `build_modality_bar` replaced it.
- **Replacement:** nothing; git history preserves it.
- **Impact:** -55 lines.
- **Risk:** none.

## 3. `native` — src/cookies.py module

- **What:** `src/cookies.py` (39 lines) — wraps streamlit-extras `cookie_manager`
  behind nested silent try/excepts to persist a single cookie
  (`radtracker_last_tab`).
- **Why:** Streamlit ≥ 1.30 ships native `st.context.cookies`; project pins
  `streamlit>=1.54`. The wrapper + lazy import + double fallback is pure
  indirection.
- **Replacement:** `st.context.cookies` in `app.py` (2 call sites:
  `get_last_tab_index`, `set_last_tab_index`).
- **Impact:** -39 lines (module) + simpler app.py; streamlit-extras dep stays
  (stoggle/skeleton/rain/star_rating still used).
- **Risk:** low — native cookie API differs slightly (sync timing); verify tab
  persistence manually after the swap.

## 4. `delete` — stale planning/report docs ✅ DONE

- Deleted: `plan.md`, `RESUMO_CORRECOES.md`, `data/producao_importada.md`.
- Git history preserves all three.

## 5. `yagni` — MODALITY_COLORS speculative entries

- **What:** `src/chart_colors.py:23-38` — 11 slugs; only the 5 seeded
  modalities are reachable (angiotomografia, radiografia, ressonancia_magnetica,
  tc_geral, tc_abdome_total).
- **Why:** the DB `color` column covers user-created modalities; the extra 6
  slugs (ultrassonografia, dopplervelocimetria, radiografia_contrastada,
  ultrassom_morfologico, mamografia, densitometria) are guesses about future use.
- **Replacement:** keep the 5; rely on DB colors for everything else.
- **Impact:** -8 lines.
- **Risk:** low — check `_add_color_column` backfill loop in db.py still works
  with 5 entries (it iterates the dict, so yes).

## 6. `shrink` — duplicated historical-cache key

- **What:** cache-key JSON built inline in `src/ui/analysis.py:41-46` and again
  as `_build_historical_cache_key` in `src/ui/chat.py`.
- **Why:** DRY — one authoritative builder. If the key shape changes, two
  places must change in sync today.
- **Replacement:** keep `_build_historical_cache_key` (move to
  `src/calculations.py` or a shared ui helper), import from both.
- **Impact:** -10 lines, one source of truth.
- **Risk:** none — pure refactor; both sites produce identical JSON.

## 7. `delete` — numpy direct dependency

- **What:** `numpy>=1.24.0` in `pyproject.toml` dependencies.
- **Why:** never imported in src/, tests/, app.py, scripts/. Pandas pulls it
  transitively.
- **Replacement:** nothing. Remove via `uv remove numpy`, commit pyproject + lock.
- **Impact:** -1 direct dep.
- **Risk:** none.

## 8. `delete` — DEFAULT_LLM_MODEL constant

- **What:** `src/db.py:21`.
- **Why:** defined, never referenced anywhere.
- **Replacement:** nothing.
- **Impact:** -1 line.
- **Risk:** none.

## 9. `yagni` — _build_payload stream parameter

- **What:** `src/llm_client.py:288` — `stream: bool = False` param.
- **Why:** the only call site (line 303) passes `stream=True`; the client is
  streaming-only by design.
- **Replacement:** hardcode `"stream": True` in the payload dict.
- **Impact:** -1 param.
- **Risk:** none — tests may assert the payload; update if needed.

## 10. `shrink` — _build_lookups half-used return

- **What:** `src/calculations.py:20-29` returns `(prices, eph)`; the sole
  caller (`compute_daily_stats:109`) does `_, eph = _build_lookups(...)`.
- **Why:** the prices half is dead — earnings use price-vigent lookups from
  `load_prices_at`, not current `modalities.price`.
- **Replacement:** return only the eph dict (rename e.g. `_eph_lookup`).
- **Impact:** -6 lines.
- **Risk:** none — single caller.

## 11. `delete` — unused slugs accumulation

- **What:** `src/charts.py:392,401` — `slugs` list built, appended, never read
  in `build_monthly_modality_donut`.
- **Replacement:** nothing.
- **Impact:** -3 lines.
- **Risk:** none.

## 12. `delete` — unused source parameter

- **What:** `src/ui/analysis.py:103` — `_render_insight_body(text, source="rules")`;
  `source` never read in the body.
- **Replacement:** drop the param and the call-site kwarg.
- **Impact:** -2 lines.
- **Risk:** none.

## 13. `shrink` — redundant exception tuple

- **What:** `app.py:44` — `except (ValueError, Exception)`.
- **Why:** `Exception` already covers `ValueError`.
- **Replacement:** `except Exception` (or better: `except (ValueError, TypeError)`
  if the intent was narrow — confirm intent before choosing).
- **Impact:** 0 lines, clarity only.
- **Risk:** none.

---

## Net

~-400 lines, -1 direct dependency, -12 files (incl. temp/).

## Suggested order

1. Low-risk deletes first: 1, 2, 4(done), 8, 11, 12, 13.
2. Dep removal: 7 (`uv remove numpy`).
3. Small refactors with test touchpoints: 5, 6, 9, 10.
4. Behavioral change last, with manual verification: 3 (cookies).

## Validation after each batch

```bash
uv run ruff check src/ app.py tests/
uv run pytest tests/ -v
```
