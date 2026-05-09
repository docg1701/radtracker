# Implementation Plan: DeepSeek V4 `reasoning_content` 400 error fix

## Goal

Make `LLMClient` capture reasoning tokens (`reasoning_content` / `reasoning`) from streaming SSE deltas, store them on assistant messages, and pass them back in subsequent multi-turn requests — model-agnostic, zero hardcoded provider checks.

## Background

DeepSeek V4 enables thinking mode by default. The API **requires** `reasoning_content` from the previous assistant message to be present in every subsequent request. Currently:

- `generate_stream()` only captures `delta.content` → ignores reasoning tokens
- `_stream_response()` stores only `{"role": "assistant", "content": ...}` → no reasoning field
- Next request lacks reasoning → DeepSeek returns 400, session unrecoverable

Pi.dev fixed this in commit [`c1dd608`](https://github.com/earendil-works/pi/commit/c1dd6082eef4a0b81877c178195decfa22a7d810) by capturing `reasoning_content` in the stream parser and preserving it on assistant messages.

## Tasks

### 1. Add reasoning buffer to `LLMClient.__init__`
- **File**: `src/llm_client.py`, ~line 234 (inside `__init__`, after `self._model = model`)
- **Change**: Add `self._reasoning_buffer: list[str] = []`
- **Acceptance**: Instance has attribute `_reasoning_buffer` initialized to empty list.

### 2. Add `reasoning` property to `LLMClient`
- **File**: `src/llm_client.py`, after `__init__`, before `generate_stream()` (~line 240)
- **Change**: Add property:
  ```python
  @property
  def reasoning(self) -> str | None:
      """Texto completo do reasoning acumulado no último generate_stream()."""
      joined = "".join(self._reasoning_buffer)
      return joined if joined else None
  ```
- **Acceptance**: `llm.reasoning` returns `None` before first stream; returns joined string after stream with reasoning tokens.

### 3. Reset buffer at start of `generate_stream()`
- **File**: `src/llm_client.py`, `generate_stream()` method, ~line 248 (first line after docstring)
- **Change**: Add `self._reasoning_buffer = []` as the first executable line of the method body.
- **Acceptance**: Each call to `generate_stream()` starts with a fresh buffer. Previous reasoning doesn't leak across calls.

### 4. Capture reasoning tokens in SSE parsing loop
- **File**: `src/llm_client.py`, `generate_stream()`, ~line 270 (inside the `try` block where `delta = ...`)
- **Change**: After `delta = (choice or {}).get("delta") or {}` and before `content = delta.get("content")`, add:
  ```python
  # Accumulate reasoning tokens from the delta.
  # DeepSeek V4 via OpenRouter uses "reasoning_content" in the native
  # format; other providers (Anthropic, Qwen, Gemini) use "reasoning"
  # as normalized by OpenRouter. Both are handled model-agnostically.
  reasoning_token = delta.get("reasoning_content") or delta.get("reasoning", "")
  if reasoning_token:
      self._reasoning_buffer.append(reasoning_token)
  ```
- **Acceptance**: 
  - Tokens from `delta.reasoning_content` are accumulated (DeepSeek native format)
  - Tokens from `delta.reasoning` are accumulated (OpenRouter normalized format)
  - `None`, `""`, or missing keys are safely ignored
  - Reasoning tokens and content tokens accumulate independently in parallel

### 5. Store reasoning in assistant message in `_stream_response()`
- **File**: `src/ui/chat.py`, `_stream_response()`, ~line 180 (where `clean_response` is stored)
- **Change**: Replace:
  ```python
  clean_response = sanitize_text(response)
  st.session_state.messages.append(
      {"role": "assistant", "content": clean_response}
  )
  ```
  With:
  ```python
  clean_response = sanitize_text(response)
  msg: dict[str, Any] = {"role": "assistant", "content": clean_response}
  reasoning = llm.reasoning
  if reasoning:
      msg["reasoning"] = reasoning
  st.session_state.messages.append(msg)
  ```
- **Acceptance**: 
  - When model returns reasoning tokens, the stored message includes `"reasoning"` field with full reasoning text
  - When model returns NO reasoning tokens, `"reasoning"` field is absent (not present at all)
  - `_trim_history()` preserves the `reasoning` field through message history (since it does `kept = user_assistant[-N:]` which passes dicts by reference)

### 6. Add test: reasoning capture from `reasoning_content` (DeepSeek format)
- **File**: `tests/test_llm_client.py`, in `TestGenerateStream` class
- **Change**: Add test:
  ```python
  @respx.mock
  def test_generate_stream_captures_reasoning_content(self):
      """reasoning_content tokens (DeepSeek native) are accumulated in buffer."""
      route = respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"reasoning_content":"Pensando...","content":null}}]}',
              'data: {"choices":[{"delta":{"content":"Resposta"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
      assert tokens == ["Resposta"]  # content tokens unchanged
      assert llm.reasoning == "Pensando..."
      assert route.called
  ```
- **Acceptance**: Test passes. `reasoning` property returns the accumulated reasoning text.

### 7. Add test: reasoning capture from `reasoning` field (OpenRouter normalized)
- **File**: `tests/test_llm_client.py`, in `TestGenerateStream` class
- **Change**: Add test:
  ```python
  @respx.mock
  def test_generate_stream_captures_reasoning_field(self):
      """reasoning tokens (OpenRouter normalized) are accumulated in buffer."""
      route = respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"reasoning":"Thinking...","content":null}}]}',
              'data: {"choices":[{"delta":{"content":"Answer"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
      assert tokens == ["Answer"]
      assert llm.reasoning == "Thinking..."
      assert route.called
  ```
- **Acceptance**: Test passes for providers using OpenRouter's `reasoning` field.

### 8. Add test: both reasoning and content in same delta
- **File**: `tests/test_llm_client.py`, in `TestGenerateStream` class
- **Change**: Add test:
  ```python
  @respx.mock
  def test_generate_stream_reasoning_and_content_same_delta(self):
      """When delta has both reasoning_content and content, both are captured."""
      route = respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"reasoning_content":"Think","content":"Out"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
      assert tokens == ["Out"]
      assert llm.reasoning == "Think"
      assert route.called
  ```
- **Acceptance**: Both reasoning and content tokens captured simultaneously.

### 9. Add test: reasoning property returns None when no reasoning tokens
- **File**: `tests/test_llm_client.py`, in `TestGenerateStream` class
- **Change**: Add test:
  ```python
  @respx.mock
  def test_generate_stream_reasoning_none_when_no_tokens(self):
      """reasoning property returns None when model doesn't emit reasoning."""
      route = respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"content":"Plain"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
      assert tokens == ["Plain"]
      assert llm.reasoning is None
      assert route.called
  ```
- **Acceptance**: `None` when no reasoning emitted.

### 10. Add test: reasoning buffer resets between calls
- **File**: `tests/test_llm_client.py`, in `TestGenerateStream` class
- **Change**: Add test:
  ```python
  @respx.mock
  def test_generate_stream_reasoning_buffer_resets(self):
      """Each generate_stream() call gets a fresh reasoning buffer."""
      respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"reasoning_content":"First"}}]}',
              'data: {"choices":[{"delta":{"content":"A"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      list(llm.generate_stream([{"role": "user", "content": "Q1"}]))
      assert llm.reasoning == "First"

      respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"content":"B"}}]}',
              "data: [DONE]",
          )
      )
      list(llm.generate_stream([{"role": "user", "content": "Q2"}]))
      assert llm.reasoning is None  # second call has no reasoning
  ```
- **Acceptance**: Buffer fully reset between calls; no cross-contamination.

### 11. Run full test suite
- **Command**: `uv run pytest tests/ -v`
- **Acceptance**: All existing 189 tests pass + 5 new tests pass = 194 total, zero failures.

## Files to Modify

| File | Changes |
|------|---------|
| `src/llm_client.py` | `__init__`: add `_reasoning_buffer` attribute. Add `reasoning` property. `generate_stream()`: reset buffer + capture reasoning tokens in SSE loop. |
| `src/ui/chat.py` | `_stream_response()`: after `st.write_stream()`, read `llm.reasoning` and include as `"reasoning"` field in stored assistant message. |
| `tests/test_llm_client.py` | 5 new tests in `TestGenerateStream`: reasoning_content capture, reasoning field capture, both in same delta, None when absent, buffer resets between calls. |

---

# Part 2 — Request-side reasoning & model configuration

## Background

Part 1 fixes the **response side** (capture and pass back `reasoning_content`).
Part 2 adds the **request side**: letting the user configure thinking on/off, effort
level, reasoning budget, and temperature from the Settings UI.

### Design principle: delegate to OpenRouter

OpenRouter provides a **unified API surface**. All provider-specific translation
happens server-side. Our client should:

- Send only OpenRouter-documented parameters — never provider-specific ones.
- Omit parameters that are optional (`max_tokens` is optional per the API spec).
- Let each model use its own natural defaults for output length.
- Expose only what the user needs to control: thinking, effort, budget, temperature.

### OpenRouter `reasoning` parameter (source: openrouter.ai/docs/api/reference/parameters)

```json
{
  "reasoning": {
    "effort": "high",       // "xhigh"|"high"|"medium"|"low"|"minimal"|"none"
    "max_tokens": 2000,     // integer, mutually exclusive with effort
    "exclude": false,       // strip reasoning from response (we don't expose)
    "enabled": true         // toggle, all models
  }
}
```

- `effort` and `max_tokens` are **mutually exclusive** — provide exactly one, never both.
- `enabled: false` disables reasoning for **all models**.
- `exclude: true` strips tokens from response → breaks multi-turn DeepSeek (we never send it).
- OpenRouter translates `effort` ↔ `max_tokens` across providers automatically.

### Why we don't send `max_tokens` (output limit)

`max_tokens` is **optional** per the OpenRouter spec. When omitted:
- Each model uses its own natural default or maximum for output length.
- No risk of truncation for models with high output ceilings (DeepSeek V4: 384K).
- No risk of credit over-reservation for models with low ceilings.

Sending a fixed `max_tokens` value would either castrate high-ceiling models or
over-reserve credits on low-ceiling ones. Omission is the correct default.

## Tasks

### 12. Add DB columns for reasoning settings
- **File**: `src/db.py`, `init_db()` function
- **Change**: Seed new keys via `save_setting()` in a one-shot migration called from
  `ensure_settings()` (simpler than ALTER TABLE):
  ```python
  for key, default in [
      ("thinking_enabled", "1"),
      ("thinking_effort", "high"),
      ("thinking_budget", ""),        # empty = not set (effort takes precedence)
      ("temperature", "0.3"),
  ]:
      if not load_setting(conn, key):
          save_setting(conn, key, default)
  ```
- **Acceptance**: `load_setting(conn, 'thinking_enabled')` returns `'1'` after migration.

### 13. Load reasoning settings in `ensure_settings()`
- **File**: `src/ui/settings.py`, `ensure_settings()` (~line 30)
- **Change**: Add after the existing setting loads:
  ```python
  if "thinking_enabled" not in st.session_state:
      raw = load_setting(conn, "thinking_enabled", "1")
      st.session_state.thinking_enabled = raw in ("1", "true", "True")
  if "thinking_effort" not in st.session_state:
      st.session_state.thinking_effort = load_setting(conn, "thinking_effort", "high")
  if "thinking_budget" not in st.session_state:
      raw = load_setting(conn, "thinking_budget", "")
      st.session_state.thinking_budget = int(raw) if raw else None
  if "temperature" not in st.session_state:
      st.session_state.temperature = float(load_setting(conn, "temperature", "0.3"))
  ```
- **Acceptance**: Session state carries reasoning config after first tab render.

### 14. Render reasoning config UI in Settings tab
- **File**: `src/ui/settings.py`, `_render_llm_section()` (~line 195), inside the
  `@st.fragment`
- **Change**: Add after the LLM model input, before the prompt text area:
  ```python
  st.subheader(":material/psychology: Thinking (reasoning)")

  thinking_enabled = st.toggle(
      "Ativar thinking mode",
      value=st.session_state.thinking_enabled,
      help="Modelo gera raciocínio interno antes da resposta. "
           "Mais qualidade analítica, maior custo de tokens.",
  )

  if thinking_enabled:
      thinking_effort = st.selectbox(
          "Nível de esforço",
          options=["low", "medium", "high", "xhigh"],
          index=["low", "medium", "high", "xhigh"].index(
              st.session_state.thinking_effort
          ),
          help="Controla quantos tokens o modelo gasta pensando. "
               "xhigh = análise mais profunda. "
               "O OpenRouter traduz para o formato nativo de cada modelo.",
      )

      thinking_budget = st.number_input(
          "Ou: orçamento exato de tokens de reasoning",
          min_value=1024, max_value=32000, step=1024,
          value=st.session_state.thinking_budget or 32000,
          help="Alternativa ao nível de esforço. "
               "Se preenchido, o esforço é ignorado. "
               "O OpenRouter traduz para o formato nativo de cada modelo.",
      )
  else:
      thinking_effort = None
      thinking_budget = None

  st.subheader(":material/thermostat: Temperatura")
  temperature = st.slider(
      "Temperatura",
      min_value=0.0, max_value=2.0, step=0.1,
      value=st.session_state.get("temperature", 0.3),
      help="Controla aleatoriedade (0 = determinístico, 2 = criativo). "
           "Alguns modelos ignoram com thinking ligado. "
           "Recomendado: 0.3 para análises.",
  )
  ```
- **Acceptance**: Settings tab shows thinking toggle, effort selector, budget input,
  and temperature slider. Zero provider-specific language.

### 15. Save reasoning config on "Salvar configurações"
- **File**: `src/ui/settings.py`, `_render_llm_section()` button callback and
  `_save_llm_settings()` function (~line 210)
- **Change**: Update the button's `on_click` lambda to pass new values, and update
  `_save_llm_settings()` signature and body:
  ```python
  def _save_llm_settings(
      conn, year_month, goal, user_name, api_key, llm_model, system_prompt,
      thinking_enabled, thinking_effort, thinking_budget, temperature,
  ) -> None:
      # ... existing saves ...
      save_setting(conn, "thinking_enabled", "1" if thinking_enabled else "0")
      if thinking_effort:
          save_setting(conn, "thinking_effort", thinking_effort)
      if thinking_budget is not None:
          save_setting(conn, "thinking_budget", str(thinking_budget))
      save_setting(conn, "temperature", str(temperature))

      st.session_state.thinking_enabled = thinking_enabled
      st.session_state.thinking_effort = thinking_effort
      st.session_state.thinking_budget = thinking_budget
      st.session_state.temperature = temperature
  ```
- **Acceptance**: All reasoning settings persist across page reloads.

### 16. Thread reasoning config into `LLMClient.generate_stream()`
- **File**: `src/llm_client.py`, `generate_stream()` method (~line 248)
- **Change**: Accept new optional parameters:
  ```python
  def generate_stream(
      self,
      messages: list[dict[str, str]],
      thinking_enabled: bool = True,
      thinking_effort: str | None = None,   # low|medium|high|xhigh
      thinking_budget: int | None = None,   # 1024–32000
      temperature: float = 0.3,
  ) -> Generator[str, None, None]:
  ```
  All new params default to current behavior so existing callers don't break.
- **Acceptance**: Method signature extended without breaking existing tests.

### 17. Build `reasoning` object in `_build_payload()`
- **File**: `src/llm_client.py`, `_build_payload()` (~line 306)
- **Change**: Accept and use the new params. Build `reasoning` object following
  OpenRouter's mutual-exclusivity rules. Do NOT send `max_tokens` (let the model
  decide its output ceiling):
  ```python
  def _build_payload(
      self, messages, stream=False,
      thinking_enabled=True,
      thinking_effort=None, thinking_budget=None, temperature=0.3,
  ) -> dict[str, Any]:
      payload: dict[str, Any] = {
          "model": self._model,
          "messages": messages,
          "stream": stream,
          "temperature": temperature,
      }

      if not thinking_enabled:
          payload["reasoning"] = {"enabled": False}
      elif thinking_budget:
          payload["reasoning"] = {"max_tokens": thinking_budget}
      elif thinking_effort:
          payload["reasoning"] = {"effort": thinking_effort}
      # else: no reasoning key → model default behavior

      return payload
  ```
- **Acceptance**: Payload includes correct `reasoning` object. No `max_tokens` sent.
  Budget takes precedence over effort when both are set.

### 18. Update `_stream_response()` to pass config to `generate_stream()`
- **File**: `src/ui/chat.py`, `_stream_response()` (~line 250)
- **Change**: Read config from `st.session_state` and pass to `llm.generate_stream()`:
  ```python
  stream = llm.generate_stream(
      st.session_state.messages,
      thinking_enabled=st.session_state.get("thinking_enabled", True),
      thinking_effort=st.session_state.get("thinking_effort"),
      thinking_budget=st.session_state.get("thinking_budget"),
      temperature=st.session_state.get("temperature", 0.3),
  )
  ```
- **Acceptance**: Chat uses user's reasoning config from Settings.

### 19. Add tests for reasoning payload construction
- **File**: `tests/test_llm_client.py`, new test class or extend existing
- **Changes**: Five new tests:

  **19a. `test_build_payload_no_max_tokens_sent`:**
  ```python
  def test_build_payload_no_max_tokens_sent(self):
      """max_tokens is never sent — model uses its own default."""
      llm = LLMClient("sk-test", "test/model")
      payload = llm._build_payload([], stream=False)
      assert "max_tokens" not in payload
  ```

  **19b. `test_build_payload_reasoning_omitted_by_default`:**
  ```python
  def test_build_payload_reasoning_omitted_by_default(self):
      """With thinking enabled and no effort/budget, no reasoning key."""
      llm = LLMClient("sk-test", "test/model")
      payload = llm._build_payload(
          [], stream=False, thinking_enabled=True,
      )
      assert "reasoning" not in payload
  ```

  **19c. `test_build_payload_reasoning_disabled`:**
  ```python
  def test_build_payload_reasoning_disabled(self):
      llm = LLMClient("sk-test", "test/model")
      payload = llm._build_payload(
          [], stream=False, thinking_enabled=False,
      )
      assert payload["reasoning"] == {"enabled": False}
      assert "max_tokens" not in payload
  ```

  **19d. `test_build_payload_reasoning_effort`:**
  ```python
  def test_build_payload_reasoning_effort(self):
      llm = LLMClient("sk-test", "test/model")
      payload = llm._build_payload(
          [], stream=False,
          thinking_enabled=True, thinking_effort="xhigh",
      )
      assert payload["reasoning"] == {"effort": "xhigh"}
      assert "max_tokens" not in payload
  ```

  **19e. `test_build_payload_reasoning_budget`:**
  ```python
  def test_build_payload_reasoning_budget(self):
      llm = LLMClient("sk-test", "test/model")
      payload = llm._build_payload(
          [], stream=False,
          thinking_enabled=True, thinking_budget=32000,
      )
      assert payload["reasoning"] == {"max_tokens": 32000}
      assert "max_tokens" not in payload
  ```

- **Acceptance**: Five tests pass, verifying: no max_tokens sent, reasoning omitted
  by default, disabled, effort, and budget configurations.

### 20. Run full test suite
- **Command**: `uv run pytest tests/ -v`
- **Acceptance**: 189 original + 5 (Part 1) + 5 (Part 2) = **199 tests, zero failures.**

## Files to Modify (Part 2)

| File | Changes |
|------|---------|
| `src/db.py` | Seed new `user_settings` keys: `thinking_enabled`, `thinking_effort`, `thinking_budget`, `temperature`. |
| `src/ui/settings.py` | `ensure_settings()`: load new keys into session state. `_render_llm_section()`: render thinking toggle, effort, budget, temperature UI. `_save_llm_settings()`: persist new keys. |
| `src/llm_client.py` | `generate_stream()`: accept new optional params. `_build_payload()`: build `reasoning` object from params; never send `max_tokens`. |
| `src/ui/chat.py` | `_stream_response()`: read config from session state and pass to `generate_stream()`. |
| `tests/test_llm_client.py` | 5 new tests for `_build_payload` reasoning logic + no max_tokens invariant. |

## Risk Analysis

1. **OpenRouter field name inconsistency** (Part 1): OpenRouter may normalize the reasoning field as `reasoning` in the delta for some providers and as `reasoning_content` for others (especially DeepSeek passthrough). Our dual capture handles both. **Mitigation**: tests 6 and 7 explicitly verify both field names.

2. **`_trim_history()`** (Part 1): copies message dicts by reference, so `reasoning` field is naturally preserved. **Mitigation**: no action needed now.

3. **DeepSeek intermittent omission of `reasoning_content`** (Part 1): if DeepSeek omits reasoning_content in a turn, the assistant message won't have `reasoning`, and the next request won't send it back. **Mitigation**: DeepSeek server-side bug tracked by OpenRouter. Our code handles the happy path and degrades gracefully.

4. **`exclude: true` breaks multi-turn DeepSeek** (Part 2): we do NOT expose `exclude` in the UI. The only way to get this state is manual DB editing.

5. **Temperature silently ignored by some models with thinking on**: DeepSeek ignores it; Anthropic and Gemini respect it. **Mitigation**: tooltip says "Alguns modelos ignoram com thinking ligado." Value is always sent (harmless when ignored).

6. **Credit-spend risk from omitting `max_tokens`**: Without an explicit output cap,
   a high-ceiling model (DeepSeek V4: 384K) could generate an unexpectedly long
   response, consuming significant credits. **Mitigation**: models naturally stop
   when their response is complete; radtracker use case (productivity analysis)
   rarely exceeds 2K–4K visible tokens. Monitor and re-add a generous `max_tokens`
   cap if runaway responses are observed.

---

# Part 3 — Release & Deploy

After all 20 tasks are implemented and the full test suite passes (199 tests):

1. **Bump version**: tag `v1.6.0` (minor bump — new reasoning capture + Settings UI features).
2. **Create GitHub release** with changelog covering Part 1 (400 error fix) and Part 2 (thinking/effort/budget/temperature configuration).
3. **Deploy to VPS** `10.10.10.209` via Ansible:
   ```bash
   export VPS_HOST=10.10.10.209 VPS_USER=galvani
   ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
     --vault-password-file ansible/.vault_pass
   ```
4. **Smoke test**: configure DeepSeek V4 in Settings, iniciar chat, fazer pergunta de múltiplos turnos, verificar que não há erro 400 e que o output não está truncado.
