# radtracker — Planning artifacts

## v1.4.0 — Modalidades configuráveis
**Plano detalhado:** `docs/plan-v1.4.0.md`  
**Status revisão:** Aprovado com 2 ressalvas

### Correções necessárias antes de implementar:
1. 🔴 `save_modality()` precisa aceitar parâmetro `label` (hoje só atualiza price/eph/active/color)
2. 🟡 `DEFAULT_PRICES` não pode ser removido — é fallback em `load_prices()` e migração v1→v2

---

## v1.5.0 — Chat com IA (RAG + streaming)
**Plano detalhado:** `docs/plan-v1.5.0.md`  
**Arquivos:**
- `src/ui/chat.py` (novo) — interface completa de chat
- `src/llm_client.py` — adicionar `generate_stream()` via SSE
- `app.py` — 5ª aba "💬 Chat IA"
- `src/ui/analysis.py` — substituir botão one-shot por atalho

**Decisões-chave:**
- Chat em nova aba dedicada (índice 3)
- Streaming SSE via `httpx.stream()` + `st.write_stream()`
- RAG = injeção de stats no system prompt (sem vector DB)
- Histórico em `st.session_state` (sem persistência em DB na v1.5.0)

---

## Sequência de releases
```
v1.3.0  →  v1.4.0 (modalidades)  →  v1.5.0 (chat IA)
```
