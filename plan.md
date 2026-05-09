# Plano de Implementação — v1.6.1

Duas features: reorganização da aba Configurações e exibição do pensamento do modelo em tempo real no chat.

---

# Feature A — Reorganizar aba Configurações

## Objetivo

Reorganizar a aba Configurações em 3 seções claras: Modalidades (inalterada), Personalização (nova), Inteligência Artificial (renomeada). Melhorar o layout com colunas lado a lado e remover ruído visual (links desnecessários, asteriscos, observações).

## Diagnóstico atual

O arquivo `src/ui/settings.py` tem a função `_render_llm_section()` que acumula tudo numa seção só: meta mensal, nome, chave API, modelo, thinking, temperatura, prompt e botão salvar. Cada `st.subheader` cria uma separação visual fraca, sem hierarquia clara. A seção "Modalidades" está separada e correta.

## Tarefas

### A1. Extrair seção "Personalização" de `_render_llm_section()`

- **Arquivo**: `src/ui/settings.py`
- **Mudança**: Criar nova função `_render_personalization_section(conn, year_month)` contendo:
  - `st.subheader(":material/person: Personalização")`
  - Duas colunas: `col1, col2 = st.columns(2)`
  - Col1: `user_name = st.text_input("Seu nome", value=current_name, key="cfg_name", ...)`
  - Col2: `goal = st.number_input("Meta mensal (R$)", value=current_goal, key="cfg_goal", ...)`
- **Critério**: Nome e meta na mesma linha, título "Personalização" entre Modalidades e IA.

### A2. Renomear e limpar seção de IA

- **Arquivo**: `src/ui/settings.py`, função `_render_ai_section()` (renomeada de `_render_llm_section`)
- **Mudança**: 
  - `st.subheader(":material/smart_toy: IA — OpenRouter *")` → `st.subheader(":material/smart_toy: Inteligência Artificial")`
  - Remover `st.caption("[Obter chave gratuita no OpenRouter](https://openrouter.ai/keys)")`
  - Remover o asterisco e qualquer texto de observação associado
  - **Manter** a caption sobre o formato do slug do modelo (ex: `"Formato: provedor/modelo"`)
- **Critério**: Título limpo, sem link promocional, sem asterisco. Caption do slug mantida.

### A3. Chave API e Modelo lado a lado

- **Arquivo**: `src/ui/settings.py`, início de `_render_ai_section()`
- **Mudança**:
  ```python
  col_api, col_model = st.columns(2)
  with col_api:
      api_key = st.text_input("Chave API OpenRouter", type="password", ...)
  with col_model:
      llm_model = st.text_input("Modelo OpenRouter (slug completo)", ...)
  ```
  A validação `if llm_model and "/" not in llm_model` sobe para depois do input (continua igual).
  A caption sobre o slug se mantém abaixo do input do modelo.
- **Critério**: Chave e modelo na mesma linha. Link "Obter chave gratuita" removido.

### A4. Thinking toggle em linha própria

- **Arquivo**: `src/ui/settings.py`
- **Mudança**: Manter o toggle como está, mas ele ocupa a linha inteira após API/modelo. Adicionar `st.divider()` antes da linha de thinking para separar.
- **Critério**: Toggle visível, ocupa linha cheia.

### A5. Três colunas: esforço, temperatura, budget

- **Arquivo**: `src/ui/settings.py`
- **Mudança**:
  ```python
  col_effort, col_temp, col_budget = st.columns(3)
  with col_effort:
      thinking_effort = st.selectbox("Nível de esforço", ...)
  with col_temp:
      temperature = st.slider("Temperatura", 0.0, 2.0, 0.1, ...)
  with col_budget:
      use_budget = st.checkbox(
          "Usar orçamento exato de tokens (ignora esforço)",
          value=st.session_state.thinking_budget is not None,
      )
      thinking_budget = st.number_input(
          "Orçamento de tokens de reasoning",
          min_value=1024, max_value=32000, step=1024,
          value=st.session_state.thinking_budget or 32000,
          disabled=not use_budget,  # ← cinza/itálico quando desmarcado
      )
  ```
- **Importante**: `disabled=True` no `st.number_input` é nativo do Streamlit — rende o campo em cinza com texto itálico automaticamente. O campo **sempre visível**, não some. Isso satisfaz o requisito do usuário sem precisar de `streamlit-extras`.
- **Critério**: 
  - Budget sempre visível, mas desabilitado/cinza quando checkbox desmarcado.
  - Temperatura sempre visível, independente do thinking.
  - Esforço sempre visível quando thinking ligado.

### A6. Renomear "Prompt da IA" → "Prompt inicial"

- **Arquivo**: `src/ui/settings.py`
- **Mudança**: 
  - Label do `st.text_area`: `"Prompt da IA"` → `"Prompt inicial"`
  - Caption: manter `"Use {user_name} como placeholder para o nome do usuário."`
- **Critério**: Label atualizado.

### A7. Atualizar `render_settings_tab()` para chamar as novas funções

- **Arquivo**: `src/ui/settings.py`, função `render_settings_tab()`
- **Mudança**: 
  ```python
  def render_settings_tab(conn):
      ensure_settings(conn)
      today = date.today()
      year_month = today.isoformat()[:7]
      _render_modality_grid(conn)
      _render_personalization_section(conn, year_month)
      _render_ai_section(conn)
      _render_danger_zone()
  ```
- **Critério**: Nova ordem de renderização: Modalidades → Personalização → IA → Danger.

### A8. Atualizar assinatura de `_save_llm_settings()` (se necessário)

- **Arquivo**: `src/ui/settings.py`
- **Mudança**: `_save_llm_settings` já aceita todos os parâmetros necessários. Como `goal` agora é definido em `_render_personalization_section()`, o botão "Salvar configurações" em `_render_ai_section()` deve ler o valor do widget pela key `st.session_state.cfg_goal` (ou receber `goal` como argumento se preferir passar via `render_settings_tab()`). Ajustar a chamada no `on_click` do botão para incluir `goal`:
  ```python
  on_click=lambda: _save_llm_settings(
      conn, year_month,
      goal=st.session_state.cfg_goal,   # ← lido da key do widget
      user_name=st.session_state.cfg_name,
      ...
  )
  ```
- **Critério**: Botão salva tudo corretamente.

### A9. Rodar testes existentes

- **Comando**: `uv run pytest tests/ -v`
- **Critério**: 199 testes passando. Nenhum teste de settings quebrado (não há testes de UI para settings.py).

---

# Feature B — Mostrar pensamento do modelo em tempo real

## Objetivo

Substituir o status estático ":material/psychology: Processando..." por frases reais do pensamento do modelo, atualizadas em tempo real conforme os tokens de reasoning chegam. Ao final, o bloco de pensamento desaparece e fica só a resposta.

## Diagnóstico atual

- `generate_stream()` em `src/llm_client.py` captura `reasoning_content`/`reasoning` no `_reasoning_buffer` mas **yield apenas `content`** (strings).
- `_stream_response()` em `src/ui/chat.py` usa `st.write_stream(gerador_de_strings)` que só mostra conteúdo.
- O `placeholder.status("Processando...")` fica estático até o primeiro token de conteúdo chegar — com xhigh, isso demora >2 minutos.

## Abordagem

Modificar `generate_stream()` para yield tuplas `(tipo, valor)`. Em `_stream_response()`, usar um **wrapper generator** que trata reasoning como efeito colateral (atualiza o `st.status`) e passa content direto para `st.write_stream` — **zero mudança na renderização do conteúdo**.

```
generate_stream() → raw_stream: (tipo, token) tuplas
                              ↓
                     wrapper generator
                    ┌───────────────────┐
   reasoning → efeito colateral        content → yield token
   (atualiza st.status)                (passa direto)
                    └───────────────────┘
                              ↓
                     st.write_stream()
                   (comportamento idêntico ao atual)
```

## Tarefas

### B1. Modificar `generate_stream()` para yield tuplas

- **Arquivo**: `src/llm_client.py`, método `generate_stream()`, ~linha 305 (dentro do loop SSE)
- **Mudança**: 
  1. **Type hint**: alterar o retorno de  
     `Generator[str, None, None]` → `Generator[tuple[str, str], None, None]`
  2. **Loop SSE**:
  ```python
  # Antes:
  if content:
      yielded_any = True
      yield content
  
  # Depois:
  if content:
      yielded_any = True
      yield ("content", content)
  
  # E ANTES do `if content`, logo após capturar reasoning_token:
  if reasoning_token:
      self._reasoning_buffer.append(reasoning_token)
      yield ("reasoning", reasoning_token)  # ← NOVO
  ```
- **Importante**: 
  - O reasoning token é tanto acumulado no buffer (para `llm.reasoning` ao final) quanto yieldado (para exibição em tempo real).
  - A flag `yielded_any` continua sendo setada apenas para content (um stream 100% reasoning sem conteúdo ainda é válido, mas queremos detectar resposta vazia se nem reasoning nem content vierem — na prática, com DeepSeek V4 sempre vem reasoning primeiro).
- **Critério**: O generator agora produz tuplas `("reasoning", str)` e `("content", str)` e a assinatura de tipo reflete isso.

### B2. Atualizar docstring de `generate_stream()`

- **Arquivo**: `src/llm_client.py`
- **Mudança**: Atualizar `Yields` na docstring para refletir o novo formato:
  ```
  Yields:
      Tuplas (tipo, texto) onde tipo é "reasoning" (pensamento do modelo)
      ou "content" (resposta visível).
  ```
- **Critério**: Docstring reflete implementação.

### B3. Atualizar `_stream_response()` com wrapper generator

- **Arquivo**: `src/ui/chat.py`, função `_stream_response()`, ~linha 229
- **Mudança**: Manter `st.write_stream` para conteúdo. Usar um wrapper generator interno que captura reasoning como efeito colateral (atualiza `st.status`) e repassa tokens de content intocados:

  ```python
  def _stream_response(api_key: str, llm_model: str) -> None:
      _trim_history()
      with st.chat_message("assistant"):
          status_ph = st.empty()      # reasoning / status
          llm = LLMClient(api_key, model=llm_model)
          raw_stream = llm.generate_stream(
              st.session_state.messages,
              thinking_enabled=st.session_state.get("thinking_enabled", True),
              thinking_effort=st.session_state.get("thinking_effort"),
              thinking_budget=st.session_state.get("thinking_budget"),
              temperature=st.session_state.get("temperature", 0.3),
          )
          
          reasoning_acc = ""   # acumula p/ snippet no status
          
          def content_stream():
              """Wrapper: reasoning → side effect, content → pass through."""
              nonlocal reasoning_acc
              for token_type, token in raw_stream:
                  if token_type == "reasoning":
                      reasoning_acc += token
                      # Mostra últimos ~150 chars, truncado com "…"
                      snippet = reasoning_acc[-150:]
                      if len(reasoning_acc) > 150:
                          snippet = "…" + snippet
                      status_ph.status(
                          f":material/psychology: {snippet}",
                          expanded=False,
                      )
                  else:  # "content"
                      status_ph.empty()  # limpa reasoning
                      yield sanitize_token(token)
          
          safe_stream = content_stream()
          
          try:
              response = st.write_stream(safe_stream)
          except LLMUnavailableError:
              status_ph.empty()
              response = (
                  ":material/error: Não foi possível gerar a resposta. "
                  "Verifique sua conexão ou chave de API."
              )
              st.error(response)
          except Exception as exc:
              status_ph.empty()
              response = (
                  ":material/error: Erro inesperado ao gerar a resposta. "
                  f"Detalhes: {exc}"
              )
              st.error(response)
          
          clean_response = sanitize_text(response)
          msg: dict[str, Any] = {"role": "assistant", "content": clean_response}
          reasoning = llm.reasoning
          if reasoning:
              msg["reasoning"] = reasoning
          st.session_state.messages.append(msg)
  ```
- **Mudanças chave**:
  - `st.write_stream` **mantido** — a renderização de conteúdo é 100% idêntica à atual.
  - `status_ph = st.empty()` adicionado para o status de reasoning.
  - Wrapper generator `content_stream()`: reasoning → atualiza `status_ph.status()` como efeito colateral; content → `yield token` direto.
  - Quando o primeiro token de content chega: `status_ph.empty()` limpa o status de reasoning.
  - A linha `safe_stream = (sanitize_token(token) for token in stream)` é substituída por `safe_stream = content_stream()`.
  - O `sanitize_token` é aplicado dentro do wrapper, apenas nos tokens de content.
- **Critério**: 
  - Conteúdo renderizado de forma idêntica ao comportamento atual.
  - "Processando..." substituído por frases reais do pensamento (truncadas a 150 chars).
  - Layout não quebra (uma linha).
  - Ao final, status de some e fica só a resposta.

### B4. Atualizar **todos** os testes existentes de `generate_stream`

- **Arquivo**: `tests/test_llm_client.py`, classe `TestGenerateStream` e outros que chamam `generate_stream()`
- **Mudança**: **Todos** os testes que consomem `generate_stream()` esperavam strings puras. Agora precisam esperar tuplas `("content", str)` ou `("reasoning", str)`. Os 5 testes de reasoning precisam de asserts expandidos; os demais precisam apenas ajustar a comparação de tokens.

  **Testes de reasoning (5 testes — asserts expandidos):**

  `test_generate_stream_captures_reasoning_content` (linha 261):
  ```python
  # Antes:
  tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
  assert tokens == ["Resposta"]
  
  # Depois:
  tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
  content_tokens = [t for t_type, t in tokens if t_type == "content"]
  reasoning_tokens = [t for t_type, t in tokens if t_type == "reasoning"]
  assert content_tokens == ["Resposta"]
  assert reasoning_tokens == ["Pensando..."]  # reasoning agora é yieldado
  ```

  `test_generate_stream_captures_reasoning_field` (linha 277):
  Mesmo padrão: filtrar por tipo.

  `test_generate_stream_reasoning_and_content_same_delta` (linha 293):
  Verificar que ambos os tipos aparecem na lista de tuplas.

  `test_generate_stream_reasoning_none_when_no_tokens` (linha 308):
  Como não há reasoning tokens, verificar que todas as tuplas são `("content", ...)`.

  `test_generate_stream_reasoning_buffer_resets` (linha 323):
  Mesmo padrão, filtrar por tipo.

  **Testes de streaming geral (~14 testes — ajuste mecânico):**
  Todos os testes que fazem `assert tokens == ["Olá", " mundo"]` ou similar devem mudar para:
  ```python
  assert tokens == [("content", "Olá"), ("content", " mundo")]
  ```
  Exemplos: `test_generate_stream_success`, `test_generate_stream_yields_tokens`, `test_generate_stream_malformed_sse`, `test_generate_stream_delta_content_null`, `test_generate_stream_delta_content_empty_string`, `test_generate_stream_malformed_sse_top_level_array`, `test_generate_stream_done_with_whitespace`.

  **Testes de erro (4 testes — nenhuma mudança no assert de exceção, mas verificar que o generator ainda pode ser listado sem erro de tipo):**
  `test_generate_stream_timeout`, `test_generate_stream_connect_error`, `test_generate_stream_http_500`, `test_generate_stream_http_error`, `test_generate_stream_network_error`, `test_generate_stream_empty_response` — nenhum deles faz assert no conteúdo do token, mas `list()` ainda funciona com tuplas.

- **Critério**: Todos os testes de `generate_stream` passando.

### B5. Adicionar 2 novos testes para o formato de tuplas

- **Arquivo**: `tests/test_llm_client.py`

  **B5a. `test_generate_stream_yields_reasoning_and_content_tuples`:**
  ```python
  @respx.mock
  def test_generate_stream_yields_reasoning_and_content_tuples(self):
      """Tokens de reasoning e content são yieldados como tuplas (tipo, valor)."""
      route = respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"reasoning_content":"Pensando..."}}]}',
              'data: {"choices":[{"delta":{"content":"Ok"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
      assert tokens == [
          ("reasoning", "Pensando..."),
          ("content", "Ok"),
      ]
      assert llm.reasoning == "Pensando..."
      assert route.called
  ```

  **B5b. `test_generate_stream_content_only_no_reasoning_tuples`:**
  ```python
  @respx.mock
  def test_generate_stream_content_only_no_reasoning_tuples(self):
      """Sem reasoning, todas as tuplas são ("content", ...)."""
      route = respx.post(_OPENROUTER_URL).mock(
          return_value=_sse_chunks(
              'data: {"choices":[{"delta":{"content":"Plain"}}]}',
              "data: [DONE]",
          )
      )
      llm = LLMClient("sk-test", "test/model")
      tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
      assert all(t_type == "content" for t_type, _ in tokens)
      assert llm.reasoning is None
      assert route.called
  ```

- **Critério**: 2 novos testes passando.

### B6. Rodar suite completa

- **Comando**: `uv run pytest tests/ -v`
- **Critério**: 199 originais + 2 novos = **201 testes, zero falhas**.

---

## Arquivos modificados

| Arquivo | Feature | Mudanças |
|---------|---------|----------|
| `src/ui/settings.py` | A | Nova função `_render_personalization_section()`. Renomear `_render_llm_section()` → `_render_ai_section()`. Layout com `st.columns`. `disabled=True` no budget. Remover link OpenRouter. Renomear labels. Atualizar `render_settings_tab()`. |
| `src/llm_client.py` | B | `generate_stream()`: yield tuplas `(tipo, valor)` em vez de strings. Reasoning yieldado além de bufferizado. Docstring atualizada. |
| `src/ui/chat.py` | B | `_stream_response()`: wrapper generator `content_stream()`. Reasoning → efeito colateral no `status_ph.status()`. Content → yield direto para `st.write_stream`. Renderização de conteúdo idêntica à atual. |
| `tests/test_llm_client.py` | B | Atualizar 5 testes existentes para esperar tuplas. Adicionar 2 testes novos. |

## Arquivos NÃO modificados

| Arquivo | Motivo |
|---------|--------|
| `src/db.py` | Nenhuma mudança no schema ou queries. |
| `pyproject.toml` | Nenhuma dependência nova. |
| Outros arquivos em `src/ui/` | Apenas settings.py e chat.py afetados. |

---

## Dependências entre tarefas

```
Feature A (independente):
  A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 (sequencial, mesma função)

Feature B (dependente de B1):
  B1 → B4 (+ B2 em paralelo)
  B1 + B4 → B3
  B1 → B5
  B3 + B5 → B6
```

As duas features são **independentes** entre si — podem ser implementadas em paralelo.

---

## Riscos

1. **`disabled=True` no `st.number_input`**: Funciona nativamente no Streamlit ≥ 1.26. Nosso `pyproject.toml` exige `streamlit>=1.54.0` — sem risco. O campo fica cinza com texto itálico automaticamente.

2. **Interação `st.status()` dentro do wrapper generator**: O `status_ph.status()` é chamado como efeito colateral dentro do `content_stream()` que está sendo iterado por `st.write_stream`. Streamlit rerenderiza a cada yield — o status atualiza no mesmo ciclo, sem custo extra de rerun. Se houver flicker visual, throttlar atualizações de status (ex: a cada 3 tokens de reasoning).

3. **`yielded_any` só para content**: Se o modelo emitir APENAS reasoning (sem content), o stream termina com `LLMUnavailableError("Resposta vazia")`. Na prática isso não ocorre — DeepSeek sempre emite content após reasoning. Se ocorrer, o erro será visível pro usuário.

4. **Sem custo extra de reruns**: O `st.write_stream` já causa rerun a cada token de content. As atualizações de `status_ph.status()` acontecem no mesmo ciclo dos yields de reasoning — zero reruns adicionais em relação ao comportamento atual. Performance idêntica.

5. **Testes quebrados por mudança de formato**: **Todos** os ~19 testes que consomem `generate_stream()` precisam ser revisados. Os 5 de reasoning precisam de lógica nova (filtro por tipo); os ~14 restantes precisam trocar `assert tokens == ["foo"]` por `assert tokens == [("content", "foo")]`. O risco é esquecer algum teste na atualização mecânica.

6. **Type hints / mypy**: A assinatura de `generate_stream()` muda de `Generator[str, None, None]` para `Generator[tuple[str, str], None, None]`. O `mypy` pode reclamar de tipos em `_stream_response()` se a tupla não for desempacotada com anotação de tipo. Garantir que o desempacotamento `for token_type, token in stream:` seja suficientemente explícito para o mypy (costuma ser).

---

## Verificação final

```bash
uv run pytest tests/ -v  # 201 testes, zero falhas
uv run streamlit run app.py  # teste manual:
  # 1. Abrir Configurações → verificar 3 seções
  # 2. Configurar DeepSeek V4 com thinking xhigh
  # 3. Chat IA → ver frases de pensamento em tempo real
  # 4. Verificar resposta final sem texto de pensamento
```
