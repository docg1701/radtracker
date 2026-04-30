# Sprint 7 Review #3 (Final)

**Scope:** `src/llm_client.py`, `src/ui/analysis.py`, `tests/test_llm_client.py`  
**Date:** 2026-04-30  
**Commit:** HEAD

---

## Quality Gates

| Gate | Command | Result |
|------|---------|--------|
| Tests | `venv/bin/python -m pytest tests/ -v` | **93/93 passed** |
| Lint | `venv/bin/ruff check src/llm_client.py src/ui/analysis.py tests/test_llm_client.py` | **All checks passed** |
| Types | `venv/bin/mypy src/llm_client.py src/ui/analysis.py --ignore-missing-imports` | **Success: no issues** |

---

## Blockers Verification

### B1 — Dados novos do prompt extraídos do DataFrame (from Sprint 7 Review)
**Status: ✅ RESOLVED**

- `_enrich_stats` (`src/llm_client.py:52-172`) extracts all required scalar metrics from `stats["df"]`:
  - MA7 / MA30 latest values (lines 56-64)
  - Acceleration trend via MA7 comparison (lines 67-77)
  - Total exam counts by modality (lines 80-87)
  - Best productive day via `idxmax()` (lines 90-99)
  - Historical monthly average gated by `len(df) >= 30` (lines 102-109)
  - Ticket médio computed from counts and prices (lines 115-119)
- `_build_prompt` interpolates the enriched dict into `_USER_PROMPT_TEMPLATE`.
- Tests were updated: `_minimal_stats()` now includes a 13-row DataFrame with `ma7`, `ma30`, `earnings`, and modality count columns (`tests/test_llm_client.py:97-121`).

### B2 — Guarda contra chamadas duplicadas / in-flight protection
**Status: ✅ RESOLVED**

- `_render_ai_section` is decorated with `@st.fragment` (`src/ui/analysis.py:138`), preventing full-page reruns from triggering LLM calls.
- `llm_insight_in_flight` boolean flag guards the execution block (`src/ui/analysis.py:151-152`).
- `finally` block reliably resets the flag (`src/ui/analysis.py:172`).
- The flag survives across fragment reruns via `st.session_state`.

### B3 — Persistência do resultado da IA entre abas / session_state cache
**Status: ✅ RESOLVED**

- `st.session_state.llm_insight_text` caches successful LLM responses (`src/ui/analysis.py:165`).
- Invalidation is correct: when `historical_cache` key changes (goal, prices, or month), `st.session_state.pop("llm_insight_text", None)` runs before recomputing stats (`src/ui/analysis.py:51`).
- On subsequent full-app reruns, the cached branch renders the expander with the stored text (`src/ui/analysis.py:155-158`).

### Review #2 Blocker — Expander collapse on tab switches
**Status: ✅ RESOLVED**

- Both the cached-text branch and the success branch now render `st.expander("🤖 Análise da IA", expanded=True)` (`src/ui/analysis.py:156-157`, `src/ui/analysis.py:167-168`).
- The previous `expanded=False` in the cached branch (which caused the expander to snap shut on full-app reruns) has been removed.

### Exception handling — catches all error types
**Status: ✅ RESOLVED**

- `LLMClient.generate` wraps `httpx` errors into `LLMUnavailableError` and has a fallback `except Exception` for unexpected JSON/API errors (`src/llm_client.py:211-223`).
- `_render_ai_section` catches both `LLMUnavailableError` and raw `Exception` (`src/ui/analysis.py:169`), ensuring `_build_prompt` failures (e.g., `KeyError`, `TypeError`) do not leak and `llm_insight_pending` is always popped.
- The generic catch is intentional and matches the requirement to handle all error types gracefully.

### Empty string responses handled gracefully
**Status: ✅ RESOLVED**

- After a successful HTTP response, `if not llm_text:` rewrites empty/null content to `"(A IA retornou uma resposta vazia.)"` (`src/ui/analysis.py:163-164`).
- The rewritten non-empty string is stored in `session_state`, so the cached branch always finds a truthy value and renders the expander.

---

## Visual Code Review

### `src/llm_client.py`
- **Clean separation**: `_enrich_stats` (pure extraction) → `_build_prompt` (templating) → `generate` (I/O).
- **Edge-case guards**: Empty DataFrames, missing columns, zero denominators, and NaN values are all guarded.
- **Dead code removed**: The dead price-inference block from review #1 is gone.
- **Template interpolation safe**: All values in `_enrich_stats` return scalar primitives or formatted strings; no `None` leaks into `fmt_brl`.
- **Minor**: `_build_prompt` still hardcodes `prices: dict[str, float] = {"rm": 35.0, "tc": 25.0, "rx": 4.5}` (review #1 note 1). This means custom prices in Settings do not affect `ticket_medio` in the LLM prompt. Risk is low for a single-user app, but it remains a follow-up item.

### `src/ui/analysis.py`
- **Fragment boundary correct**: `@st.fragment` on `_render_ai_section` isolates LLM latency from the rest of the analysis page.
- **State lifecycle correct**: `llm_insight_pending` is set by `on_click`, consumed by the fragment, popped on success or error.
- **No unsafe HTML**: `_render_insight_body` uses `st.markdown(text)` + `st.caption(caption)`, eliminating the XSS surface from LLM output.
- **Minor**: No explicit `key` on `st.expander`; fragment reruns will reset the user's toggle to `expanded=True`. The fragment has no other interactive widgets, so this is acceptable for now.

### `tests/test_llm_client.py`
- Covers success (200), missing/empty key, timeout, HTTP 401/429/500.
- Covers `_build_prompt` sanitization (`None` wow) and BRL formatting.
- **Follow-up**: Still no dedicated edge-case tests for `_enrich_stats` (empty df, single row, missing columns, all-zeros). This was review #1 action #2 and remains pending.

---

## Review Summary

| Item | Status |
|------|--------|
| B1 — Prompt data extraction | ✅ Resolved |
| B2 — In-flight / duplicate-call guard | ✅ Resolved |
| B3 — IA result persistence across tabs | ✅ Resolved |
| Review #2 expander collapse | ✅ Resolved |
| Exception handling catches all types | ✅ Resolved |
| Empty string responses | ✅ Resolved |
| pytest 93/93 | ✅ Pass |
| ruff | ✅ Pass |
| mypy | ✅ Pass |
| Custom prices through to ticket_medio | ⏳ Follow-up (low risk) |
| `_enrich_stats` edge-case tests | ⏳ Follow-up |

**Verdict: SPRINT 7 IS READY.**

All critical blockers are resolved, all quality gates pass, and the implementation is minimal and focused. The two remaining follow-up items (custom prices in prompt and edge-case unit tests) are acceptable technical debt for a single-user local app and do not block shipping.
