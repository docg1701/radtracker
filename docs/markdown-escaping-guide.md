# Guia: Escape de `$` no Markdown do Streamlit

## Problema

O frontend do Streamlit (`react-markdown` + `remark-math` + `rehype-katex`)
trata pares de `$...$` como matemática inline. Texto vindo do LLM com moeda
brasileira (`R$ 1.250,00`) ou americana (`$50`) tem múltiplos `$` no mesmo
parágrafo, e o KaTeX pareia o primeiro com um seguinte: o conteúdo entre
eles vira fórmula em fonte serifada itálica, os cifrões delimitadores
somem da tela, e o resultado parece "texto verde, fonte miúda, distorcido"
quando o pareamento ocorre dentro de um balão de chat com fundo colorido.

A Streamlit não oferece (até a v1.57) flag de configuração nem parâmetro
em `st.markdown` para desligar LaTeX. A recomendação oficial dos
mantenedores (issue [#7898](https://github.com/streamlit/streamlit/issues/7898),
fechada) é exatamente uma das duas opções:

- `st.text(content)` — renderiza tudo literal, mas perde Markdown inteiro
  (negrito, listas, links). Inviável para chat formatado.
- `st.markdown(content.replace("$", "\\$"))` — escape do `$` para `\$`,
  preserva o resto do Markdown.

O `radtracker` usa a segunda abordagem, refinada por um pipeline de
sanitização que também cobre matemática vinda de LLMs no formato OpenAI
(`\(...\)`, `\[...\]`).

---

## Arquitetura atual: três pontos de aplicação

A sanitização do chat acontece em três pontos do fluxo, todos em
`src/ui/chat.py`:

| Ponto | Local | Função | Razão |
|---|---|---|---|
| Streaming token a token | `_stream_response` | `sanitize_token(token)` em cada chunk SSE | Cada chunk é parseado parcialmente; um `$` solto pode acionar pareamento espúrio com cifrão de chunks anteriores antes do stream terminar. |
| Salvamento da resposta | `_stream_response` | `sanitize_text(response)` na string completa | Conserta casos que cruzam fronteira de chunk (ex.: `\(` em um chunk e `\)` no seguinte) que o token-level não pega. |
| Re-renderização do histórico | loop em `render_chat_tab` | `sanitize_text(content)` antes de cada `st.markdown` | O `st.session_state.messages` é re-renderizado a cada `st.rerun()`. Como `sanitize_text` é idempotente, aplicar de novo é seguro e cobre conteúdo de sessões antigas. |

A regra: **a sanitização precisa ser idempotente** (`f(f(x)) == f(x)`) para
sobreviver às múltiplas aplicações nos pontos acima.

---

## Módulo `src/text_sanitize.py`

Toda a lógica de sanitização vive em um módulo dedicado, com duas funções
expostas:

- `sanitize_token(token)` — leve, por chunk, durante o streaming.
- `sanitize_text(text)` — completa, idempotente, sobre a string inteira.

### Ordem das transformações em `sanitize_text`

A ordem importa e cada passo justifica a posição:

1. **Normalização de whitespace** — ` ` (thin-space) e ` ` (NBSP)
   colapsados para espaço normal. Modelos europeus emitem NBSP antes de
   moeda; tipograficamente correto, mas confunde o KaTeX.
2. **Strip de legacy `\\$`** — converte `\\$` (backslash duplo + cifrão) em
   `$`. Vestígio de sessões pré-v1.5.3 que escapavam duas vezes. Roda
   antes do escape de moeda para que o `$` resultante seja capturado pela
   etapa seguinte.
3. **Escape de cifrão monetário** — `(?<!\\)\$(?=\s*\d)` casa todo `$` não
   precedido por `\` e seguido por dígito (com ou sem espaço). Substitui
   por `\$`. Esta é a etapa que distingue moeda de matemática (ver
   próxima seção).
4. **Conversão LaTeX display** — `\[...\]` → `$$...$$`. Pareamento *lazy*
   com `re.DOTALL` para não cruzar pares.
5. **Conversão LaTeX inline** — `\(...\)` → `$...$`. Mesma lógica.
6. **Strip de delimitadores desemparelhados** — `\(`, `\)`, `\[`, `\]` que
   sobraram (sem par válido) viram `(`, `)`, `[`, `]`. Cobre o caso de
   chunks SSE que cortam no meio de um delimitador.

A ordem 3 → 4 → 5 garante que os `$` introduzidos pela conversão LaTeX
**não** sejam escapados — eles são math intencional.

### `sanitize_token`

Roda em cada chunk durante o streaming. Aplica apenas as etapas 1, 2 e 3
(whitespace, legacy strip, escape de moeda). Não tenta conversão LaTeX
porque os pares `\(...\)` podem cruzar fronteira de chunk; isso é tarefa
do `sanitize_text` que roda na string já completa.

---

## Distinção entre moeda e matemática

O lookahead `(?=\s*\d)` na regex de escape é a fronteira entre os dois
universos:

- **Moeda** sempre tem dígito imediatamente após o `$` (com no máximo um
  espaço): `R$ 100`, `R$1.250`, `$50`, `US$ 5,00`.
- **Matemática** começa com letra, símbolo ou comando LaTeX: `$x^2$`,
  `$f(n) = 2n$`, `$\frac{a}{b}$`, `$\sum_i x_i$`.

A regex `(?<!\\)\$(?=\s*\d)` portanto:
- escapa `R$ 100` → `R\$ 100` (sai como cifrão literal),
- preserva `$x^2$` (não casa, não toca),
- escapa `$50` → `\$50` (USD literal),
- preserva `$\frac{a}{b}$` (não casa).

### Modelos LLM cobertos

| Família | Formato típico de math | Como é tratado |
|---|---|---|
| `openai/gpt-*`, `openai/o1*` | `\(...\)` / `\[...\]` | Conversão LaTeX (etapas 4 e 5) → `$...$` → KaTeX renderiza. |
| `anthropic/claude-*` | `$...$` nativo | Escape de moeda não casa (não há dígito após `$`); KaTeX renderiza diretamente. |
| `meta-llama/*`, `qwen/*`, `deepseek/*` | `$...$` predominante | Mesma lógica do Claude. |
| `mistralai/*`, `google/gemini-*` | mistura | Coberto pelos dois caminhos. |

Em todos os casos, moeda fica literal e matemática renderiza.

### Falsos positivos conhecidos (raros)

- LLM emitindo math que começa com dígito: `$3x + 5 = 0$`. O primeiro `$`
  seria escapado. Na prática LLMs escrevem `$f(x) = 3x + 5$`, não `$3...$`.
- `R$` solto sem dígito próximo (ex.: "preço em R$ apenas") não é escapado;
  se houver outro `$` solto na mesma linha pode haver pareamento. Caso de
  borda; o usuário pode reformular o prompt se aparecer.

---

## Helpers em `src/formatting.py` (abas estáticas)

`md_escape(text) → text.replace("$", "\\$")` é o escape **global** de `$`,
mais agressivo que o do `text_sanitize`. Continua sendo a ferramenta
correta para as abas estáticas onde:

- O conteúdo é gerado pelo próprio app (passou por `fmt_brl`).
- Não há matemática vinda de LLM para preservar.
- Cada string é renderizada uma única vez por rerun.

Uso atual:
- `src/ui/today.py` — KPI cards e deltas.
- `src/ui/month.py` — métricas, deltas, mensagens de meta.
- `src/ui/analysis.py` — texto de análise.

**Não usar `md_escape` no chat**: matar global de `$` quebraria a
matemática que o `text_sanitize` se esforça para preservar.

---

## Idempotência

`sanitize_text(sanitize_text(x)) == sanitize_text(x)` é requisito porque a
re-renderização do histórico aplica a função em todo `st.rerun()`. A
verificação por inspeção:

- `R$ 100` → run 1: `R\$ 100`. Run 2: o `$` está precedido por `\`, o
  lookbehind `(?<!\\)` bloqueia, sem mudança.
- `\(x^2\)` → run 1: conversão produz `$x^2$`. Run 2: o `$` é seguido por
  `x`, não por dígito, o lookahead `(?=\s*\d)` bloqueia, sem mudança.
- `\\$ 100` → run 1: legacy strip vira `$ 100` → escape vira `\$ 100`.
  Run 2: idem ao primeiro caso.

O teste `test_idempotent` em `tests/test_text_sanitize.py` cobre essa
propriedade.

---

## Cenários cobertos

| Entrada do LLM | Saída após `sanitize_text` | Renderização |
|---|---|---|
| `R$ 129.513` | `R\$ 129.513` | `R$ 129.513` literal |
| `R$129.513` (sem espaço) | `R\$129.513` | literal |
| `R$ 100` (NBSP) | `R\$ 100` | literal |
| `R$ 12,12 vs R$ 8,14` | `R\$ 12,12 vs R\$ 8,14` | dois cifrões literais |
| `$50 dólares` | `\$50 dólares` | literal |
| `$x^2$` | inalterado | math inline |
| `$\frac{a}{b}$` | inalterado | math inline |
| `$$\sum_i x_i$$` | inalterado | math display |
| `\(x^2\)` | `$x^2$` | math inline |
| `\[\sum x\]` | `$$\sum x$$` | math display |
| `Faturamento R$ 100 e fórmula $f(x)=2x$` | `Faturamento R\$ 100 e fórmula $f(x)=2x$` | moeda literal + math |
| `R\$ 100` (já escapado) | inalterado | literal (idempotente) |
| `\\$ 100` (legacy duplo) | `\$ 100` | literal |

---

## Checklist para diagnóstico de bugs futuros

- [ ] Toda saída do LLM passa por `sanitize_token` em
      `_stream_response` (chat.py)?
- [ ] A resposta completa passa por `sanitize_text` antes de ser
      salva em `st.session_state.messages`?
- [ ] A re-renderização do histórico chama `sanitize_text` em cada
      mensagem assistant antes de `st.markdown`?
- [ ] `sanitize_text(sanitize_text(x)) == sanitize_text(x)` para
      qualquer input testado? (rodar `pytest tests/test_text_sanitize.py`)
- [ ] Cifrão monetário (`R$ 100`) sai como `R\$ 100`?
- [ ] Math nativa (`$x^2$`) é preservada?
- [ ] Math OpenAI (`\(x^2\)`) é convertida para `$x^2$`?
- [ ] NBSP / thin-space são colapsados antes do escape de moeda?
- [ ] Para abas estáticas (`today`, `month`, `analysis`), `md_escape`
      é aplicado em toda string com `R$` que vai para `st.markdown`,
      `st.metric`, `st.expander`, `st.warning`, `st.info`?

---

## Histórico de correções e regressões

| Commit | O que mudou |
|---|---|
| `3f696e3` | `md_escape(text)` antes de `st.markdown` em `analysis.py`. |
| `de44f2a` | `md_escape(msg["content"])` no histórico do chat. |
| `d9a67dd` | `safe_stream` com `replace("$", "\\$")` no `st.write_stream`. |
| `bdf5860` | Eliminada dupla-escapagem; thin-space/NBSP colapsados no `safe_stream`. |
| `4d292ff` | Refactor para módulo unificado `text_sanitize.py`. **Introduziu regressão**: removeu o `replace("$", "\\$")` do streaming sem repor equivalente. Bug do `R$` virando math voltou ao chat (e só ao chat, porque outras abas continuaram com `md_escape`). |
| `cfc8a84` | Fixes de NaN, dead code, imports. Não tocou no escape. |
| `303d2b3` | Fix de bug de regex (uso de lambda em `re.sub` para evitar erro de back-reference). Não tocou no escape. |
| (próximo) | Restauração do escape de `$` via regex `(?<!\\)\$(?=\s*\d)` em `text_sanitize.py`, como nova etapa entre o legacy strip e a conversão LaTeX. |

---

## Como instrumentar para diagnosticar regressões

Se a renderização voltar a quebrar e não estiver claro qual etapa falhou,
adicionar temporariamente em `src/llm_client.py`, dentro do loop de
streaming (em torno da linha 260):

```python
import sys
if content:
    print(repr(content), file=sys.stderr)
    yield content
```

Provocar uma resposta com moeda e/ou matemática. No log do contêiner:

```bash
docker compose logs -f --tail=200 radtracker | grep -E "\\$|\\\\\\(|\\\\\\["
```

Os tokens brutos antes da sanitização aparecem no log, permitindo
verificar se o LLM emite `\(math\)` ou `$math$`, com ou sem NBSP, e onde
o `text_sanitize` está acertando ou falhando. Remover o `print` antes de
fazer commit.

---

## Referências

- Issue [streamlit#7898](https://github.com/streamlit/streamlit/issues/7898) — caso original do `$` virando math; resposta oficial recomenda `replace("$", "\\$")` ou `st.text`.
- Issue [streamlit#9272](https://github.com/streamlit/streamlit/issues/9272) — pedido de delimitadores customizáveis para LaTeX (aberto desde ago/2024).
- Issue [streamlit#11499](https://github.com/streamlit/streamlit/issues/11499) — pedido de flag global em `config.toml` para desligar LaTeX (aberto, sem implementação).
- PR [streamlit#12952](https://github.com/streamlit/streamlit/pull/12952) — tentativa de adicionar `latex_delimiters` parameter; fechada stale em jan/2026.
