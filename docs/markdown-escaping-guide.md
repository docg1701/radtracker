# Guia: Escape de `$` no Markdown do Streamlit

## Problema

O frontend do Streamlit (`react-markdown` + `micromark-extension-math` +
`rehype-katex`) trata pares de `$...$` como matemática inline. Texto
contendo moeda brasileira (`R$ 1.250,00`), americana (`$50`) ou simples
referência à notação (`R$`, `"R$"`, `**R$**`) tem múltiplos `$` no mesmo
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
sanitização que escapa apenas `$` em **contexto inequívoco de moeda**,
preservando matemática vinda de LLMs tanto em formato KaTeX nativo
(`$x^2$`) quanto em formato OpenAI (`\(x^2\)`).

---

## Arquitetura: quatro pontos de aplicação

A sanitização acontece em quatro pontos do fluxo, todos em
`src/ui/chat.py`:

| Ponto | Local | Função | Razão |
|---|---|---|---|
| Streaming token a token | `_stream_response` | `sanitize_token(token)` em cada chunk SSE | Cada chunk é parseado parcialmente; um `$` solto pode acionar pareamento espúrio com cifrão de chunks anteriores antes do stream terminar. |
| Salvamento da resposta | `_stream_response` | `sanitize_text(response)` na string completa | Conserta casos que cruzam fronteira de chunk (ex.: `\(` em um chunk e `\)` no seguinte) que o token-level não pega. |
| Re-renderização do histórico | loop em `render_chat_tab` | `sanitize_text(content)` antes de cada `st.markdown` | O `st.session_state.messages` é re-renderizado a cada `st.rerun()`. Como `sanitize_text` é idempotente, aplicar de novo é seguro e cobre conteúdo de sessões antigas. |
| Mensagens do usuário (`role=user`) | mesmo loop em `render_chat_tab` + save em `chat_input` | `sanitize_text(content)` em **todos** os roles, não só assistant | Pergunta do usuário com 2+ `$` (ex.: "você escreve R$ sem o $?") sofre o mesmo bug que resposta do LLM. Tratar igual. |

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

1. **Normalização de whitespace** — ` ` (thin-space) e ` ` (NBSP)
   colapsados para espaço normal. Modelos europeus emitem NBSP antes de
   moeda; tipograficamente correto, mas confunde a tokenização do KaTeX.
2. **Strip de legacy `\\$`** — converte `\\$` (backslash duplo + cifrão) em
   `$`. Vestígio de sessões pré-v1.5.3 que escapavam duas vezes. Roda
   antes do escape de moeda para que o `$` resultante seja capturado pela
   etapa seguinte.
3. **Escape de cifrão monetário** — regex `(?<=[A-Za-z])\$|(?<!\\)\$(?=\s*\d)`
   casa `$` em qualquer contexto inequívoco de moeda (ver próxima seção).
   Substitui por `\$`. Esta etapa distingue moeda de matemática.
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

## A regex de escape de moeda

A regex correta é uma **alternação de duas patterns**:

```python
_CURRENCY_DOLLAR_RE = re.compile(r"(?<=[A-Za-z])\$|(?<!\\)\$(?=\s*\d)")
```

Decomposição:

| Pattern | Casa quando | Cobre |
|---|---|---|
| `(?<=[A-Za-z])\$` | `$` precedido por letra ASCII | sufixos de moeda: `R$`, `US$`, `EUR$`, `HK$`, `S$` — independente do que vem depois |
| `(?<!\\)\$(?=\s*\d)` | `$` não escapado, seguido por whitespace + dígito | prefixos de valor: `$50`, `$ 1.250,00`, `$ 5,00` |

A primeira pattern não precisa do lookbehind `(?<!\\)` porque letra e `\`
são mutuamente exclusivos: se o caractere anterior é letra, não é `\`. A
proteção contra dupla-escapagem vem grátis.

### Distinção entre moeda e matemática

A regra empírica é: o `$` é **moeda** quando há **letra antes** ou
**dígito depois**. É **matemática** quando está em posição neutra — sem
letra antes, sem dígito depois — abrindo conteúdo LaTeX-ish.

| Contexto | Exemplo | Pattern que casa |
|---|---|---|
| Sufixo de moeda | `R$`, `US$`, `R$**`, `"R$"`, `R$/dia`, `R$,` | 1 (letra antes) |
| Prefixo de valor | `$50`, `$ 100` | 2 (dígito depois) |
| Sufixo + valor | `R$ 100`, `US$ 5,00` | 1 e 2 (qualquer um basta) |
| Já escapado | `R\$`, `\$50` | nenhum (idempotência) |
| Math inline | `$x^2$`, `$f(n)$`, `$\frac{a}{b}$` | nenhum (preservado) |
| Math display | `$$\sum x$$` | nenhum (preservado) |
| Math após espaço | `valor $x$ é positivo` | nenhum (preservado) |

### Modelos LLM cobertos

| Família | Formato típico de math | Como é tratado |
|---|---|---|
| `openai/gpt-*`, `openai/o1*` | `\(...\)` / `\[...\]` | Conversão LaTeX (etapas 4 e 5) → `$...$` → KaTeX renderiza. |
| `anthropic/claude-*` | `$...$` nativo | Regex de moeda não casa em math (não há letra antes nem dígito depois); KaTeX renderiza diretamente. |
| `meta-llama/*`, `qwen/*`, `deepseek/*` | `$...$` predominante | Mesma lógica do Claude. |
| `mistralai/*`, `google/gemini-*` | mistura | Coberto pelos dois caminhos. |

**Observação importante**: independente do formato de math escolhido pelo
modelo, qualquer modelo escrevendo em português brasileiro emite `R$` em
prosa (sufixo de moeda, listagem de valores, ou referência meta à
notação). O pattern 1 da regex cobre esse caso para todos os modelos.

### Falso positivo conhecido

Matemática colada a uma palavra sem espaço, ex.: `equação$x$`. O `$`
inicial seria escapado pelo pattern 1 (precedido por `o`, letra), e a
fórmula renderizaria como literal `$x$`. LLMs nunca emitem assim na
prática — convenção é sempre `equação $x$` com espaço. Se aparecer, é
cosmético; nunca causa o bug oposto de texto virando math.

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
verificação por inspeção dos casos críticos:

- `R$ 100` → run 1: pattern 1 casa (R antes), escapa → `R\$ 100`.
  Run 2: lookbehind `(?<=[A-Za-z])` precisa de letra; vê `\` antes do
  `$`, falha. Pattern 2 tem `(?<!\\)`, que falha porque `\` está antes.
  Sem mudança.

- `R$` (solto) → run 1: pattern 1 casa, escapa → `R\$`.
  Run 2: idem ao primeiro caso. Sem mudança.

- `\(x^2\)` → run 1: regex de moeda não casa (nem letra antes nem dígito
  depois). Conversão LaTeX produz `$x^2$`. Run 2: o primeiro `$` é
  precedido pelo que veio antes do `\(` original (espaço típico) — não
  letra, pattern 1 falha. Seguido por `x`, não dígito, pattern 2 falha.
  Idempotente.

- `$x^2$` → run 1: pattern 1 falha (nada antes do primeiro `$`, ou espaço,
  não letra; segundo `$` precedido por `2`, não letra). Pattern 2 falha
  (`x` não é dígito). Sem mudança. Run 2: idem.

- `\\$ 100` → run 1: legacy strip vira `$ 100`. Pattern 2 casa (espaço +
  dígito depois), escapa → `\$ 100`. Run 2: ambos patterns bloqueados
  pelo `\`. Sem mudança.

O teste `test_currency_idempotent` em `tests/test_text_sanitize.py` cobre
essa propriedade.

---

## Cenários cobertos

| Entrada | Saída após `sanitize_text` | Renderização |
|---|---|---|
| `R$ 129.513` | `R\$ 129.513` | `R$ 129.513` literal |
| `R$129.513` (sem espaço) | `R\$129.513` | literal |
| `R$ 100` (NBSP) | `R\$ 100` | literal |
| `R$ 12,12 vs R$ 8,14` | `R\$ 12,12 vs R\$ 8,14` | dois cifrões literais |
| `R$` (solto) | `R\$` | literal |
| `**R$**` (LLM em negrito) | `**R\$**` | bold com `R$` literal |
| `"R$"` (entre aspas) | `"R\$"` | literal |
| `R$/dia` (sufixo de unidade) | `R\$/dia` | literal |
| `R$,` (cifrão antes de vírgula) | `R\$,` | literal |
| `R$.` (cifrão antes de ponto) | `R\$.` | literal |
| `R$\n` (fim de linha) | `R\$\n` | literal |
| `US$)` (cifrão antes de parêntese) | `US\$)` | literal |
| `valor em R$ apenas` | `valor em R\$ apenas` | literal |
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

## O que **não** é responsabilidade do sanitize

LLMs (especialmente OpenAI e modelos STEM) podem emitir **comandos LaTeX
órfãos sem delimitadores**, ex.:

```
Gap restante: G = M - F = 33\,300 - 9\,430 = 23\,870 \text{ R$}
P_{\text{necessária}} = \frac{G}{6} = 3\,978
```

Esses `\,`, `\text{...}`, `\frac{...}{...}`, `_{...}`, `^{...}` aparecem
fora de `$...$` ou `\(...\)`, então o KaTeX não toca neles e o usuário
vê os comandos como texto literal.

**Isso não é bug do `text_sanitize` e não deve ser tratado lá.** A
solução é instruir no prompt do sistema (`src/ui/settings.py:53-62`) que
o LLM **não use sintaxe LaTeX** e apresente fórmulas em notação
aritmética simples:

> "Apresente fórmulas em texto simples, sem usar sintaxe LaTeX (sem
> `\frac`, `\text`, `\,`, `\sum`, `\sqrt`). Use apenas notação aritmética
> comum: `(33.300 − 9.430) ÷ 6 = 3.978`."

Implementar parser de subset de LaTeX para "consertar" output do LLM em
runtime é caminho de muita dívida técnica, sem cobertura geral (KaTeX
tem centenas de comandos), e ortogonal ao escopo do módulo.

---

## Checklist para diagnóstico de bugs futuros

- [ ] Toda saída do LLM passa por `sanitize_token` em
      `_stream_response` (chat.py)?
- [ ] A resposta completa passa por `sanitize_text` antes de ser
      salva em `st.session_state.messages`?
- [ ] A re-renderização do histórico chama `sanitize_text` em **todas**
      as mensagens (assistant **e** user) antes de `st.markdown`?
- [ ] Mensagens do usuário (`role=user`) também passam por
      `sanitize_text` no momento do save (defesa em profundidade)?
- [ ] `sanitize_text(sanitize_text(x)) == sanitize_text(x)` para
      qualquer input testado? (rodar `pytest tests/test_text_sanitize.py`)
- [ ] A regex casa `R$` independente do que vem depois (pontuação,
      letra, fim de linha, dígito)?
- [ ] Cifrão monetário (`R$ 100`, `R$**`, `"R$"`, `R$/dia`) sai sempre
      como `\$`?
- [ ] Math nativa (`$x^2$`) é preservada (regex não casa)?
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
| `<commit-fix-v1>` | Primeiro fix do bug do `4d292ff`: regex `(?<!\\)\$(?=\s*\d)` em `text_sanitize.py`, escapa `$` apenas quando seguido por dígito. Cobriu `R$ 100`, `R$129`, `$50`. Falhou em `R$**`, `"R$"`, `R$/dia`, `R$,`, `R$\n` — todos casos onde o LLM usa `R$` como token simbólico, não amount. |
| `<commit-fix-v2>` | Regex estendida para `(?<=[A-Za-z])\$\|(?<!\\)\$(?=\s*\d)`. Adiciona alternativa "letra antes do `$`", cobrindo todo sufixo de moeda independente do que vem depois. Fecha os gaps do v1. |
| `<commit-fix-v3>` | Aplicar `sanitize_text` também a mensagens com `role=user` em `chat.py`. Antes, a pergunta do usuário com 2+ `$` quebrava porque bypassava o pipeline (o `if msg["role"] == "assistant":` no loop de render). |

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

Para reproduzir a renderização do frontend sem subir o app:

```python
# uv pip install markdown-it-py mdit-py-plugins
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from src.text_sanitize import sanitize_text

md = MarkdownIt("commonmark").use(dollarmath_plugin)
texto = "..."  # output do LLM ou input do usuário
print(md.render(sanitize_text(texto)))
# se aparecer <span class="math"...>, KaTeX vai renderizar como fórmula
```

Aproxima bem o comportamento do `micromark-extension-math` que o
Streamlit usa.

---

## Referências

- Issue [streamlit#7898](https://github.com/streamlit/streamlit/issues/7898) — caso original do `$` virando math; resposta oficial recomenda `replace("$", "\\$")` ou `st.text`.
- Issue [streamlit#9272](https://github.com/streamlit/streamlit/issues/9272) — pedido de delimitadores customizáveis para LaTeX (aberto desde ago/2024).
- Issue [streamlit#11499](https://github.com/streamlit/streamlit/issues/11499) — pedido de flag global em `config.toml` para desligar LaTeX (aberto, sem implementação).
- PR [streamlit#12952](https://github.com/streamlit/streamlit/pull/12952) — tentativa de adicionar `latex_delimiters` parameter; fechada stale em jan/2026.
