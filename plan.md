# Implementation Plan — Fix Markdown Math Rendering

## Goal

Replace the broken token-by-token regex conversion of LaTeX delimiters with a paired-delimiter-aware, full-string processor that correctly handles streaming, storage, and history rendering.

## Root Cause

`src/text_sanitize.py` applies four **independent** regex replacements to each streaming token:

```
\[  →  $$    (any occurrence, not just paired)
\]  →  $$    (any occurrence)
\(  →  $     (any occurrence)
\)  →  $     (any occurrence)
```

Three fatal flaws:

1. **Unpaired delimiters**: A standalone `\(` becomes `$`, opening an inline-math block that never closes — all subsequent text renders in KaTeX math font (green/tiny).
2. **False positives**: Non-math `\(text\)` (escaped parentheses) becomes `$text$` — rendered as math.
3. **Token-boundary splits**: `\` in token N and `(` in token N+1 cannot match `\(`.

## Architecture Decision

**Do NOT process math during streaming at all.** Only sanitize whitespace (thin-space/NBSP) and strip legacy `\\$` per-token. Math delimiter conversion must run on the **complete** accumulated string, because it requires paired-delimiter matching.

Streamlit's `st.write_stream` concatenates tokens internally and renders incrementally — partial `$...` math that spans multiple tokens *already works correctly* in Streamlit's renderer because it re-renders the entire accumulated buffer on each yield. So `$` delimiters (which the LLM may output natively) are fine during streaming. The only conversion needed is `\(...\)` → `$...$` and `\[...\]` → `$$...$$`, which must be done on the full string.

Apply full-string sanitization **once**, after `st.write_stream` returns, and store the clean result. On history rerun, apply the same sanitization to stored content (idempotent).

## Tasks

### 1. Rewrite `sanitize_text()` to use paired-delimiter matching

- **File**: `src/text_sanitize.py`
- **Changes**:
  - Replace 4 standalone regexes with **2 paired-delimiter regexes**:
    - `re.compile(r"\\\\\\[(.*?)\\\\\\]", re.DOTALL)` — matches `\[...\]` (lazy, dotall) → replace with `$$\\1$$`
    - `re.compile(r"\\\\\\((.*?)\\\\\\)", re.DOTALL)` — matches `\(...\)` (lazy, dotall) → replace with `$\\1$`
  - These regexes only match **complete pairs**. Standalone `\(` or `\[` are left untouched.
  - Keep thin-space/NBSP sanitization and legacy `\\\\$` cleanup.
- **Acceptance**:
  - `sanitize_text(r"\( x^2 \)")` → `"$ x^2 $"`
  - `sanitize_text(r"\[ x^2 \]")` → `"$$ x^2 $$"`
  - `sanitize_text(r"valor \(R$ 45\)")` → `"valor $R$ 45$"` — but wait, `(R$ 45)` is NOT LaTeX math, it's escaped parens. This is a false positive. Need to think harder...

- **Critical edge case**: `\(R$ 45\)` looks like a LaTeX inline math pair but the content is currency. The regex will convert it to `$R$ 45$` which gives three `$` signs — the first `$R$` is math, then ` 45$` tries to close but there's an extra `$`.

  **Decision**: Accept this as a known limitation. The LLM should not output `\(R$ 45\)` — `\(...\)` is a LaTeX math delimiter, and the LLM would only use it when the content IS math. If the user gets a bad render from this edge case, it's a prompt-engineering issue, not a code bug. The LLM should use `\$` for dollar signs inside `\(...\)` math blocks.

  However, a safer approach: **strip backslashes from unmatched `\(` and `\[`** rather than converting them. Unmatched `\(` → `(` (just remove the backslash). This prevents accidental math-block opening without losing the text.

### 2. Change streaming to minimal processing

- **File**: `src/ui/chat.py`, function `_stream_response()`
- **Changes**:
  - Remove `sanitize_text(token)` from the streaming generator.
  - Instead, use a minimal per-token processor that ONLY:
    - Collapses thin-space/NBSP (`\u202f` → ` `, `\u00a0` → ` `)
    - Strips legacy `\\\\$` → `$`
  - Create a new `sanitize_token()` function in `text_sanitize.py` or inline.
- **Acceptance**: Streaming shows LLM output as-is (with `\(...\)` visible during stream), then snaps to correct math rendering on completion.

### 3. Apply full `sanitize_text()` after streaming completes

- **File**: `src/ui/chat.py`, function `_stream_response()`
- **Changes**:
  - After `st.write_stream(safe_stream)` returns, call `sanitize_text(response)` and store the result.
  - This is already done; just ensure `sanitize_text` is now the paired-delimiter version.
- **Acceptance**: Stored content has `\(...\)` → `$...$` and `\[...\]` → `$$...$$` applied.

### 4. History rendering: apply `sanitize_text()` on rerun

- **File**: `src/ui/chat.py`, `render_chat_tab()`
- **Changes**:
  - Already applies `sanitize_text(content)` for assistant messages. No change needed.
- **Acceptance**: Old stored messages with raw `\(...\)` or `\[...\]` get properly converted on rerun.

### 5. Handle unmatched delimiters gracefully

- **File**: `src/text_sanitize.py`
- **Changes**:
  - After the paired-delimiter regex replacements, add a fallback pass:
    - Unmatched `\(` → `(` (just strip the backslash, keeping the paren)
    - Unmatched `\)` → `)`
    - Unmatched `\[` → `(`
    - Unmatched `\]` → `)`
  - This prevents single backslash-bracket from creating open math blocks.
- **Acceptance**: Text like `valores \(x, y, z\)` renders as `valores (x, y, z)`.

### 6. Update tests

- **File**: `tests/test_text_sanitize.py`
- **Changes**:
  - `test_converts_display_math_brackets`: still passes (paired conversion)
  - `test_converts_inline_math_parens`: still passes
  - **Add** `test_unmatched_brace_fallback`: `r"valor \(x"` → `"valor (x"`
  - **Add** `test_unmatched_display_fallback`: `r"nota \["` → `"nota ("`
  - **Add** `test_nested_does_not_cross`: `r"\(a\) and \(b\)"` → `"$a$ and $b$"` (two separate pairs, not one big match)
  - **Add** `test_lazy_matching`: `r"\[a\] b \[c\]"` → `"$$a$$ b $$c$$"`
  - Verify `test_does_not_touch_regular_brackets` still passes: `[note]` → `[note]`
- **Acceptance**: All new tests pass. No regressions.

### 7. Dead code cleanup

- **File**: `src/text_sanitize.py`
- **Changes**: Remove the 4 old standalone regex constants; replace with 2 paired ones.
- **Acceptance**: No unused imports or variables.

## Files to Modify

| File | Changes |
|------|---------|
| `src/text_sanitize.py` | Replace 4 regexes with 2 paired-delimiter regexes; add unmatched-brace fallback; keep whitespace/legacy cleanup |
| `src/ui/chat.py` | Split streaming processing: token-level only thin-space/NBSP/legacy; full `sanitize_text()` only on final string |
| `tests/test_text_sanitize.py` | Add 4 new test cases for edge cases; update existing tests where needed |

## New Files

None.

## Detailed Regex Specification

```
# Paired display math: \[...\] → $$...$$
_DISPLAY_PAIR_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)

# Paired inline math: \(...\) → $...$
_INLINE_PAIR_RE  = re.compile(r"\\\((.*?)\\\)", re.DOTALL)

# Unmatched openers (after pairs are consumed): strip backslash
_UNMATCHED_OPEN_RE  = re.compile(r"\\(?=[\[\(])")

# Unmatched closers: strip backslash  
_UNMATCHED_CLOSE_RE = re.compile(r"\\(?=[\]\)])")
```

Processing order in `sanitize_text()`:
1. Collapse whitespace (thin-space, NBSP)
2. Replace paired `\[...\]` → `$$...$$`
3. Replace paired `\(...\)` → `$...$`
4. Strip backslash from remaining unmatched `\(`, `\[`, `\)`, `\]`
5. Strip legacy `\\$` → `$`

## Streaming Architecture

```
LLM stream tokens
    │
    ▼
sanitize_token()  ─── only whitespace + legacy cleanup
    │
    ▼
st.write_stream()  ─── Streamlit natively handles $/$$ math across tokens
    │
    ▼
full_response (string)
    │
    ▼
sanitize_text()  ─── paired-delimiter conversion on complete string
    │
    ▼
store in st.session_state.messages
```

## Dependencies

- Task 2 depends on Task 1 (new `sanitize_token` in same module)
- Task 6 depends on Tasks 1-5 (tests validate the whole solution)
- Task 7 is cleanup, can be done anytime after Task 1

## Risks

1. **Lazy matching (`.*?`)**: If the LLM outputs very large math blocks (>10KB), `.*?` with DOTALL could have backtracking issues. Mitigation: set a reasonable `max_tokens` on the LLM call (already 800).
2. **False negatives for \(...\) math**: If math content contains `\)` literally (like closing a nested group), lazy matching will stop early. Example: `\(a(b)\)c\)` — the first `\)` closes at `b`, leaving `)c\)` unmatched. Mitigation: LLMs rarely nest `\)` inside `\(...\)`; if they do, they'd use `$...$` anyway.
3. **Streaming visual glitch**: During streaming, `\(x^2\)` will display as literal `\(x^2\)` (not math). Only after the stream completes and `sanitize_text` runs will it render as $x^2$. This causes a visual "snap" — jarring but correct. Mitigation: acceptable trade-off for correctness.
4. **Idempotency**: `sanitize_text` is called on stored content during rerun. Since `\(...\)` → `$...$`, a second call won't match (no more `\(` in the string). ✓
