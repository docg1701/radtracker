# Sprint 7 Review — Refatoração do Sistema de Insights

**Reviewer**: subagent-disciplined  
**Data**: 2026-04-30  
**Artefato revisado**: `docs/sprints/SPRINT_7_insights_refactor.md`  
**Base de código**: `src/ui/analysis.py`, `src/llm_client.py`, `src/calculations.py`, `src/ui/settings.py`, `tests/`

---

## Review

### Correct — o que já está bom

1. **Cache `historical_cache` é preservado**  
   A função `render_analysis_tab` continua calculando `stats` e usando `st.session_state.historical_cache` com a mesma chave (`cache_key`). Isso evita recomputação entre renders e entre regras/IA. ✅ `src/ui/analysis.py:44-49`

2. **Separação regras/IA é arquiteturalmente correta**  
   Rules-first, LLM-on-demand elimina a chamada automática que hoje bloqueia a aba no carregamento. ✅

3. **Não há conflito com `st.fragment` existente**  
   `settings.py` usa `@st.fragment` para forms e danger zone. O plano **não** propõe fragmentos na aba Análise, portanto não há risco de scopes de rerun interferindo com o `historical_cache` (que é global ao session). Nota: isso é seguro, mas sub-ótimo — ver Nota 4 abaixo.

4. **Escopo mínimo de alterações**  
   A lista de arquivos modificados está correta e não invade módulos sem relação (`charts`, `db`, `app.py`). ✅

---

### Blocker — deve ser resolvido antes da implementação

#### B1. Dados novos do prompt não existem no `stats` atual; `src/calculations.py` é declarado "inalterado"
O plano pede para adicionar ao prompt:
- Totais de exames por modalidade (não só %)
- Média móvel de 7 e 30 dias (valores atuais)
- Tendência de aceleração/desaceleração
- Comparação com média histórica de todos os meses
- Dia mais produtivo do mês e valor

**Problema**: `compute_historical_stats` retorna um `DataFrame` em `stats["df"`] com colunas `ma7`/`ma30`, mas **não retorna esses dados como escalares** prontos para interpolação. `_build_prompt` atual acessa apenas `stats["current_month_stats"]`, `stats["wow_change_pct"]`, etc. Se `_build_prompt` for "expandido" sem lógica de extração do DataFrame, ocorrerá `KeyError` em tempo de execução.

**Resolução necessária**:  
- Incluir passo no plano para extrair MA7/MA30, totais de exames, dia mais produtivo, etc., em `_build_prompt` (ou adicionar precomputação em `compute_historical_stats` e remover `src/calculations.py` da lista "Files NOT Modified").  
- Atualizar `tests/test_llm_client.py` — `_minimal_stats()` não possui chave `"df"`; qualquer acesso a `stats["df"]` quebrará os testes existentes.

**Evidência**: `src/llm_client.py:101-131` (método `_build_prompt`), `tests/test_llm_client.py:89-94` (`_minimal_stats()` sem `"df"`).

#### B2. `llm_insight_pending` NÃO previne chamadas duplicadas em reruns concorrentes
O plano afirma na tabela de riscos:  
> "Duplo clique no botão IA → `llm_insight_pending` é resetado no finally, impedindo re-chamada acidental"

**Problema**: Streamlit executa o script inteiro a cada interação. Se o usuário der um duplo-clique, dois reruns são enfileirados. No rerum 1, `pending=True`, a chamada HTTP começa. No rerum 2 (disparado antes do término do primeiro), `pending` ainda é `True`, então uma **segunda chamada HTTP é iniciada em paralelo**. O `finally` de cada um apenas zera `pending` no final da **própria** execução; ele não bloqueia re-entrada.

**Resolução necessária**:  
- Adicionar guarda `llm_insight_in_flight` (ou `llm_request_timestamp`) para rejeitar chamadas enquanto uma está ativa; OU  
- Isolar a seção IA em `@st.fragment` para que apenas interações dentro do fragmento disparem rerun, eliminando a causadora externa de reruns duplicados.

**Evidência**: `src/ui/settings.py:44` (`@st.fragment` já é usado no projeto para isolar interações pesadas), `src/ui/analysis.py:63-72` (modelo atual de fallback LLM que o plano substitui).

#### B3. Resultado da IA é efêmero — perde-se a cada mudança de aba ou interação externa
Como `llm_insight_pending` é resetado para `False` e o texto da IA **não é armazenado em `session_state`**, ao usuário:
1. Clicar em "Perguntar à IA"
2. Esperar 5-15s
3. Ver o resultado
4. Clicar em outra aba (Hoje/Mês)
5. Voltar para Análise

…o resultado desaparece. A experiência é regressive em relação ao comportamento atual, que mostra regras imediatamente (fallback) e mantém o insight visível.

**Resolução necessária**: Armazenar `st.session_state.llm_insight_text` (e talvez `llm_insight_error`) para persistir entre renders. Invalidar esse cache somente quando `cache_key` de `historical_cache` mudar (meta, preços, mês).

---

### Note — observações, riscos e itens de seguimento

#### N1. Critério de aceite 7.1 é fraco
"Prompt gerado contém pelo menos 8 campos de dados distintos" — o template **atual** (`_USER_PROMPT_TEMPLATE`) já contém ~11 campos distintos (MTD, % meta, dias, média diária, meta diária, projeção, WoW, MoM, mix RM, mix TC, mix RX, consecutivos). O critério seria satisfeito sem nenhuma alteração.  
**Sugestão**: exigir que o novo template inclua, no mínimo, MA7, MA30, totais de exames por modalidade, dia mais produtivo e média histórica.

#### N2. Token/prompt safety: aumento de `max_tokens` e tamanho do prompt
- `max_tokens` 600→800 aumenta o custo/tempo de resposta em ~33%.
- O plano estima "~2K tokens" para o prompt, mas não inclui cálculo real. Com MA7, MA30, dias produtivos, comparação histórica e totais, o prompt pode ultrapassar 2.5K–3K tokens.
- O modelo `openai/gpt-oss-120b:free` tem 1M de contexto (verdade), mas a **camada free do OpenRouter** tem rate limits agressivos (RPM/TPM). Um prompt mais denso + max_tokens 800 pode estourar o rate limit mais rápido.

**Sugestão**: adicionar ao plano um passo de benchmark do tamanho do prompt final e documentar o rate limit atual do endpoint free.

#### N3. Ausência de testes para `src/ui/analysis.py`
Não existe `tests/test_analysis.py`. A refatoração:
- Renomeia `_render_insight_card` → `_render_insight_body`
- Adiciona `_request_llm_insight` e `_render_llm_section`
- Muda fluxo de renderização condicional

Sem testes, regressões no HTML/markdown, no fluxo do botão ou no tratamento de exceções não serão detectadas.

**Sugestão**: adicionar ao plano a criação de `tests/test_analysis.py` com mocks para `LLMClient` e asserts sobre:
- Condição de retorno precoce quando `df` é vazio
- `_request_llm_insight` seta flag corretamente
- `_render_llm_section` chama `LLMClient.generate` com os `stats` esperados
- Expander de regras é renderizado sempre; expander de IA só quando flag está ativa.

#### N4. Omissão de `@st.fragment` para a seção IA é uma oportunidade perdida
O projeto já domina `@st.fragment` (`settings.py:44,97`). Envolver a seção IA em um fragmento:
- Isolava o spinner da chamada LLM do resto da página (melhor UX)
- Eliminava a necessidade de preocupação com reruns externos causando chamadas duplicadas
- Permitia que o usuário interagisse com outros widgets enquanto a IA "pensava" (se o fragmento não depende deles)

O plano deveria pelo menos avaliar essa opção.

#### N5. Edge case: `api_key` ausente mostra erro genérico; não há fast-fail no botão
`_render_llm_section` obtém a chave via `os.environ.get` e passa para `LLMClient`. Se a chave for `None`, a exceção é capturada e mostra:  
> "Não foi possível gerar a análise. Verifique sua conexão ou chave de API."

Isso é aceitável, mas o botão continua cliclável. Uma melhoria seria desabilitar o botão quando `OPENROUTER_API_KEY` não está configurada (`disabled=(api_key is None)`), com um caption explicativo. Não é blocker, mas melhora a UX.

#### N6. Nomenclatura do helper `_render_insight_body`
O rename remove o container com borda e o `<h3>`. A nova função deve conter apenas markdown + caption. Isso é correto porque `st.expander` fornece o título. Verificar se `_render_insight_body` ainda precisa do `unsafe_allow_html=True` (provavelmente não, se for apenas `st.markdown` puro). Se for mantido, o `re.sub` para bold HTML pode ser substituído por `st.markdown(text)` diretamente, já que Streamlit renderiza `**negrito**` nativamente. Isso simplificaria o código.

---

## Sumário Executivo

| Item | Severidade | Status |
|------|------------|--------|
| Cache `historical_cache` preservado | — | ✅ OK |
| Separação regras/IA | — | ✅ OK |
| Escopo de arquivos | — | ✅ OK |
| Dados do prompt não existem em `stats` (B1) | **Blocker** | 🔴 Requer plano de extração dos dados |
| Chamadas duplicadas LLM em reruns (B2) | **Blocker** | 🔴 Requer guarda de in-flight ou `@st.fragment` |
| Resultado IA efêmero entre abas (B3) | **Blocker** | 🔴 Requer cache em `session_state` |
| Critério de aceite 7.1 fraco (N1) | Note | 🟡 Melhorar critério |
| Token safety / rate limiting (N2) | Note | 🟡 Documentar benchmark |
| Sem testes para `analysis.py` (N3) | Note | 🟡 Adicionar ao plano |
| Não usar `@st.fragment` na IA (N4) | Note | 🟢 Seguro, mas sub-ótimo |
| Botão sem fast-fail para key ausente (N5) | Note | 🟡 Nice-to-have |
| Refactor de HTML para markdown puro (N6) | Note | 🟢 Oportunidade de simplificação |

**Recomendação final**: Não aprovar a implementação até que B1, B2 e B3 sejam endereçados no plano (dados extraídos para o prompt, guarda contra chamadas duplicadas, e persistência do resultado da IA no `session_state`).
