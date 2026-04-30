# Sprint 5 — Plano de Implementação

**Projeto**: radtracker
**Data**: 2026-04-29
**Status**: Planejamento concluído. Implementação pendente.
**Sprints anteriores**: S1 (sidebar + SQLite) · S2 (Hoje) · S3 (Mês) · S4 (Análise) — todas ✅ concluídas

---

## Objetivo

Implementar três funcionalidades interdependentes:
1. **Integração LLM** — insights gerados por IA (GPT-OSS 120B via OpenRouter), com fallback automático para o motor de regras existente
2. **Aba de Configurações** — edição de preços (RM/TC/RX) e meta mensal, com persistência imediata
3. **Session state para preços/meta** — carregamento único no boot, eliminando chamadas repetidas a `load_prices`/`load_goal` em cada aba

---

## Arquitetura Atual (referência)

```
app.py
  ├── render_sidebar(conn)           # Formulário de entrada
  ├── render_today_tab(conn)         # KPI cards, donut, sparkline
  ├── render_month_tab(conn)         # Gauge, linha diária, alerta
  ├── render_analysis_tab(conn)      # Insights + 3 gráficos (Sprint 4)
  └── tab_config (placeholder)       # "Em breve — preços e meta (Sprint 5)"

Cada aba chama load_prices(conn) e load_goal(conn, year_month) independentemente.
Não há session_state para preços/meta — cada chamada faz query ao SQLite.
```

**Problema**: se o usuário altera preços na aba Config, as outras abas só veem o novo valor no próximo rerun. Com session_state, a atualização é refletida em todas as abas imediatamente.

---

## Tarefas

### 5.0 — Atualizar `.env.example`

**Arquivo**: `.env.example` (já existe, verificar conteúdo)

**Ação**: garantir que o arquivo contenha a variável `OPENROUTER_API_KEY` com comentário explicativo:

```bash
# OpenRouter API key — obtenha em https://openrouter.ai/settings/keys
# Deixe em branco para usar apenas os insights baseados em regras (sem IA).
OPENROUTER_API_KEY=your_key_here
```

**Dependências**: nenhuma.

---

### 5.1 — Criar `src/llm_client.py`

**Arquivo novo**: `src/llm_client.py`

**Responsabilidade**: encapsular toda a comunicação com a API OpenRouter. Nenhuma dependência de Streamlit ou do banco de dados.

**API pública** (segue o contrato arquitetural do `docs/PLAN.md` §8.3):

```python
class LLMUnavailableError(Exception):
    """Levantada quando a API OpenRouter não está acessível (timeout, 4xx, 5xx, ou chave ausente)."""
    pass


class LLMClient:
    """
    Wrapper stateless para a API OpenRouter (GPT-OSS 120B).

    Constructor recebe a API key. Método generate() aceita stats dict
    e retorna string markdown em português.
    """

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise LLMUnavailableError("API key não configurada")
        self._api_key = api_key

    def generate(self, stats: dict[str, Any]) -> str:
        """
        Chama GPT-OSS 120B via OpenRouter para gerar insights em português.

        Args:
            stats: Dict de compute_historical_stats() — mesmo usado por generate_rule_insights.

        Returns:
            String markdown em português com análise personalizada.

        Raises:
            LLMUnavailableError: timeout (>15s) ou erro HTTP.
        """
        user_prompt = self._build_prompt(stats)
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-oss-120b:free",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 600,
                    "temperature": 0.3,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise LLMUnavailableError("Timeout ao chamar OpenRouter (15s)") from None
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(
                f"OpenRouter HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

        return data["choices"][0]["message"]["content"]
```

**Prompt template** (em português, constante `SYSTEM_PROMPT` no módulo).

⚠️ **Sanitização de `None`**: `wow_change_pct` e `mom_change_pct` podem ser `None`
(quando há <2 semanas ou <2 meses de dados). O chamador deve substituir `None` por
`"sem dados suficientes"` antes de interpolar no prompt — jamais enviar `"None%"`
para o modelo.

```
Você é um assistente pessoal de produtividade para um médico radiologista chamado Galvani.
Analise os dados de produção abaixo e gere um parágrafo de insights em português,
com tom amigável e direto. Use os números reais. Dê sugestões acionáveis.

Dados:
- Faturamento no mês (MTD): R$ {mtd}
- Percentual da meta: {pct}%
- Dias trabalhados: {dias_trabalhados} de {total_dias} dias úteis
- Média diária: R$ {media_diaria}
- Meta diária necessária: R$ {meta_diaria}
- Projeção de fechamento: R$ {projecao}
- Variação semana a semana: {wow}
- Variação mês a mês: {mom}
- Mix atual: RM {mix_rm}%, TC {mix_tc}%, RX {mix_rx}%
- Dias consecutivos abaixo da meta: {consecutivos}

Responda APENAS com o texto do insight, sem introduções, sem "Aqui está sua análise:".
Use **negrito** para destaques. Máximo 3 parágrafos.
```

**Detalhes de implementação**:
- Timeout: 15 segundos
- Modelo: `openai/gpt-oss-120b:free` (conforme PLAN.md original)
- Temperatura: `0.3` (consistência nas respostas)
- Se a chave for `None` ou `""` → construtor levanta `LLMUnavailableError("API key não configurada")`
- Se timeout → `raise LLMUnavailableError("Timeout ao chamar OpenRouter (15s)")`
- Se HTTPError ≥400 → `raise LLMUnavailableError(f"Erro HTTP {status_code}")`
- A API key é lida de `os.environ["OPENROUTER_API_KEY"]` pelo chamador (app.py), **não** dentro de `llm_client.py` — o construtor recebe a key como parâmetro

**Chamada à API** (exemplo concreto):
```python
import httpx

client = httpx(
    host="https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
)
response = client.chat(
    model="openai/gpt-oss-120b:free",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    options={"temperature": 0.3},
)
return response["message"]["content"]
```

**Dependências**:
- `httpx` (já está em `requirements.txt`)
- `python-dotenv` (já está em `requirements.txt` — o chamador faz `load_dotenv()`)
- **Nenhuma** dependência de Streamlit, pandas, ou `src/*`

---

### 5.2 — Implementar fallback LLM em `src/ui/analysis.py`

**Arquivo modificado**: `src/ui/analysis.py`

**Mudanças**:

1. **Adicionar imports**:
   ```python
   import os
   from src.llm_client import LLMClient, LLMUnavailableError
   ```
   Nota: `load_dotenv()` é chamado **uma vez** no `app.py` (inicialização centralizada),
   não dentro da aba de análise.

2. **Modificar `render_analysis_tab`**: após computar `stats` e validar que `df` não está vazio, substituir a chamada direta a `generate_rule_insights(stats)` por uma lógica de duas vias:

   ```python
   # ── Insight card (LLM com fallback) ──
   api_key = os.environ.get("OPENROUTER_API_KEY")

   try:
       with st.spinner("🧠 Gerando insights com IA..."):
           llm = LLMClient(api_key)
           insight_text = llm.generate(stats)
       _render_insight_card(insight_text, source="llm")
   except LLMUnavailableError:
       insight_text = generate_rule_insights(stats)
       st.info("🤖 IA indisponível — exibindo análise baseada em regras.")
       _render_insight_card(insight_text, source="rules")
   ```

3. **Modificar `_render_insight_card`** para aceitar um parâmetro `source`:
   - `source="llm"` → caption: `"🤖 Gerado por GPT-OSS 120B (OpenRouter) · Análise automática baseada nos seus dados"`
   - `source="rules"` → caption: `"📊 Análise automática baseada nos seus dados"` (comportamento atual)

**Dependências**: tarefa 5.1 (precisa do `llm_client.py` existir)

---

### 5.3 — Criar `src/ui/settings.py`

**Arquivo novo**: `src/ui/settings.py`

**Layout da aba** (seguindo DESIGN_SPEC §4.7):

```
┌─────────────────────────────────────────────────────┐
│ ⚙️ Configurações                                    │
│                                                     │
│ ── Preços dos Exames ──                            │
│ RM  [ 35.00 ]  TC  [ 25.00 ]  RX  [  4.50 ]       │
│                                                     │
│ ── Meta Mensal ──                                  │
│ Meta (R$)  [ 45000 ]                               │
│                                                     │
│ [ 💾 Salvar configurações ]                        │
│                                                     │
│ ── ⚠️ Zona de Perigo ──                            │
│ [ 🗑️ Limpar todos os dados ]                       │
└─────────────────────────────────────────────────────┘
```

**Função pública**:

```python
def render_settings_tab(conn: Any) -> None:
    """
    Renderiza a aba de Configurações: preços, meta mensal, e zona de perigo.

    - Preços: 3 number_inputs com step=0.01, format="%.2f" (prefixo "R$" no label)
    - Meta: 1 number_input com step=100.0
    - Ao salvar, grava no banco e atualiza st.session_state
    - Zona de perigo: botão com dupla confirmação para deletar todos os dados
    """
```

**Detalhes de implementação**:

1. **Preços**: `st.number_input("RM (R$)", min_value=0.01, step=0.01, format="%.2f", value=current["rm"])`. O parâmetro `format="%.2f"` exibe duas casas decimais nativamente. O prefixo "R$" fica no label do input.

2. **Meta mensal**: `st.number_input("Meta mensal (R$)", min_value=0.0, step=100.0, value=current_goal)`.

3. **Botão Salvar**: chama `save_prices(conn, rm, tc, rx)` e `save_goal(conn, year_month, goal)`, depois atualiza `st.session_state.prices` e `st.session_state.goal`, mostra toast `"✅ Configurações salvas!"`, e não dá rerun (o session_state já reflete nas outras abas).

4. **Zona de perigo** — padrão de dupla confirmação:
   ```python
   st.divider()
   st.subheader("⚠️ Zona de Perigo")

   if "confirm_delete" not in st.session_state:
       st.session_state.confirm_delete = False

   if not st.session_state.confirm_delete:
       if st.button("🗑️ Limpar todos os dados", type="secondary"):
           st.session_state.confirm_delete = True
           st.rerun()
   else:
       st.warning("Tem certeza? Esta ação não pode ser desfeita.")
       col1, col2 = st.columns(2)
       with col1:
           if st.button("✅ Sim, limpar tudo", type="primary"):
               _delete_all_data(conn)
               st.session_state.confirm_delete = False
               st.toast("🗑️ Todos os dados foram removidos.")
               st.rerun()
       with col2:
           if st.button("❌ Cancelar"):
               st.session_state.confirm_delete = False
               st.rerun()
   ```

5. **`_delete_all_data(conn)`**: helper privado que executa `DELETE FROM daily_production; DELETE FROM exam_prices; DELETE FROM monthly_goals;` dentro de uma transação. Deve estar em `settings.py` como função privada.

   ⚠️ **Comportamento documentado na UI**: "Esta ação remove TODOS os dados, incluindo preços e metas configurados. Os valores padrão serão restaurados (RM=R$35, TC=R$25, RX=R$4,50, meta=R$45.000)."

**Validações**:
- Preços devem ser > 0 (a UI já força `min_value=0.01`)
- Meta deve ser ≥ 0 (a UI já força `min_value=0.0`)
- Se o usuário salvar preços zerados, mostrar `st.error("Os preços devem ser maiores que zero.")` e não salvar

**Dependências**: nenhuma (usa `db.py` que já existe)

---

### 5.4 — Wire session_state para preços e meta

**Arquivos modificados**: `app.py`, `src/ui/settings.py`

**Estratégia**: em vez de cada aba chamar `load_prices`/`load_goal`, carregamos uma vez no boot do app e armazenamos em `st.session_state`. A aba de Config atualiza tanto o banco quanto o session_state.

**Limitação documentada**: `st.session_state.goal` armazena apenas a meta do **mês atual**. Suporte a consulta de metas de outros meses requer refatoração futura para `st.session_state.goals: dict[str, float]`. Para o escopo da Sprint 5, apenas o mês corrente é necessário.

**Mudanças em `app.py`**:

```python
# Após init_db(conn):
if "prices" not in st.session_state:
    st.session_state.prices = load_prices(conn)

if "goal" not in st.session_state:
    today = date.today()
    st.session_state.goal = load_goal(conn, today.isoformat()[:7])

# Passar para as abas (todas já recebem conn, mas agora podem ler do session_state)
```

**Alternativa mais limpa**: criar um helper `ensure_settings(conn)` chamado no início de cada aba que popula o session_state se não existir. Evita poluir `app.py`.

```python
# Em src/ui/settings.py (ou um novo módulo leve):
def ensure_settings(conn: Any) -> None:
    """Garante que st.session_state.prices e .goal estejam populados."""
    if "prices" not in st.session_state:
        st.session_state.prices = load_prices(conn)
    if "goal" not in st.session_state:
        today = date.today()
        st.session_state.goal = load_goal(conn, today.isoformat()[:7])
```

**Impacto nas abas existentes**:

| Arquivo | Mudança |
|---|---|
| `src/ui/today.py` | `prices = st.session_state.prices` em vez de `prices = load_prices(conn)`; `monthly_goal = st.session_state.goal` em vez de `load_goal(conn, year_month)` |
| `src/ui/month.py` | Idem |
| `src/ui/analysis.py` | Idem |
| `src/ui/analysis.py` (LLM) | Já modificado na tarefa 5.2 |

**Tradeoff**: session_state persiste durante a sessão do navegador. Se o usuário fechar e reabrir, recarrega do banco. Isso é o comportamento desejado — o banco é a fonte da verdade, o session_state é um cache de sessão.

**Dependências**: tarefa 5.3 (settings.py precisa existir para o ciclo de save funcionar)

---

### 5.5 — Verificar e completar `.streamlit/config.toml`

**Arquivo**: `.streamlit/config.toml` (já existe)

**Estado atual**: contém tema light, sem bloco dark. O PLAN.md §5.5 pede para "Ensure file matches DESIGN_SPEC §7.3 exactly. Light theme default, dark theme block."

**Verificações**:
1. O arquivo atual tem `[theme]` com `base = "light"` ✅
2. Precisa adicionar bloco `[theme]` para dark mode? O Streamlit alterna automaticamente se o usuário selecionar "Dark" no menu ☰ → Settings → Theme, usando as cores do tema claro como base. Não é necessário um bloco separado `[theme]` para dark — o Streamlit inverte automaticamente.
3. Todas as cores de fundo dos charts são `rgba(0,0,0,0)` (transparente) — já verificado ✅

**Ação**: verificar que o arquivo está conforme, adicionar comentário documentando. Não requer alterações estruturais.

Nota: a task 5.6 do PLAN.md original ("Add theme-aware chart colors") já está satisfeita desde a Sprint 4 — todos os charts usam `paper_bgcolor='rgba(0,0,0,0)'` e `plot_bgcolor='rgba(0,0,0,0)'`, herdando o tema do Streamlit automaticamente.

---

### 5.6 — Teste end-to-end (manual)

**Cenários de teste**:

| # | Cenário | Passos | Resultado esperado |
|---|---|---|---|
| 1 | **LLM disponível** | Configurar `OPENROUTER_API_KEY` no `.env`, abrir aba Análise | Spinner "🧠 Gerando insights com IA...", insight com emojis e texto personalizado, caption "🤖 Gerado por GPT-OSS 120B (OpenRouter)" |
| 2 | **LLM indisponível** | Remover ou invalidar `OPENROUTER_API_KEY`, abrir aba Análise | Banner `st.info("🤖 IA indisponível — exibindo análise baseada em regras.")`, insight baseado em regras, caption "📊 Análise automática" (sem menção à IA) |
| 3 | **Timeout LLM** | Simular timeout (mock ou chave inválida que cause demora) | Após 15s, fallback com banner informativo exibindo análise baseada em regras |
| 4 | **Salvar preços** | Aba Config → alterar RM para 40.00 → Salvar | Toast "✅ Configurações salvas!", aba Hoje reflete R$40.00/exame imediatamente |
| 5 | **Salvar meta** | Aba Config → alterar meta para 50000 → Salvar | Aba Mês reflete nova meta no gauge e no KPI |
| 6 | **Deletar dados (cancelar)** | Zona de perigo → "🗑️ Limpar todos" → "❌ Cancelar" | Botão de confirmação desaparece, dados intactos |
| 7 | **Deletar dados (confirmar)** | Zona de perigo → "🗑️ Limpar todos" → "✅ Sim, limpar tudo" | Todas as 3 tabelas vazias, toast "🗑️ Todos os dados foram removidos.", tabs mostram empty states |
| 8 | **Preços zerados** | Aba Config → RM=0 → Salvar | `st.error("Os preços devem ser maiores que zero.")`, nada salvo |
| 9 | **Recarregar sessão** | Fechar navegador, reabrir | Preços/meta carregados do banco, session_state populado corretamente |

**Dependências**: tarefas 5.1–5.5 concluídas

---

## Ordem de Implementação

```
5.0 (.env.example)    ←── independente
5.3 (settings.py)     ←── independente (usa db.py existente)
5.4 (session_state)   ←── depende de 5.3 (ciclo save/load)
5.1 (llm_client.py)   ←── independente (zero deps do projeto)
5.2 (LLM fallback)    ←── depende de 5.1 e 5.4
5.5 (config.toml)     ←── independente
5.6 (teste manual)    ←── depende de todas
```

**Paralelizável**: 5.0, 5.1 e 5.3 podem ser implementadas simultaneamente (zero dependências entre elas).

---

## Decisões de Design

### 1. LLMClient como classe (conforme contrato arquitetural)

**Decisão**: classe `LLMClient(api_key)` com método `generate(stats) -> str`.

**Justificativa**: o `docs/PLAN.md` §8.3 estabelece o contrato arquitetural:
"`llm_client.py`: single class `LLMClient` wrapping the OpenRouter API. Constructor takes API key."
Seguir o contrato mantém consistência com o restante do projeto e facilita
futura extensão (retry, pooling, cache) sem quebrar a API pública.

### 2. API key no .env vs banco de dados

**Decisão**: `.env` (variável de ambiente).

**Justificativa**: a API key é uma credencial secreta — não pertence ao banco SQLite local (que é feito backup e pode ser compartilhado). `.env` já está no `.gitignore`. O padrão da indústria para chaves de API é variável de ambiente.

### 3. `ensure_settings` em módulo separado vs inline em cada aba

**Decisão**: função `ensure_settings(conn)` em `src/ui/settings.py`, chamada no início de cada aba.

**Justificativa**: evita duplicação do guard `if "prices" not in st.session_state` em 3 arquivos. Centraliza a lógica de fallback (se session_state vazio, carrega do banco). O nome `ensure_settings` deixa claro que é idempotente.

### 4. Deleção de dados: lógica no db.py vs settings.py

**Decisão**: função privada `_delete_all_data(conn)` em `settings.py`.

**Justificativa**: é usada apenas na aba de Config. Se futuramente for necessária em outro lugar (ex: testes), movemos para `db.py`. Por ora, KISS.

### 5. Formato dos inputs de preço

**Decisão**: `st.number_input("RM (R$)", min_value=0.01, step=0.01, format="%.2f")`.

**Justificativa**: `st.number_input` suporta nativamente o parâmetro `format` (ex: `"%.2f"`).
Usar `format="%.2f"` exibe duas casas decimais no próprio input, sem necessidade de
 label externo. O prefixo "R$" fica no label do input, não no format string.

---

## Arquivos Afetados

| Arquivo | Tipo | Mudança |
|---|---|---|
| `.env.example` | Verificado/atualizado | Documentar `OPENROUTER_API_KEY` com comentário |
| `src/llm_client.py` | **Novo** | Classe `LLMClient`, prompt, tratamento de erros |
| `src/ui/settings.py` | **Novo** | Aba de Configurações completa |
| `src/ui/analysis.py` | Modificado | Fallback LLM + rules, caption condicional |
| `app.py` | Modificado | Substituir placeholder Config, importar settings |
| `src/ui/today.py` | Modificado | Usar `st.session_state.prices` e `.goal` |
| `src/ui/month.py` | Modificado | Idem |
| `.streamlit/config.toml` | Verificado | Confirmar conformidade, adicionar comentários |

---

## Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| **OpenRouter quebrar API** — mudança de endpoint, auth, ou nome do modelo | Média (30%) | Baixo — LLM é opcional | Fallback automático para regras. `LLMUnavailableError` captura qualquer exceção HTTP da biblioteca `httpx`. |
| **Rate limit (429)** — mais de ~50 chamadas/dia no plano free | Baixa (10%) | Baixo — só afeta qualidade do insight | Cache por dia: não re-gerar se stats não mudaram. Alternativa: throttling de 1 chamada a cada 5 minutos. |
| **`st.session_state` não persiste após rerun** — comportamento do Streamlit | Muito baixa (<5%) | Alto — preços/meta zerados | Inicialização idempotente: se `"prices" not in st.session_state`, recarrega do banco. O banco é sempre a fonte da verdade. |
| **Deleção acidental de dados** — usuário confirma sem querer | Média (15%) | Alto — perda de dados | Dupla confirmação com `st.warning`. Botão "Cancelar" proeminente. Futuro: backup automático (Sprint 6). |
| **Conflito de session_state entre abas** — duas abas atualizam `st.session_state.prices` simultaneamente | Muito baixa (<1%) | Baixo | Streamlit é single-threaded por sessão. Apenas uma aba processa por vez. |

---

## Definition of Done (Sprint 5)

- [ ] `.env.example` atualizado com `OPENROUTER_API_KEY=your_key_here` e comentário explicativo
- [ ] `src/llm_client.py` existe com classe `LLMClient(api_key)` e método `generate(stats) -> str`, mais `LLMUnavailableError`
- [ ] Prompt em português, temperatura 0.3, timeout 15s
- [ ] `generate_rule_insights` é chamado como fallback automático quando LLM falha
- [ ] Aba Análise mostra spinner "🧠 Gerando insights com IA..." quando chama LLM
- [ ] Banner `st.info` aparece quando fallback é ativado
- [ ] Caption do insight card muda conforme source (LLM vs rules)
- [ ] Aba Config renderiza 3 inputs de preço + 1 input de meta + botão Salvar
- [ ] Salvar atualiza `exam_prices` e `monthly_goals` no banco
- [ ] Salvar atualiza `st.session_state.prices` e `st.session_state.goal` imediatamente
- [ ] Zona de perigo exige dupla confirmação para deletar todos os dados
- [ ] `ensure_settings(conn)` população inicial do session_state em cada aba
- [ ] `.streamlit/config.toml` verificado (tema light default, dark mode funcional)
- [ ] Testes manuais (9 cenários) passam
- [ ] `python -m py_compile app.py src/*.py src/ui/*.py` sem erros
