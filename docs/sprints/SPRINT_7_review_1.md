# Sprint 7 Review #1

**Scope:** `src/llm_client.py`, `src/ui/analysis.py`, `tests/test_llm_client.py`
**Date:** 2026-04-30
**Commit:** HEAD (diff reviewed)

---

## Correct ✅

### _enrich_stats edge cases
- Empty `df` is guarded with `not df.empty` before every DataFrame operation (lines 81, 95, 106, 117, 125).
- Single-row `df` works safely: `ma7`/`ma30` read the last row; acceleration trend is gated by `len(df) >= 14`; `idxmax()` works on 1 row; historical average is gated by `len(df) >= 30`.
- Missing columns are checked explicitly (`"ma7" in df.columns`, `"earnings" in df.columns`, `"date" in df.columns`).
- Division-by-zero guards exist for `days_worked`, `total_exames`, `unique_months`, and `prior/recent` MA7 comparison.

### in_flight guard with st.fragment
- `_render_ai_section` is decorated with `@st.fragment` (streamlit>=1.54 supports `st.fragment`).
- `llm_insight_in_flight` boolean flag prevents overlapping executions inside the fragment.
- `finally` block reliably resets the flag even if `LLMUnavailableError` is raised.
- The LLM call is synchronous (httpx 15 s timeout); because Streamlit runs scripts single-threaded, the in-flight guard mainly protects against rapid user re-clicks, not true concurrency.

### llm_insight_text persistence & invalidation
- `st.session_state.llm_insight_text` caches the last successful LLM response across tab switches.
- **Invalidation is correct:** when `historical_cache` key changes (goal, prices, or month), `st.session_state.pop("llm_insight_text", None)` runs before recomputing stats (line 51).
- `llm_insight_pending` is popped after successful generation or on error, so stale pending flags don't survive.

### _render_insight_body without unsafe_allow_html
- Removed `re`, `CHART_COLORS`, and manual HTML generation.
- Replaced with plain `st.markdown(text)` + `st.caption(caption)`. Streamlit natively renders `**bold**` from GPT-OSS.
- Eliminates XSS surface from LLM-generated content.

### Syntax & imports
- No syntax errors.
- All imports are used after the diff (verified with `ruff`).
- `mypy` passes on the three files.

### Tests
- **All 93 tests pass** (no regressions).

---

## Fixed 🔧

### Dead code + line-too-long in `_build_prompt` (`src/llm_client.py`)
- **Location:** `_build_prompt`, lines ~258–275.
- **Issue:** A block attempted to derive custom prices from the DataFrame but never mutated the `prices` dict (all variables computed were discarded). This triggered `ruff E501` (line 105 chars) and created misleading comments.
- **Resolution:** Removed the entire dead price-inference block. `_build_prompt` now directly builds the default `prices` dict and calls `_enrich_stats`.
- **Post-fix:** `ruff` passes; 93 tests still pass.

---

## Blockers 🚫
*None identified.*

---

## Notes ⚠️

### 1. `_enrich_stats` ticket médio ignores custom prices
- `_enrich_stats` hardcodes `35.0 / 25.0 / 4.5` for `ticket_medio` computation. If the user has custom prices in Settings, the LLM prompt will show an incorrect ticket médio even though `earnings` in the DataFrame reflect the real prices.
- **Risk:** Low — single-user app with rarely changed prices.
- **Follow-up:** Inject actual prices into `compute_historical_stats` output (or add them to session state) so `_enrich_stats` can use them.

### 2. Missing unit tests for `_enrich_stats`
- `_minimal_stats` always provides a 13-row DataFrame. There are **no tests** for:
  - Empty DataFrame (`pd.DataFrame()`)
  - Single-row DataFrame
  - Missing columns (`ma7`, `ma30`, `earnings`, `date`)
  - All-zeros or NaN values
- **Follow-up:** Add a dedicated `TestEnrichStats` class with edge-case fixtures.

### 3. Markdown newline behavior change
- Old `_render_insight_card` converted `\n` → `<br>`, preserving single newlines as hard breaks.
- `_render_insight_body` uses standard Markdown, where single newlines collapse to spaces.
- **Impact:** Minor. GPT-OSS typically returns paragraphs separated by blank lines, which render correctly. If the model returns single-newline lists or line breaks, spacing will be slightly denser.

### 4. `meta_mensal` computed twice
- `_enrich_stats` computes `meta_mensal` inside its return dict; `_build_prompt` immediately overwrites it with the same formula.
- **Impact:** Harmless redundancy; could be cleaned up later for readability.

### 5. `st.fragment` in-flight semantics
- Because Streamlit scripts run sequentially, `llm_insight_in_flight` is only useful if a fragment rerun is triggered while another script run is still executing. In practice the HTTP call blocks the event loop for up to 15 s, so the guard is largely defensive.
- **Observation:** This is acceptable for a free-tier LLM integration; if latency becomes an issue, consider running the call in a background thread or using `st.experimental_fragment` caching.

---

## Action Summary
| # | Action | Status |
|---|--------|--------|
| 1 | Fix dead price-inference code + E501 | ✅ Done |
| 2 | Add `_enrich_stats` edge-case tests | ⏳ Pending |
| 3 | Thread actual prices through to `_enrich_stats` | ⏳ Pending |
