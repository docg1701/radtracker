# Guia: Escape de `$` no Markdown do Streamlit — radtracker v1.5.8

## Problema

O parser markdown do Streamlit (`pulldown-cmark` + KaTeX) trata pares
`$...$` como matemática inline. Texto contendo moeda brasileira
(`R$ 1.250,00`) ou referência à notação (`R$`, `**R$**`, `R$)`) tem
múltiplos `$` no mesmo parágrafo, e o KaTeX pareia o primeiro com um
seguinte: o conteúdo entre eles vira fórmula em fonte serifada/verde,
os cifrões delimitadores somem da tela.

A Streamlit não oferece flag de configuração nem parâmetro em
`st.markdown` para desligar LaTeX. A solução adotada é um pipeline de
sanitização que escapa `$` apenas em **contexto inequívoco de moeda**
(`R$`), preservando matemática (`$x^2$`, `$\frac{a}{b}$`).

---

## Arquitetura

A sanitização acontece em três pontos, todos em `src/ui/chat.py`:

| Ponto | Função | Razão |
|---|---|---|
| Streaming token a token | `sanitize_token(token)` | Evita que `R$100` abra math durante o streaming |
| Salvamento da resposta | `sanitize_text(response)` | Converte `\(...\)` e aplica escape de moeda na string completa |
| Re-renderização (assistant) | `sanitize_text(content)` | Idempotente — cobre conteúdo de sessões antigas |

**Mensagens do usuário (`role=user`) NÃO passam por sanitização.**
O texto do usuário é renderizado como-is com `st.markdown`. Se o usuário
digitar `R$` sem espaço, pode quebrar visualmente — mas isso é raro e o
dano é cosmético e temporário (some no próximo rerun).

---

## Módulo `src/text_sanitize.py`

Duas funções públicas:

- `sanitize_token(token)` — leve, por chunk, durante streaming.
  Colapsa thin-space/NBSP, limpa legacy `\\$`, escapa `R$`.
- `sanitize_text(text)` — completa, idempotente, string inteira.
  Mesmo que token + conversão LaTeX + unmatched cleanup.

### Ordem das transformações em `sanitize_text`

1. **Normalização de whitespace** — thin-space (`\u202f`) e NBSP
   (`\u00a0`) → espaço normal.
2. **Strip de legacy `\\$`** — vestígio de sessões pré-v1.5.3.
3. **Escape de `R$`** — regex `(?<=R)\$(?![a-zA-Z\\])` (ver abaixo).
4. **Conversão LaTeX display** — `\[...\]` → `$$...$$` (pareada, lazy).
5. **Conversão LaTeX inline** — `\(...\)` → `$...$` (pareada, lazy).
6. **Unmatched cleanup** — `\(`, `\)`, `\[`, `\]` órfãos viram
   `(`, `)`, `[`, `]`.

A ordem 3 → 4 → 5 garante que os `$` introduzidos pela conversão
LaTeX **não** sejam re-escapados.

---

## A regex de escape: `(?<=R)\$(?![a-zA-Z\\])`

Decomposição:

| Parte | Significado |
|---|---|
| `(?<=R)` | `$` precedido pela letra `R` (prefixo do Real brasileiro) |
| `\$` | o próprio cifrão |
| `(?![a-zA-Z\\])` | NÃO seguido de letra ou backslash (preserva `R$x` e `R$\frac`) |

### Distinção entre moeda e matemática

| Contexto | Regex casa? | Resultado |
|---|---|---|
| `R$ 100` | ✅ | `R\$ 100` (literal) |
| `R$100` | ✅ | `R\$100` (literal) |
| `**R$**` | ✅ (`$` seguido de `*`, não letra/backslash) | `**R\$**` (bold com cifrão) |
| `R$)` | ✅ | `R\$`)` (literal) |
| `R$"` | ✅ | `R\$"` (literal) |
| `R$/dia` | ✅ | `R\$/dia` (literal) |
| `$50` (sem R) | ❌ (não tem `R` antes) | preservado — pode ser math `$50$` |
| `$x^2$` | ❌ (não tem `R` antes) | preservado — math inline |
| `$25\times4$` | ❌ | preservado — math com dígito |
| `$\frac{a}{b}$` | ❌ | preservado — math inline |
| `$$\sum x$$` | ❌ | preservado — math display |
| `\(x^2\)` | ❌ (não tem `$` visível ainda) | etapa 5 converte → `$x^2$` |
| `R\$ 100` | ❌ (`$` precedido por `\`) | idempotente |
| `\\$ 100` | ❌ (etapa 2 limpa → `$ 100`; não tem `R` antes) | `$ 100` literal |

### Por que NÃO escapamos `$` seguido de dígito sem `R`?

Versões anteriores (v1.5.6–v1.5.7) tentaram `$(?=\s*\d)` para pegar
`$50` standalone. Isso quebrou fórmulas como `$25\times4 = 100$`
porque o `$2` era escapado. No contexto de radiologia brasileira,
valores monetários sempre usam prefixo `R$` — o caso `$50` sem `R`
simplesmente não ocorre.

---

## Cenários cobertos

| Entrada | Saída | Renderização |
|---|---|---|
| `R$ 129.513` | `R\$ 129.513` | `R$ 129.513` literal |
| `R$129.513` | `R\$129.513` | literal |
| `R$ 100` (NBSP) | `R\$ 100` | literal |
| `R$ 12,12 vs R$ 8,14` | `R\$ 12,12 vs R\$ 8,14` | dois cifrões literais |
| `**R$**` | `**R\$**` | bold com `R$` literal |
| `"R$"` | `"R\$"` | literal |
| `R$/dia` | `R\$/dia` | literal |
| `$x^2$` | inalterado | math inline |
| `$\frac{a}{b}$` | inalterado | math inline |
| `$25\times4 = 100$` | inalterado | math inline |
| `$$\sum x$$` | inalterado | math display |
| `\(x^2\)` | `$x^2$` | math inline |
| `Faturamento R$ 100 e $f(x)=2x$` | `Faturamento R\$ 100 e $f(x)=2x$` | moeda + math |
| `R\$ 100` (já escapado) | inalterado | literal (idempotente) |
| `\\$ 100` (legacy) | `$ 100` | literal |

---

## O que NÃO é coberto

1. **LaTeX órfão sem delimitadores**: LLMs podem emitir `\frac`, `\text`,
   `\,` fora de `$...$`. O KaTeX ignora, o usuário vê os comandos crus.
   **Solução**: instruir no prompt da IA para usar notação aritmética
   simples, não LaTeX.

2. **`$` sem `R` em texto explicativo**: LLM discutindo o símbolo `$`
   escreve `"símbolo $"`. Sem `R` antes, sem dígito depois → não
   escapado. Se houver outro `$` no mesmo parágrafo, pode parear.
   **Frequência**: raríssimo no domínio do app.

3. **`R$x$` (math colado em R)**: `R$` seguido de letra → regex não
   escapa (preserva possível math). Se era moeda, o `$` fica solto.
   **Frequência**: nunca acontece — LLMs separam moeda de fórmula.

---

## Função `md_escape` em `src/formatting.py`

`md_escape(text) → text.replace("$", "\\$")` é o escape **global** para
as abas estáticas (`today`, `month`, `analysis`), onde:
- O conteúdo é gerado pelo próprio app (passou por `fmt_brl`).
- Não há matemática vinda de LLM.
- Cada string é renderizada uma única vez.

**NÃO usar `md_escape` no chat** — mataria matemática legítima.

---

## Idempotência

`sanitize_text(sanitize_text(x)) == sanitize_text(x)` é verificado por:

- `R$ 100` → run 1: `R\$ 100`. Run 2: `(?<=R)` vê `\` antes do `$`,
  falha → sem mudança.
- `\(x^2\)` → run 1: `$x^2$`. Run 2: sem `\(` → sem mudança.
- `$x^2$` → regex de moeda não casa. Sem mudança.
- `\\$ 100` → run 1: `$ 100` (etapa 2 limpa, etapa 3 não casa sem R).
  Run 2: sem `\\$` → sem mudança.

Teste: `test_currency_idempotent` + `test_idempotent` em
`tests/test_text_sanitize.py`.

---

## Histórico de evolução da regex

| Versão | Regex | O que quebrou |
|---|---|---|
| v1.5.5 | `\[→$$`, `\(→$` (4 regexes standalone) | `$` não escapado; `\(` sozinho abria math |
| v1.5.6 | `(?<!\\)\$(?=\s*\d)` | Escapava `$25` em `$25\times4$` — matava fórmula |
| v1.5.7 | `(?<=[A-Za-z])\$\|(?<!\\)\$(?=\s*\d)` | `[A-Za-z]` pegava `x$` fechando math |
| **v1.5.8** | **`(?<=R)\$(?![a-zA-Z\\])`** | **Estável — R$ em qq contexto, math preservado** |

---

## Testes

```bash
uv run pytest tests/test_text_sanitize.py -v   # 35 testes
uv run pytest tests/ -v                         # 189 total
```

## Referências

- [pulldown-cmark math spec](https://pulldown-cmark.github.io/pulldown-cmark/specs/math.html)
- [st.markdown — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/text/st.markdown)
- [streamlit#7898](https://github.com/streamlit/streamlit/issues/7898) — caso original; resposta oficial recomenda `replace("$", "\\$")`
- [streamlit#9272](https://github.com/streamlit/streamlit/issues/9272) — pedido de delimitadores customizáveis (aberto)
