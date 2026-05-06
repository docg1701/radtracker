# Guia: Escape de `$` no Markdown do Streamlit

## Problema

Quando o LLM (OpenRouter) gera texto contendo `$` (ex: `R$ 4.500,00`), o
renderizador Markdown do Streamlit interpreta `$` como delimitador de LaTeX
(modo matemático). O resultado: texto verde, fonte miúda, distorcido.

Isso acontece em **duas situações distintas** e exige **duas correções
diferentes**.

### Situação 1 — Histórico de mensagens (st.markdown / st.write)

Mensagens já completas no `st.session_state.messages` são re-renderizadas a
cada `st.rerun()`. Se o conteúdo tem `$`, o `st.markdown()` ativa o modo LaTeX.

**Correção:** Passar o texto por `md_escape()` antes de renderizar:

```python
from src.formatting import md_escape

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(md_escape(msg["content"]))
```

`md_escape()` está em `src/formatting.py` e faz `text.replace("$", "\\$")`.

### Situação 2 — Streaming token por token (st.write_stream)

`st.write_stream()` renderiza cada token **imediatamente** como Markdown.
Se um token contém `$`, o LaTeX é ativado naquele momento, e todos os tokens
seguintes continuam em modo matemático até o fim do stream (já que o `$` de
abertura nunca é fechado). Só depois do stream completo, no `st.rerun()`
seguinte, a Situação 1 corrige o texto final.

**Correção:** Envolver o generator de tokens com um wrapper que escapa `$`:

```python
stream = llm.generate_stream(messages)
safe_stream = (token.replace("$", "\\$") for token in stream)
response = st.write_stream(safe_stream)
```

> **IMPORTANTE:** Escapar apenas no histórico **não resolve** o streaming.
> Escapar apenas no streaming **não resolve** o histórico.
> **Ambas as correções são necessárias.**

---

## Checklist para futuros bugs de renderização no chat

- [ ] `md_escape()` aplicado em TODOS os `st.markdown()` que renderizam conteúdo
      do LLM ou que contenham `fmt_brl()`
- [ ] `safe_stream` com `token.replace("$", "\\$")` envolvendo o generator
      passado para `st.write_stream()`
- [ ] Se usar `st.write()` em vez de `st.markdown()`, o comportamento é o mesmo
      — `st.write(string)` chama `st.markdown()` internamente, então a correção
      acima se aplica igual

---

## Histórico de correções neste projeto

| Commit | Arquivo | O que corrigiu |
|--------|---------|---------------|
| `3f696e3` | `src/ui/analysis.py` | `md_escape(text)` antes de `st.markdown` |
| `de44f2a` | `src/ui/chat.py` | `md_escape(msg["content"])` no histórico |
| `d9a67dd` | `src/ui/chat.py` | `safe_stream` no `st.write_stream()` |
