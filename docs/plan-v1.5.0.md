# plan-v1.5.0.md — Chat com IA (RAG + OpenRouter streaming)

**Status:** em planejamento  
**Release alvo:** v1.5.0  
**Base:** v1.4.0 (modalidades configuráveis)  
**Dependência:** v1.4.0 deve estar concluída antes de iniciar

---

## Objetivo

Substituir o botão one-shot "Perguntar à IA" por uma interface de chat completa:
- Primeiro prompt injeta os stats como contexto (RAG)
- Resposta inicial em streaming (token por token)
- Chat interativo para perguntas de follow-up
- Histórico completo da conversa visível
- O usuário nunca mais precisa ir em Settings mudar o prompt manualmente

---

## Escopo

### O que entra

| # | Funcionalidade | Descrição |
|---|---------------|-----------|
| 1 | Chat UI | Nova aba "💬 Chat IA" com `st.chat_message` + `st.chat_input` |
| 2 | Streaming SSE | `st.write_stream()` exibe tokens conforme chegam do OpenRouter |
| 3 | RAG (context injection) | Stats do `compute_historical_stats()` injetados no system prompt |
| 4 | Histórico da conversa | Persistido em `st.session_state.messages` durante a sessão |
| 5 | Trigger automático | Ao abrir a aba Chat, o relatório inicial já começa a ser gerado |
| 6 | Sugestões de follow-up | Pills com perguntas sugeridas após o primeiro relatório |
| 7 | Botão "Novo relatório" | Regenera o contexto RAG com dados frescos |
| 8 | `LLMClient.generate_stream()` | Novo método que faz POST com `stream: true` e faz yield de tokens |

### O que NÃO entra

- Persistência do histórico entre sessões (opcional futuro: JSON em user_settings)
- Upload de arquivos no chat
- Múltiplas conversas / tópicos
- Ferramentas / function calling
- Embeddings ou vector DB (não necessário — RAG é context injection simples)

---

## Arquivos afetados

| Arquivo | Mudança |
|---------|---------|
| `app.py` | Adicionar 5ª aba "💬 Chat IA" na navegação |
| `src/ui/chat.py` | **NOVO** — módulo completo da interface de chat |
| `src/llm_client.py` | Adicionar `generate_stream()`, refatorar `generate()` para reusar lógica |
| `tests/test_llm_client.py` | Testes para `generate_stream()` com mock SSE |
| `tests/test_chat.py` | **NOVO** — testes para o módulo de chat (se viável) |
| `src/cookies.py` | Atualizar `TAB_LABELS` (se referenciado) para incluir nova aba |

### Arquivos NÃO afetados

- `src/db.py` — sem mudanças no schema (histórico fica em session_state)
- `src/ui/analysis.py` — a seção IA existente pode ser removida ou simplificada
- `src/calculations.py` — sem mudanças
- `src/charts*.py` — sem mudanças
- `src/ui/sidebar.py`, `src/ui/today.py`, `src/ui/month.py`, `src/ui/settings.py` — sem mudanças

---

## Design detalhado

### 1. Nova aba "💬 Chat IA"

**app.py** — Adicionar 5ª aba:

```python
TAB_LABELS = [
    ":material/today: Hoje",
    ":material/calendar_month: Mês Atual",
    ":material/trending_up: Análise",
    ":material/smart_toy: Chat IA",        # NOVA
    ":material/settings: Configuração",
]
```

Mapeamento:
```python
elif selected_idx == 3:
    from src.ui.chat import render_chat_tab
    render_chat_tab(conn)
```

### 2. Estrutura do módulo `src/ui/chat.py`

```
src/ui/chat.py
├── render_chat_tab(conn)          # Entry point chamado por app.py
├── _stream_assistant_response()   # Dispatcher: pending check → LLM call → st.write_stream → append
├── _render_suggestion_chips()     # Pills de follow-up
└── _clear_chat()                  # Callback do botão limpar
```

### 3. Fluxo da interface

```
Usuário clica na aba "Chat IA"
  → ensure_settings(conn) para carregar api_key, model, etc.
  → Se api_key vazia: mostrar mensagem "Configure sua chave API em Configuração"
  → Se já existe histórico em session_state.messages: mostrar conversa existente
  → Se NÃO existe histórico:
      → Calcular stats (compute_historical_stats) — usa cache já existente
      → Montar contexto RAG (system prompt + dados dos stats)
      → Iniciar streaming da resposta inicial
      → Exibir token por token via st.write_stream()
      → Adicionar resposta ao histórico

Usuário digita pergunta no st.chat_input
  → Append mensagem "user" ao histórico
  → Exibir bolha "user"
  → Iniciar streaming da resposta
  → Exibir bolha "assistant" com tokens
  → Append resposta ao histórico

Usuário clica em sugestão
  → Append mensagem "user" ao histórico
  → st.rerun()
  → Na re-execução, o dispatcher detecta messages[-1]["role"] == "user"
      e NÃO há resposta assistant correspondente
  → Inicia streaming automaticamente

**Dispatcher de mensagens pendentes** (crítico para pills):

```python
# No topo de render_chat_tab(), após exibir o histórico:
pending = (
    st.session_state.messages
    and st.session_state.messages[-1]["role"] == "user"
)
if pending:
    with st.chat_message("assistant"):
        llm = LLMClient(api_key, model=llm_model)
        stream = llm.generate_stream(st.session_state.messages)
        try:
            response = st.write_stream(stream)
        except LLMUnavailableError:
            response = "❌ Não foi possível gerar a resposta."
            st.error(response)
        st.session_state.messages.append(
            {"role": "assistant", "content": response}
        )
    st.rerun()  # exibe a resposta e volta ao estado estável
```

Usuário clica "Novo relatório"
  → Limpar histórico
  → Recalcular stats
  → Gerar novo relatório inicial
```

### 4. Estrutura do histórico de mensagens

```python
st.session_state.messages = [
    {"role": "system", "content": "Você é um assistente... Dados do mês: ..."},  # oculto na UI
    {"role": "assistant", "content": "## Relatório de Produtividade\n\n..."},     # relatório inicial
    {"role": "user", "content": "Qual foi o dia mais produtivo?"},
    {"role": "assistant", "content": "O dia mais produtivo foi..."},
]
```

A primeira mensagem `system` contém o contexto RAG completo e NÃO é exibida na UI.
As demais são exibidas normalmente.

### 5. RAG — Context injection via public API

**IMPORTANTE:** `chat.py` NÃO deve importar símbolos privados (`_enrich_stats`,
`_USER_PROMPT_TEMPLATE`, `_SYSTEM_PROMPT`) de `llm_client.py`. Em vez disso,
`llm_client.py` expõe uma **função pública**:

```python
# src/llm_client.py — NOVA função pública
def build_rag_context(
    stats: dict[str, Any],
    active_mods: list[dict[str, Any]],
    system_prompt: str | None = None,
) -> str:
    """Monta o system prompt com dados estruturados dos stats para RAG.

    Args:
        stats: Dict de compute_historical_stats().
        active_mods: Lista de modalidades ativas.
        system_prompt: Prompt personalizado do usuário (settings).
                       Se None, usa o default interpolado com user_name.

    Returns:
        String completa do system prompt com contexto RAG injetado.
    """
    enriched = _enrich_stats(stats, active_mods)
    user_prompt = _USER_PROMPT_TEMPLATE.format(**enriched)
    prompt = system_prompt or _SYSTEM_PROMPT
    return f"""{prompt}

=== DADOS ATUAIS PARA ANÁLISE ===
Os dados abaixo são o contexto da conversa. Use-os para responder perguntas.
Quando o usuário pedir "relatório", gere uma análise completa com esses dados.

{user_prompt}
"""
```

`chat.py` importa apenas `build_rag_context` (público) e `LLMClient`/`LLMUnavailableError`.
O `system_prompt` é sempre obtido de `st.session_state.llm_prompt` (populado por
`ensure_settings()`), nunca do fallback hardcoded em `llm_client.py`.

### 6. Streaming — `LLMClient.generate_stream()`

Novo método no `LLMClient`:

```python
def generate_stream(
    self,
    messages: list[dict[str, str]],
) -> Generator[str, None, None]:
    """Chama OpenRouter com stream=True e faz yield de tokens.

    Args:
        messages: Lista completa de mensagens (system + user + assistant).
            O chamador é responsável por incluir o system prompt com RAG context.

    Yields:
        Tokens de texto conforme chegam via SSE.

    Raises:
        LLMUnavailableError: timeout, HTTP error, ou rate limit.
    """
    payload = {
        "model": self._model,
        "messages": messages,
        "stream": True,
        "max_tokens": 800,
        "temperature": 0.3,
    }
    try:
        with httpx.stream(
            "POST",
            _OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,  # 30s para connect + read (vs 15s do não-streaming)
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue  # ignora linhas malformadas
    except httpx.TimeoutException:
        raise LLMUnavailableError("Timeout ao chamar OpenRouter (30s)") from None
    except httpx.HTTPStatusError as exc:
        raise LLMUnavailableError(
            f"OpenRouter HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        # Captura ConnectError, NetworkError, etc.
        raise LLMUnavailableError(
            f"Erro de conexão com OpenRouter: {exc}"
        ) from exc
```

**Nota:** `httpx.stream()` faz streaming da resposta HTTP. O OpenRouter envia SSE no formato:
```
data: {"choices":[{"delta":{"content":"Olá"}}]}

data: {"choices":[{"delta":{"content":" mundo"}}]}

data: [DONE]
```

### 7. Integração com `st.write_stream()` + tratamento de erros

```python
with st.chat_message("assistant"):
    try:
        stream = llm.generate_stream(messages_to_send)
        response = st.write_stream(stream)
    except LLMUnavailableError:
        response = (
            "❌ Não foi possível gerar a resposta. "
            "Verifique sua conexão ou chave de API."
        )
        st.error(response)
    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )
```

O `try/except` captura falhas de streaming (rede caiu no meio da resposta,
modelo indisponível, etc.) e renderiza uma mensagem de erro amigável dentro
da bolha do assistant, sem quebrar o restante da página.

### 8. Sugestões de follow-up

Após a resposta inicial, exibir pills com perguntas sugeridas:

```python
SUGGESTIONS = [
    "Qual dia foi mais produtivo?",
    "Minha média é consistente?",
    "Como está o mix de modalidades?",
    "Qual a projeção para fechar o mês?",
    "Compare esta semana com a anterior",
]

# Só mostra quando há pelo menos 1 mensagem no histórico
if len(st.session_state.messages) >= 2:  # system + assistant
    selected = st.pills(
        "Sugestões de perguntas:",
        SUGGESTIONS,
        label_visibility="collapsed",
        key="chat_suggestions",
    )
    if selected:
        # Trata como se o usuário tivesse digitado
        st.session_state.messages.append({"role": "user", "content": selected})
        st.rerun()
```

### 9. Botão "Novo relatório" e limpar chat

```python
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("📊 Novo relatório", type="secondary"):
        # Recalcula stats e gera novo relatório inicial
        st.session_state.messages = []
        st.session_state.pop("historical_cache", None)
        st.rerun()
with col2:
    if st.button("🗑️ Limpar chat", type="secondary"):
        st.session_state.messages = []
        st.rerun()
```

---

## O que acontece com a IA na aba "Análise"?

**Opção A (recomendada):** Substituir o botão atual por um link/atalho para a aba Chat:
```python
st.button(
    "💬 Abrir Chat com IA",
    on_click=lambda: st.session_state.update(active_tab_idx=3),
)
```
Isso evita duplicação de funcionalidade e direciona o usuário para a experiência completa.

**Opção B:** Manter o botão one-shot como fallback rápido, renomeado para "Análise rápida".
Não recomendado — confunde o usuário com duas interfaces diferentes para a mesma coisa.

---

## Plano de implementação (ordem)

### Fase 1: Backend — streaming
- [ ] `build_rag_context(stats, active_mods, system_prompt)` — **função pública** em `llm_client.py`
- [ ] `LLMClient.generate_stream(messages)` — método de streaming via SSE
- [ ] Refatorar `LLMClient` para compartilhar payload builder entre `generate()` e `generate_stream()`

### Fase 2: Testes — streaming
- [ ] `test_generate_stream_yields_tokens` — mock httpx.stream com respx (ver padrão abaixo)
- [ ] `test_generate_stream_empty_response`
- [ ] `test_generate_stream_http_error`
- [ ] `test_generate_stream_network_error` — ConnectError vira LLMUnavailableError
- [ ] `test_generate_stream_timeout`
- [ ] `test_generate_stream_malformed_sse` — JSON inválido, `choices` ausente
- [ ] `test_generate_stream_delta_content_null` — `delta.content` explicitamente `null`
- [ ] `test_generate_stream_done_with_whitespace` — `[DONE]` com espaços extras
- [ ] `test_build_rag_context_includes_stats`
- [ ] `test_build_rag_context_respects_custom_prompt`

**Padrão de mock SSE com respx:**

```python
import httpx
import respx

def _sse_chunks(*lines: str):
    """Helper: gera bytes de SSE a partir de strings."""
    return httpx.Response(
        200,
        content="\n".join(lines).encode("utf-8"),
    )

@respx.mock
def test_generate_stream_yields_tokens():
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=_sse_chunks(
            'data: {"choices":[{"delta":{"content":"Olá"}}]}',
            'data: {"choices":[{"delta":{"content":" mundo"}}]}',
            "data: [DONE]",
        )
    )
    llm = LLMClient("sk-test")
    tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
    assert tokens == ["Olá", " mundo"]
```

### Fase 3: Frontend — chat UI
- [ ] Novo arquivo `src/ui/chat.py`
- [ ] `render_chat_tab(conn)` — estrutura principal
- [ ] Exibir histórico de mensagens com `st.chat_message`
- [ ] `st.chat_input()` para capturar perguntas
- [ ] Integração com `generate_stream()` e `st.write_stream()`
- [ ] Sugestões de follow-up com `st.pills`
- [ ] Botões "Novo relatório" e "Limpar chat"
- [ ] Estado: sem API key → mensagem amigável

### Fase 4: Integração — app.py + aba Análise
- [ ] Adicionar 5ª aba no `app.py`
- [ ] Substituir `_render_ai_section()` na aba Análise por atalho para o Chat
- [ ] Remover decorator `@st.fragment` de `_render_ai_section()` (função vira botão simples)
- [ ] Limpar chaves órfãs do `session_state`: `llm_insight_text`, `llm_insight_pending`, `llm_insight_in_flight`, `llm_insight_cancelled`
- [ ] **NÃO** atualizar `cookies.py` — bounds check em `app.py` já trata o shift de índices

### Fase 5: Testes manuais + qualidade
- [ ] `uv run streamlit run app.py` — testar fluxo completo
- [ ] Abrir Chat IA → relatório inicial aparece em streaming
- [ ] Fazer pergunta de follow-up → resposta contextualizada
- [ ] Clicar em sugestão → pergunta enviada
- [ ] Clicar "Novo relatório" → dados frescos
- [ ] `uv run ruff check src/ tests/`
- [ ] `uv run mypy src/`
- [ ] `uv run pytest tests/ -v`

---

## Riscos e mitigações

| Risco | Prob. | Impacto | Mitigação |
|-------|-------|---------|-----------|
| SSE parsing quebrado por formato inesperado | Média | Alto | `try/except` por linha; `delta.content` null tratado; `[DONE]` com whitespace aceito; `data.get("choices", [{}])` seguro |
| `st.write_stream()` não funciona com generator customizado | Baixa | Médio | Streamlit ≥1.54 documenta suporte. Fallback: acumular tokens e exibir de uma vez |
| Stats desatualizados entre mensagens | Baixa | Baixo | Aceitável para a sessão. Botão "Novo relatório" resolve |
| Histórico muito longo → token limit excedido | Média | Médio | **Regra concreta:** system prompt + últimas 10 mensagens (5 pares). Assumir modelo ≥32k tokens. Descartar pares antigos FIFO |
| Conexão cai durante streaming (ConnectError/NetworkError) | Média | Alto | `except httpx.HTTPError` amplo em `generate_stream()`; `try/except` no `st.write_stream()` renderiza erro inline |
| Conflito com `st.rerun()` ao processar streaming | Alta | Alto | Usar `@st.fragment` para isolar o chat do resto da página |
| Cookie de aba com índice antigo no upgrade v1.4→v1.5 | Baixa | Baixo | `app.py` tem bounds check (`0 <= idx < len(TAB_LABELS)`); não quebra. Documentar no release notes |

---

## Decisões de design

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| Onde colocar o chat? | **Nova aba "💬 Chat IA"** | Isola o estado conversacional; não polui a aba Análise já cheia de charts |
| Streaming vs batch? | **Streaming** | Reduz percepção de demora; nativo no Streamlit; OpenRouter suporta |
| Persistir histórico? | **Session state apenas** (v1.5.0) | Simples; sem mudanças no schema. Persistência em DB fica para v1.6.0 |
| O que fazer com a IA na Análise? | **Substituir por atalho** | Evita duplicação; experiência única de chat |
| Contexto RAG | **System prompt enriquecido** | Sem vector DB; os stats já são dados estruturados; o modelo entende |
| Modelo padrão | **Manter configurável** (settings) | Usuário já configura o modelo em Configuração |

---

## Constantes e convenções

- Aba Chat: índice 3 (Análise é 2, Configuração é 4)
- Prompt inicial max_tokens: 800 (igual ao one-shot atual)
- Streaming timeout: 30s (httpx connect + read combinados; vs 15s do não-streaming)
- Histórico máximo: 11 mensagens enviadas ao modelo (1 system + 5 pares user+assistant). Acima disso, descarta pares mais antigos (FIFO)
- Modelo mínimo recomendado: 32k tokens de contexto (cabe system prompt ~1k + 5 pares ~8k + resposta ~1k)
- SSE parser: ignora linhas que não começam com `data: `, ignora `[DONE]`, ignora JSON inválido
- Nome do módulo: `src/ui/chat.py` (consistente com `src/ui/analysis.py`, `src/ui/settings.py`)
- Função entry point: `render_chat_tab(conn)` (consistente com `render_analysis_tab(conn)`)
