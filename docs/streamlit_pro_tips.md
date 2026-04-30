# 25+ Dicas PRO de Streamlit — De script básico a dashboard profissional

Resumo organizado, explicado e validado contra a documentação oficial do vídeo **"25+ Streamlit PRO Tips from a Co-founder Dashboard App"** (`https://www.youtube.com/watch?v=pAPEP0j73QE`).

Cada dica traz: o que o vídeo recomenda, o motivo, o trecho de código equivalente e um link direto para a documentação oficial. Onde a transcrição diverge da documentação atual, há uma nota de **Correção**.

---

## 1. Configuração inicial da página

### Dica 1 — `st.set_page_config` com layout largo, título e ícone

Sempre comece o app definindo o layout, título e ícone da aba do navegador. Isso aproveita toda a largura da tela e dá identidade visual logo na aba.

```python
import streamlit as st

st.set_page_config(
    page_title="Stock Dashboard",
    page_icon=":material/show_chart:",
    layout="wide",
)
```

- `layout="wide"` faz o app ocupar toda a largura do navegador.
- `page_title` aparece na aba do navegador.
- `page_icon` aceita emoji, caminho de arquivo ou ícones Material UI no formato `:material/nome_do_icone:`.

Documentação: <https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config>

### Dica 2 — Ícones Material UI inline

Streamlit suporta a sintaxe `:material/nome_do_icone:` em qualquer texto markdown (títulos, labels, `st.write`, `st.metric`, abas etc.).

```python
st.write(":material/trending_up: Performance")
st.button(":material/refresh: Atualizar")
```

A grafia do nome do ícone é em **snake_case** (estilo "rounded"). Lista completa: <https://fonts.google.com/icons?icon.set=Material+Symbols&icon.style=Rounded>

Documentação: <https://docs.streamlit.io/develop/api-reference/text/st.markdown>

---

## 2. Layout em grid com cara de dashboard

### Dica 3 — Colunas com larguras desiguais

Em vez de `st.columns(2)` (colunas iguais), passe uma lista para definir proporções.

```python
left, right = st.columns([1, 3])  # left = 25%, right = 75%
```

Documentação: <https://docs.streamlit.io/develop/api-reference/layout/st.columns>

### Dica 4 — Containers com `border=True` para visual de "card"

```python
with left.container(border=True):
    st.metric("Total", "1.2k", "+5%")
```

`border=True` desenha uma borda arredondada que dá o aspecto de cartão.

Documentação: <https://docs.streamlit.io/develop/api-reference/layout/st.container>

### Dica 5 — `height="stretch"` para alinhar alturas

Quando você tem cards lado a lado, eles podem ter alturas diferentes e quebrar o grid. Force que ocupem toda a altura disponível:

```python
with left.container(border=True, height="stretch"):
    ...
with right.container(border=True, height="stretch"):
    ...
```

A altura aceita `"content"` (padrão), `"stretch"` ou um inteiro em pixels.

Documentação: <https://docs.streamlit.io/develop/api-reference/layout/st.container>

### Dica 6 — `vertical_alignment="center"` para centralizar conteúdo nos cards

Quando o card é grande mas o conteúdo é pequeno, ele "boia" no topo. Centralize:

```python
with col.container(border=True, height="stretch", vertical_alignment="center"):
    st.metric("Vencedoras", "12 / 20")
```

Valores aceitos: `"top"` (padrão), `"center"`, `"bottom"`, `"distribute"`.

> ℹ️ **Observação:** `st.columns` também aceita `vertical_alignment`, porém só com `"top" | "center" | "bottom"` (sem `"distribute"`).

Documentação: <https://docs.streamlit.io/develop/api-reference/layout/st.container>

---

## 3. Carregamento de dados e cache

### Dica 7 — Cache de dados com TTL

Evite que cada interação faça download da API novamente.

```python
@st.cache_data(ttl="6h", show_spinner=False)
def load_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    import yfinance as yf
    return yf.download(list(tickers), period="1y")
```

- `ttl="6h"` mantém os dados em cache por 6 horas (também aceita segundos ou `timedelta`).
- O argumento da função precisa ser **hashable** — por isso `tuple` em vez de `list`.

> ⚠️ **Correção em relação à transcrição.** O vídeo (na transcrição automática) menciona `st.cache_resource` para `load_data`. A documentação recomenda **`st.cache_data`** quando o retorno é dado serializável (DataFrame, dict, lista, valor). Use `st.cache_resource` apenas para recursos compartilháveis e não-serializáveis (conexão de banco, modelo de ML, cliente HTTP).

Documentação:
- `st.cache_data` → <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data>
- `st.cache_resource` → <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource>

### Dica 8 — `show_spinner=False` para esconder o spinner do cache

O spinner padrão "Running load_data..." quebra a sensação de polish. Esconda-o e, se quiser, mostre seu próprio indicador.

```python
@st.cache_data(ttl="6h", show_spinner=False)
def load_data(tickers): ...
```

Também funciona com texto custom: `show_spinner="Buscando cotações..."`.

### Dica 9 — Não envenenar o cache em caso de erro

Se a API retornar erro de rate limit e você cachear esse erro/valor vazio, todos os usuários ficam presos por 6 horas. Limpe a entrada de cache no erro:

```python
import streamlit as st
import yfinance as yf

@st.cache_data(ttl="6h", show_spinner=False)
def load_data(tickers):
    try:
        return yf.download(list(tickers), period="1y")
    except yf.exceptions.YFRateLimitError as e:
        load_data.clear()       # limpa apenas esta função
        st.error(f"Limite da Yahoo Finance: {e}")
        st.stop()                # interrompe o restante do app
```

- `funcao.clear()` apaga o cache **só dessa função** (granular).
- `st.cache_data.clear()` apaga **todos** os caches de dados (mais agressivo).

Documentação: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data>

### Dica 10 — `st.stop()` para abortar a renderização

Quando os dados falham, não faz sentido tentar desenhar gráficos vazios. `st.stop()` interrompe o script naquele ponto sem disparar exceção.

Documentação: <https://docs.streamlit.io/develop/api-reference/control-flow/st.stop>

---

## 4. Métricas e KPIs

### Dica 11 — `st.metric` com delta

Mostre variação relativa com seta colorida automática (verde/vermelho):

```python
st.metric(label="Vencedoras", value="12", delta="+3 vs ontem")
st.metric(label="Perdas", value="8", delta="-2", delta_color="inverse")
```

- `delta_color="inverse"` inverte as cores (útil quando "subir é ruim").
- `border=True` adiciona o estilo de cartão diretamente no metric.

Documentação: <https://docs.streamlit.io/develop/api-reference/data/st.metric>

---

## 5. Filtros: multiselect e pills

### Dica 12 — `st.multiselect` com texto livre

Permita que o usuário **digite novas opções** que não estavam na lista original:

```python
tickers = st.multiselect(
    "Tickers",
    options=["AAPL", "MSFT", "GOOG", "NVDA"],
    default=["AAPL", "MSFT"],
    accept_new_options=True,   # aceita texto fora das opções
    max_selections=10,         # bom par para limitar crescimento
)
```

Documentação: <https://docs.streamlit.io/develop/api-reference/widgets/st.multiselect>

### Dica 13 — `st.pills` com mapa label → valor

`st.pills` mostra opções como botões em formato de "pílulas". Para exibir um label bonito e usar um valor diferente internamente, mantenha um dicionário e use `format_func`:

```python
horizon_map = {"1D": "1d", "1W": "5d", "1M": "1mo", "1Y": "1y"}

choice = st.pills(
    "Horizonte",
    options=list(horizon_map.keys()),  # mostra "1D", "1W", ...
    default="1M",
    selection_mode="single",
)
period = horizon_map[choice]            # "1mo"
data = load_data(tickers, period=period)
```

Documentação: <https://docs.streamlit.io/develop/api-reference/widgets/st.pills>

### Dica 14 — `st.info` para estados vazios

Em vez de mostrar gráfico em branco, oriente o usuário:

```python
if not tickers:
    st.info(":material/info: Selecione ao menos um ticker para começar.")
    st.stop()
```

Documentação: <https://docs.streamlit.io/develop/api-reference/status/st.info>

---

## 6. Pipeline de dados para gráficos

### Dica 15 — Normalize os preços para comparação justa

Comparar uma ação de US$ 100 com outra de US$ 1.000 no mesmo eixo distorce a leitura. Normalize tudo para começar em **1**:

```python
normalized = df.div(df.iloc[0])
```

### Dica 16 — Wide → long com `df.melt()` para Altair

Altair (e a maioria das ferramentas grammar-of-graphics) prefere o formato **tidy / long**.

```python
long = normalized.reset_index().melt(
    id_vars="Date",
    var_name="Ticker",
    value_name="Price",
)
```

### Dica 17 — Grade dinâmica de cards com `enumerate`

Para mostrar um mini-gráfico por ticker em uma grade de N colunas:

```python
cols = st.columns(4)
for i, ticker in enumerate(tickers):
    with cols[i % 4].container(border=True):
        st.altair_chart(make_chart(long, ticker), use_container_width=True)
```

---

## 7. Estilo dos gráficos (Altair)

### Dica 18 — Escala de cores categórica fixa

Em vez de cores aleatórias, defina explicitamente:

```python
import altair as alt

color = alt.Color(
    "Ticker:N",
    scale=alt.Scale(range=["#E0413E", "#9AA0A6"]),  # vermelho + cinza
)
```

### Dica 19 — Tooltips interativas

Permita exploração ao passar o mouse:

```python
chart = (
    alt.Chart(long)
    .mark_line()
    .encode(
        x="Date:T",
        y="Price:Q",
        color=color,
        tooltip=["Date:T", "Ticker:N", alt.Tooltip("Price:Q", format=".2f")],
    )
)
```

### Dica 20 — Legenda na parte inferior em cards pequenos

Em mini-gráficos, a legenda lateral come muito espaço. Mande para baixo:

```python
color = alt.Color(
    "Ticker:N",
    legend=alt.Legend(orient="bottom"),
)
```

Documentação Altair (oficial integrada ao Streamlit): <https://docs.streamlit.io/develop/api-reference/charts/st.altair_chart>

---

## 8. Tema customizado profissional

### Dica 21 — Crie um `.streamlit/config.toml` com tema dark customizado

```toml
# .streamlit/config.toml
[theme]
base = "dark"
primaryColor = "#7C5CFF"
backgroundColor = "#0E0B1F"
secondaryBackgroundColor = "#1A1530"
borderColor = "#2A2440"
dataframeHeaderBackgroundColor = "#1A1530"
```

Chaves principais:
- `base` → `"light"` ou `"dark"` (ponto de partida).
- `primaryColor` → cor de destaque (botões, foco, seleção).
- `backgroundColor` / `secondaryBackgroundColor` → fundo do app e dos widgets.
- `borderColor` → bordas dos widgets e containers.
- `dataframeHeaderBackgroundColor` → cabeçalho do `st.dataframe`.

Documentação: <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>

### Dica 22 — Fonte custom do Google Fonts (ex.: Space Grotesk)

```toml
[theme]
font = "Space Grotesk"
headingFont = "Space Grotesk"
baseFontSize = 16
baseFontWeight = 400

# Tamanhos por nível de heading (h1..h6)
headingFontSizes = ["2.25rem", "1.75rem", "1.5rem", "1.25rem", "1.125rem", "1rem"]
headingFontWeights = [700, 700, 600, 600, 500, 500]

[[theme.fontFaces]]
family = "Space Grotesk"
url = "https://fonts.gstatic.com/s/spacegrotesk/v15/V8mDoQDjQSkFtoMM3T6r8E7mF71Q-gOoraIAEj7aUUM.woff2"
weight = "300 700"
style = "normal"
```

Para hospedar fontes locais com seu app, ative `server.enableStaticServing = true`.

Documentação:
- Tema (cores e bordas): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>
- Tema (fontes): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts>
- `[[theme.fontFaces]]`: <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts>

> ℹ️ **Importante:** o tema **não** se aplica automaticamente aos gráficos Altair/Plotly. Você precisa definir as cores explicitamente no encoding do gráfico (ver Dica 18).

---

## 9. Compartilhamento de estado via URL

### Dica 23 — Inicializar `session_state` a partir da URL

Permita que o usuário compartilhe um link com filtros já aplicados.

```python
if "tickers" not in st.session_state:
    qp = st.query_params.get_all("stocks")  # lista de strings
    st.session_state.tickers = qp or ["AAPL", "MSFT"]
```

Documentação: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params>

### Dica 24 — Usar o `session_state` como `default` do widget

```python
selected = st.multiselect(
    "Tickers",
    options=ALL_TICKERS,
    default=[t for t in st.session_state.tickers if t in ALL_TICKERS],
    accept_new_options=True,
    key="tickers",
)
```

### Dica 25 — Sincronizar a URL ao mudar a seleção

Depois de o usuário interagir, espelhe o estado de volta na query string:

```python
st.query_params["stocks"] = selected   # aceita lista para repetir a chave
# URL resultante: ...?stocks=AAPL&stocks=MSFT
```

> 💡 **Atalho moderno:** widgets como `st.multiselect` e `st.pills` aceitam `bind="query-params"` para sincronizar automaticamente com a URL, sem precisar do passo manual de leitura/escrita. Verifique a versão do Streamlit usada (recurso recente).

Documentação: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params>

---

## 10. Checklist final do "look profissional"

Antes de publicar, garanta que seu app tem:

- [ ] `st.set_page_config(layout="wide", page_title=..., page_icon=...)`
- [ ] Cards com `st.container(border=True, height="stretch")`
- [ ] Métricas com `delta`
- [ ] Filtros agrupados em uma única coluna lateral ou cabeçalho
- [ ] `st.cache_data(ttl=..., show_spinner=False)` em todas as chamadas externas
- [ ] Tratamento de erro com `funcao.clear()` + `st.stop()`
- [ ] `.streamlit/config.toml` com paleta e fonte custom
- [ ] Cores de gráfico definidas explicitamente (não confiar no tema)
- [ ] `st.info` em estados vazios em vez de gráficos em branco
- [ ] URL refletindo os filtros (compartilhável)

---

## Referências oficiais

- API Reference: <https://docs.streamlit.io/develop/api-reference>
- Tema (cores/bordas): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>
- Tema (fontes): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts>
- Cache: <https://docs.streamlit.io/develop/concepts/architecture/caching>
- `st.query_params`: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params>
- Vídeo original: <https://www.youtube.com/watch?v=pAPEP0j73QE>
