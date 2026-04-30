# Sprint 7 — Refatoração do Sistema de Insights

**Data**: 2026-04-30  
**Objetivo**: Separar regras de IA, adicionar botão explícito, blocos colapsáveis, prompt melhorado.

---

## Goal

Refatorar a aba "Análise" para que:
1. Insights padrão sejam baseados em regras (sem chamada automática à IA)
2. Um botão "🧠 Perguntar à IA" faça chamada idempotente à OpenRouter
3. Ambos os blocos de insight sejam colapsáveis via `st.expander`
4. O prompt da IA seja ~20-30% mais denso, com mais fatores e análise mais rica

---

## Tasks

### 7.1 — Melhorar o prompt da IA em `src/llm_client.py`

- **File**: `src/llm_client.py`
- **Changes**:
  - Reescrever `SYSTEM_PROMPT` para ser mais específico sobre o que analisar
  - Expandir `_USER_PROMPT_TEMPLATE` com mais dados:
    - Totais de exames por modalidade (não só %)
    - Média móvel de 7 e 30 dias (valores atuais)
    - Tendência de aceleração/desaceleração
    - Dias restantes no mês
    - Comparação com média histórica de todos os meses
    - Dia mais produtivo do mês e valor
  - Aumentar `max_tokens` de 600 para 800
  - Remover limite de "máximo 3 parágrafos", substituir por "análise completa e detalhada"
  - Adicionar ao system prompt: "Analise tendências, sazonalidade, composição do mix, ritmo de trabalho, projeções e riscos. Seja analítico e profundo."
- **Acceptance**: Prompt gerado contém pelo menos 8 campos de dados distintos.

### 7.2 — Refatorar `src/ui/analysis.py` — nova lógica de insights

- **File**: `src/ui/analysis.py`
- **Changes**:
  1. Remover o bloco atual de LLM-com-fallback (linhas ~63-72)
  2. Adicionar após a validação de dados:

```python
# ── Bloco 1: Insights por regras (expandido por padrão) ──
with st.expander("💡 Insights", expanded=True):
    rule_text = generate_rule_insights(stats)
    _render_insight_body(rule_text, source="rules")

# ── Bloco 2: IA (botão explícito, resultado colapsável) ──
st.button("🧠 Perguntar à IA", type="secondary",
          on_click=lambda: _request_llm_insight())
if st.session_state.get("llm_insight_pending"):
    _render_llm_section(stats)
```

- **Acceptance**: Aba abre sem chamada LLM, mostra regras expandidas, botão IA visível.

### 7.3 — Implementar `_request_llm_insight()` e `_render_llm_section()`

- **File**: `src/ui/analysis.py`
- **New helpers**:

```python
def _request_llm_insight() -> None:
    """Flag que dispara a chamada LLM no próximo render."""
    st.session_state.llm_insight_pending = True

def _render_llm_section(stats: dict) -> None:
    """Executa a chamada LLM e renderiza o resultado num expander colapsável."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    try:
        with st.spinner("🧠 Gerando análise com IA..."):
            llm = LLMClient(api_key)
            llm_text = llm.generate(stats)
        with st.expander("🤖 Análise da IA", expanded=True):
            _render_insight_body(llm_text, source="llm")
    except LLMUnavailableError:
        st.error("Não foi possível gerar a análise. Verifique sua conexão ou chave de API.")
    finally:
        st.session_state.llm_insight_pending = False
```

- **Acceptance**: Clique no botão → spinner → expander com resultado. Clique de novo → nova chamada.

### 7.4 — Substituir `_render_insight_card` por `_render_insight_body`

- **File**: `src/ui/analysis.py`
- **Changes**:
  - Renomear `_render_insight_card` para `_render_insight_body`
  - Remover o container com borda e o `<h3>` (o expander já provê o título)
  - Manter apenas o corpo do texto com markdown
  - Manter caption de source no final
- **Acceptance**: Função renderiza texto puro + caption, sem borda própria.

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/llm_client.py` | Prompt expandido, max_tokens 600→800, mais dados no template |
| `src/ui/analysis.py` | Separa regras/IA, 2 expanders, botão explícito, rename helper |

## Files NOT Modified

- `src/insights_rules.py` — inalterado
- `src/calculations.py` — inalterado
- `src/charts*.py` — inalterado
- `app.py` — inalterado

---

## Dependencies

```
7.1 (prompt LLM)     ← independente
7.2 (refatorar fluxo) ← independente de 7.1
7.3 (helpers novos)  ← depende de 7.2
7.4 (rename helper)  ← depende de 7.2
```

7.1 e 7.2 são paralelizáveis.

---

## Risks

| Risco | Mitigação |
|-------|-----------|
| `st.expander` com `expanded=True` em IA colapsada pode piscar | Usar `expanded=True` só quando resultado chega |
| `on_click` com lambda capturando `stats` stale | Passar stats via session_state, não closure |
| Prompt maior pode exceder limite de tokens do modelo free | Modelo tem 1M de contexto, prompt fica em ~2K tokens — seguro |
| Duplo clique no botão IA | `llm_insight_pending` é resetado no finally, impedindo re-chamada acidental |
