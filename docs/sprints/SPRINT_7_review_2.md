# Sprint 7 Review #2

**Scope:** `src/llm_client.py`, `src/ui/analysis.py`, `tests/test_llm_client.py`
**Date:** 2026-04-30
**Commit:** HEAD (diff reviewed)
**Baseline:** Review #1 findings are assumed fixed/known. This review focuses on issues **not** caught in Review #1.

---

## Correct ✅

### Tests, lint, and type-check
- **93/93 tests pass** — no regressions.
- **Ruff** (`venv/bin/ruff check src/llm_client.py src/ui/analysis.py tests/test_llm_client.py`): all clean.
- **Mypy** (`venv/bin/mypy src/llm_client.py src/ui/analysis.py --ignore-missing-imports`): no issues.

### `on_click` callback — no stale-closure bug
- The button callback is `lambda: st.session_state.update(llm_insight_pending=True)`.
- It references `st.session_state` (module-level singleton) at call-time, with no closure over local variables from `_render_ai_section`. Verified: no stale-variable capture.

### Streamlit API deprecations
- `st.plotly_chart(..., width="stretch")` is the **recommended** modern spelling (replaces deprecated `use_container_width`).
- `@st.fragment` is the stable API in Streamlit 1.57; no `st.experimental_fragment` usage found.
- `st.toast`, `st.spinner`, `st.expander`, `st.button(type="secondary")` are all valid in 1.57.

### Thread safety / reentrancy guard
- Streamlit runs scripts single-threaded per session. `llm_insight_in_flight` is sufficient to prevent overlapping LLM calls from rapid re-clicks, and the `finally` block ensures it is always reset.
- No concrete cross-thread race condition exists in the current single-threaded model.

---

## Blockers 🚫

### 1. IA expander collapses on full-app reruns (tab switches)
**Location:** `src/ui/analysis.py`, `_render_ai_section` — lines 145–148 and 160–161.

**Evidence:** The expander is rendered in two branches with different `expanded` values and no persistent key:
```python
# Cached-text branch
with st.expander("🤖 Análise da IA", expanded=False):
    _render_insight_body(llm_text, source="llm")

# Success branch (immediately after generation)
with st.expander("🤖 Análise da IA", expanded=True):
    _render_insight_body(llm_text, source="llm")
```

**Root cause:** `st.expander` defaults to `on_change="ignore"`. In this mode Streamlit **does not track state** (`.open` returns `None`, docs: "The expander doesn't track state"). The `expanded` parameter authoritatively sets visibility on **every** render.

**Impact:** After the user generates an AI analysis, the expander is open. If they switch to another tab and return (or any full-app rerun occurs), the fragment re-executes as part of the full run, hits the cached-text branch (`expanded=False`), and the expander **snaps shut** — the analysis is hidden.

**Fix:** Add a stable `key` and use `on_change="rerun"` to let Streamlit persist the user's toggle, or always render with the same `expanded` value once text exists (e.g., default to `expanded=True` in both branches and add a key).

---

## Fixed 🔧

*None applied in this review.*

---

## Notes ⚠️

### 1. Large DataFrame retained in `session_state`
**Location:** `src/ui/analysis.py`, line ~51.

```python
st.session_state.historical_cache = {"key": cache_key, "stats": stats}
```

`stats` contains the full historical DataFrame (`df`) built by `compute_historical_stats`, which concatenates **all** months of daily records. As the database grows, this DataFrame grows unbounded. It is overwritten on each full app run, so it is not an *unbounded* leak, but it is a large object persistently held in memory for the lifetime of the browser session.

**Risk:** Low for a single-user local app, but it becomes a memory-pressure concern after years of daily data.
**Follow-up:** Consider returning only the scalar aggregates needed by the fragment from `compute_historical_stats`, or keep `df` in a module-level cache instead of session state.

### 2. Uncaught exceptions from `_build_prompt` leave `llm_insight_pending=True`
**Location:** `src/llm_client.py` line ~210; `src/ui/analysis.py` lines 150–162.

`LLMClient.generate` calls `self._build_prompt(stats)` **outside** its internal `try/except` block:

```python
def generate(self, stats: dict[str, Any]) -> str:
    user_prompt = self._build_prompt(stats)   # <-- not wrapped
    try:
        response = httpx.post(...)
        ...
```

If `_build_prompt` (or the `_enrich_stats` it calls) raises an unexpected exception — e.g., `KeyError` on a missing column — the exception propagates out of `generate` as a raw Python exception, **not** as `LLMUnavailableError`.

In `_render_ai_section`:
```python
    except LLMUnavailableError:
        ...
        st.session_state.pop("llm_insight_pending", None)
```

The raw exception is **not caught**, so `llm_insight_pending` is never popped. On the next fragment rerun Streamlit will see `pending=True` and attempt another LLM call, potentially creating a retry-loop for deterministic errors.

**Follow-up:** Broaden the `except` in `_render_ai_section` to `except (LLMUnavailableError, Exception) as exc:` and always pop `pending`, or move `_build_prompt` inside the `try` block of `generate` and wrap its errors in `LLMUnavailableError`.

### 3. Empty string LLM response makes the expander vanish
**Location:** `src/ui/analysis.py`, lines 145–148.

If OpenRouter returns a valid 200 with `"content": ""`, the code stores `""` in `st.session_state.llm_insight_text`. On subsequent fragment reruns:

```python
llm_text = st.session_state.get("llm_insight_text")
if llm_text:   # "" is falsy
    ...
```

The expander is not rendered at all. The user sees no result and no error message.

**Follow-up:** Use `if llm_text is not None:` or check `if isinstance(llm_text, str):` so that empty (but valid) responses still render the expander, possibly with a fallback caption.

### 4. `st.fragment` argument capture semantics
`_render_ai_section(stats)` receives `stats` by value at call time. Because fragments cache the wrapped function and its closure-captured arguments, the DataFrame inside `stats` is retained by the fragment storage for the lifetime of the session (until the next full app run overwrites it). This is the same object referenced by `session_state.historical_cache`, so there is no extra copy, but it does mean the fragment closure holds a reference to the large DataFrame. This is expected Streamlit fragment behavior, but worth documenting for future memory profiling.

---

## Tool Output Summary

| Tool | Command | Result |
|------|---------|--------|
| pytest | `venv/bin/python -m pytest tests/ -v` | 93 passed |
| ruff | `venv/bin/ruff check src/llm_client.py src/ui/analysis.py tests/test_llm_client.py` | All checks passed |
| mypy | `venv/bin/mypy src/llm_client.py src/ui/analysis.py --ignore-missing-imports` | Success: no issues found |
