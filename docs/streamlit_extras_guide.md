# `streamlit-extras` — Análise Completa e Guia de Referência

Guia consolidado da biblioteca **[`streamlit-extras`](https://arnaudmiribel.github.io/streamlit-extras/)**, validado contra o código-fonte oficial (versão **1.5.0**, abril/2026) — todos os 56 extras catalogados, organizados por categoria, com sinalização explícita do que está **depreciado** e qual recurso nativo do Streamlit substitui cada caso.

---

## Sumário

1. [O que é](#1-o-que-é)
2. [Quando usar (e quando não usar)](#2-quando-usar-e-quando-não-usar)
3. [Instalação e uso básico](#3-instalação-e-uso-básico)
4. [Análise estratégica: o que faz sentido em 2026](#4-análise-estratégica-o-que-faz-sentido-em-2026)
5. [Catálogo completo dos 56 extras](#5-catálogo-completo-dos-56-extras)
   - [5.1 Layout e containers](#51-layout-e-containers)
   - [5.2 Inputs e widgets interativos](#52-inputs-e-widgets-interativos)
   - [5.3 Visuais e branding](#53-visuais-e-branding)
   - [5.4 Gráficos e visualização de dados](#54-gráficos-e-visualização-de-dados)
   - [5.5 Integração com o navegador](#55-integração-com-o-navegador)
   - [5.6 Utilidades de desenvolvimento e debug](#56-utilidades-de-desenvolvimento-e-debug)
6. [Extras depreciados (e seus substitutos nativos)](#6-extras-depreciados-e-seus-substitutos-nativos)
7. [Como contribuir](#7-como-contribuir)
8. [Links úteis](#8-links-úteis)

---

## 1. O que é

`streamlit-extras` é uma **biblioteca da comunidade** que reúne componentes e utilitários que **não estão no Streamlit oficial**. É um projeto Apache-2.0, mantido por:

- **Arnaud Miribel** ([@arnaudmiribel](https://github.com/arnaudmiribel)) — engenheiro da Snowflake/Streamlit
- **Zachary Blackwood** ([@blackary](https://github.com/blackary)) — engenheiro da Streamlit
- **Lukas Masuch** — engenheiro da Streamlit

Apesar de serem todos engenheiros que trabalham com/no Streamlit, **a biblioteca não é oficial** — não tem garantias de roadmap nem ciclo de release atrelado ao core. É um sandbox onde ideias de componentes amadurecem antes (ou no lugar) de virarem features oficiais.

**Métricas (abr/2026):**
- ⭐ **956 stars** no GitHub
- 📦 **+11.600 projetos** dependem dele
- 🧩 **56 extras** ativos (50 funcionais + 6 depreciados)
- 🐍 **Python ≥ 3.10**, **Streamlit ≥ 1.54.0**
- 📅 Última versão: **1.5.0** (21/abril/2026)

Repositório: <https://github.com/arnaudmiribel/streamlit-extras>
Documentação: <https://arnaudmiribel.github.io/streamlit-extras/>

---

## 2. Quando usar (e quando não usar)

### ✅ Use quando:

- Precisa de **um componente específico** que ainda não existe no core (ex.: `cookie_manager`, `eval_javascript`, `sigma_graph`).
- Está em **fase de prototipagem** e quer ganhar velocidade.
- Quer um efeito de **polish visual** rápido (ex.: `let_it_rain`, `floating_button`, `radial_menu`).
- Precisa de uma **utilidade dev** específica (ex.: `concurrency_limiter`, `function_explorer`).

### ❌ Evite quando:

- O recurso já existe **nativamente** no Streamlit (vários extras viraram nativos — ver [seção 6](#6-extras-depreciados-e-seus-substitutos-nativos)).
- O componente é **complexo e crítico** para o produto: prefira pacotes dedicados maduros (`streamlit-aggrid`, `streamlit-folium`, `streamlit-elements`).
- Você está construindo algo que precisa **garantia de manutenção de longo prazo** — `streamlit-extras` é volátil; extras podem ser depreciados quando o core evolui.

### 🚦 Princípio geral

> Comece sempre no core. Só puxe `streamlit-extras` quando bater numa limitação concreta.

---

## 3. Instalação e uso básico

```bash
pip install streamlit-extras
# ou com uv (recomendado pelos mantenedores)
uv add streamlit-extras
```

Cada extra é importado **individualmente** do submódulo correspondente — você não importa a biblioteca inteira:

```python
from streamlit_extras.bottom_container import bottom
from streamlit_extras.let_it_rain import rain
from streamlit_extras.cookie_manager import cookie_manager
```

A convenção dos nomes:
- O **submódulo** sempre tem o nome listado neste guia (ex.: `bottom_container`).
- A **função pública** geralmente tem nome diferente (ex.: `bottom`) — confira a coluna *Import* na tabela de cada categoria.

---

## 4. Análise estratégica: o que faz sentido em 2026

Validando todos os extras contra o Streamlit atual (≥ 1.54), eles caem em **4 grupos** distintos:

### Grupo A — "Foram absorvidos pelo core" (não use mais)

6 extras estão **explicitamente marcados como depreciados** no código-fonte porque o Streamlit oficial passou a oferecer o recurso de forma nativa, melhor integrada e mais estável.

| Extra depreciado       | Substituto nativo no Streamlit                 |
| ---------------------- | ---------------------------------------------- |
| `add_vertical_space`   | `st.write("")` ou margens via CSS              |
| `app_logo`             | [`st.logo`](https://docs.streamlit.io/develop/api-reference/media/st.logo) (Streamlit 1.35+)              |
| `colored_header`       | [`st.header(divider=...)`](https://docs.streamlit.io/develop/api-reference/text/st.header)                       |
| `row`                  | [`st.columns(gap=...)`](https://docs.streamlit.io/develop/api-reference/layout/st.columns) com layout horizontal |
| `stylable_container`   | [`st.container(key=...)`](https://docs.streamlit.io/develop/api-reference/layout/st.container) (a `key` vira CSS class) |
| `tags`                 | [`st.badge`](https://docs.streamlit.io/develop/api-reference/text/st.badge) e [`st.pills`](https://docs.streamlit.io/develop/api-reference/widgets/st.pills)                       |

### Grupo B — "Ganham do core" (ainda valem em 2026)

Extras que **continuam sem equivalente nativo** e que entregam valor real:

- **`cookie_manager`**, **`local_storage_manager`** — persistência no navegador.
- **`eval_javascript`** — pequenos scripts no browser sem criar um custom component.
- **`bottom_container`** — barra fixa no rodapé (útil pra chat input genérico).
- **`floating_button`**, **`radial_menu`** — ações flutuantes / menus circulares.
- **`dataframe_explorer`** — UI automática de filtros para DataFrames.
- **`sigma_graph`**, **`three_viewer`**, **`chartjs_chart`**, **`great_tables`**, **`json_editor`**, **`image_crop`**, **`image_compare_slider`** — wrappers de bibliotecas JS sem alternativa nativa.
- **`concurrency_limiter`**, **`exception_handler`** — utilidades dev pesadas.

### Grupo C — "Polish / efeitos" (use à vontade)

- **`let_it_rain`**, **`buy_me_a_coffee`**, **`badges`**, **`avatar`**, **`star_rating`**, **`mention`**, **`keyboard_text`** — micro-componentes visuais que adicionam personalidade ao app sem peso.

### Grupo D — "Casos de nicho"

- **`jupyterlite`**, **`sandbox`**, **`function_explorer`**, **`diagrams`**, **`echo_expander`**, **`word_importances`** — úteis em contextos muito específicos (educação, debugging avançado, ML interpretability).

---

## 5. Catálogo completo dos 56 extras

> Convenção: 🟢 ativo · 🟡 funciona, mas existe alternativa nativa · 🔴 oficialmente depreciado.

### 5.1 Layout e containers

| Status | Módulo | Função | O que faz |
|---|---|---|---|
| 🔴 | `add_vertical_space` | `add_vertical_space(n)` | Insere N linhas em branco. Use `st.write("")` ou CSS. |
| 🟢 | `bottom_container` | `bottom()` | Container que **fica fixo no rodapé** da tela (útil pra barras de chat custom). |
| 🟢 | `grid` | `grid(*spec)` | Define um layout em grade declarativo: `grid([2, 1, 3], 1)` cria duas linhas com proporções específicas. |
| 🟢 | `resizable_columns` | `resizable_columns([1,1,1])` | Drop-in para `st.columns` com **divisórias arrastáveis** pelo usuário. |
| 🔴 | `row` | `row(spec)` | Container horizontal. Use `st.columns` direto. |
| 🟢 | `scroll_to_element` | `scroll_to_element(key)` | Faz scroll programático até qualquer elemento que tenha `key`. |
| 🟢 | `skeleton` | `skeleton(height=...)` | Placeholder cinza animado enquanto dados carregam (estilo Facebook/LinkedIn). |
| 🔴 | `stylable_container` | `stylable_container(key, css_styles)` | CSS arbitrário num container. Use `st.container(key=...)` + CSS no `[theme]`. |

### 5.2 Inputs e widgets interativos

| Status | Módulo | Função | O que faz |
|---|---|---|---|
| 🟢 | `card_selector` | `card_selector(options)` | Picker em formato de cards grandes com ícone, título e descrição. Versão "rica" do `st.segmented_control`. |
| 🟢 | `floating_button` | `floating_button(label)` | Botão flutuante fixo no canto inferior-direito (estilo "novo chat"). |
| 🟢 | `image_crop` | `image_crop(image)` | Recorte interativo de imagens com bordas arrastáveis. |
| 🟢 | `image_selector` | `image_selector(image)` + `show_selection()` | Permite ao usuário selecionar uma região da imagem com **lasso ou bounding box**. |
| 🟢 | `json_editor` | `json_editor(data)` | Editor JSON com syntax highlight e validação (componente React). |
| 🟢 | `keyboard_text` | `key("Ctrl+S")` | Renderiza texto com aparência de tecla de teclado (`<kbd>`). |
| 🟢 | `keyboard_url` | `keyboard_to_url(key, url)` | Cria atalho global: pressionar uma tecla abre uma URL em nova aba. |
| 🟢 | `mandatory_date_range` | `date_range_picker(...)` | `st.date_input` que **força** a seleção de dois valores (start + end). |
| 🟢 | `mention` | `mention(label, icon, url)` | Link estilo "@menção" do Notion, com ícone ao lado. |
| 🟢 | `pagination` | `pagination(items, items_per_page)` | Componente clássico de paginação numerada com ‹ › e truncamento (`1 ... 4 5 6 ... 99`). |
| 🟢 | `radial_menu` | `radial_menu(options)` | Menu radial — opções em círculo ao redor de um botão central. |
| 🟢 | `specialized_inputs` | `specialized_text_input(...)` | Inputs com validação built-in (email, url, etc.). |
| 🟢 | `star_rating` | `star_rating(value)` | Estrelas read-only para mostrar avaliações. |
| 🟢 | `stateful_button` | `button(label)` | Botão que **mantém estado** (toggle), em vez de só disparar uma vez. |
| 🟢 | `stateful_chat` | `add_message(role, content)` | Container de chat que **persiste o histórico** automaticamente em `session_state`. |
| 🟢 | `steps` | `steps(items)` | Indicador de progresso de fluxo multi-etapas (vertical/horizontal, numerado/dots). |
| 🟢 | `stodo` | `to_do(items, key)` | Lista de tarefas/checklist em Streamlit. |
| 🟢 | `stoggle` | `stoggle(summary, content)` | Toggle dropdown estilo Notion (revela conteúdo escondido). |
| 🔴 | `tags` | `tagger_component(content, tags)` | Tags coloridas estilo issue do GitHub. Use `st.badge` ou `st.pills`. |

### 5.3 Visuais e branding

| Status | Módulo | Função | O que faz |
|---|---|---|---|
| 🔴 | `app_logo` | `add_logo(url)` | Logo no topo da sidebar. Use [`st.logo`](https://docs.streamlit.io/develop/api-reference/media/st.logo). |
| 🟢 | `avatar` | `avatar(image, label, caption)` | Avatar circular com label e legenda opcional. |
| 🟢 | `badges` | `badge("pypi", name="streamlit")` | Badges prontas (PyPI, GitHub, Twitter, Buy Me a Coffee, Streamlit Cloud). |
| 🟢 | `buy_me_a_coffee` | `button(username, ...)` | Botão flutuante de "Buy Me a Coffee" para apps públicos. |
| 🔴 | `colored_header` | `colored_header(label, ...)` | Cabeçalho colorido. Use [`st.header(divider="rainbow")`](https://docs.streamlit.io/develop/api-reference/text/st.header). |
| 🟢 | `customize_running` | `center_running()` | Customiza o widget "Running..." do Streamlit (ex.: centraliza). |
| 🟢 | `let_it_rain` | `rain(emoji, ...)` | Faz "chover" emojis na tela — extensão de `st.balloons`/`st.snow`. |
| 🟢 | `metric_cards` | `style_metric_cards(...)` | Estiliza `st.metric` como cartão custom. **Hoje você pode usar `st.metric(border=True)` direto.** |

### 5.4 Gráficos e visualização de dados

| Status | Módulo | Função | O que faz |
|---|---|---|---|
| 🟢 | `chart_annotations` | `get_annotations_chart(...)` | Adiciona anotações em timestamps específicos de séries temporais Altair. |
| 🟢 | `chart_container` | (sem export — usar via `with`) | Embrulha um gráfico em abas (visualização / dados / código de export). |
| 🟢 | `chartjs_chart` | `chartjs_chart(config)` | Renderiza gráficos Chart.js com integração ao tema do Streamlit. |
| 🟢 | `dataframe_explorer` | `dataframe_explorer(df)` | Gera UI de **filtros automáticos** para qualquer DataFrame (categórico, numérico, data). |
| 🟢 | `diagrams` | `st_diagram(...)` | Renderiza diagramas Mermaid/Graphviz (wrapper de [`mingrammer/diagrams`](https://github.com/mingrammer/diagrams)). |
| 🟢 | `great_tables` | `great_tables(gt)` | Renderiza tabelas da biblioteca [Great Tables](https://posit-dev.github.io/great-tables/) (Posit). |
| 🟢 | `sigma_graph` | `sigma_graph(graph)` | Visualização de **grafos interativos com WebGL** (sigma.js). Aceita `networkx.Graph` ou dict. |
| 🟢 | `three_viewer` | `three_viewer(file)` | Viewer **3D** com controles de órbita. Suporta GLTF, GLB, OBJ, STL, PLY, FBX. |
| 🟢 | `word_importances` | `format_word_importances(words, scores)` | Destaca palavras conforme um score de importância (ML interpretability, inspirado no [Captum](https://captum.ai/)). |

### 5.5 Integração com o navegador

| Status | Módulo | Função | O que faz |
|---|---|---|---|
| 🟢 | `cookie_manager` | `cookie_manager()` | Lê/escreve **cookies do navegador** com interface dict-like. |
| 🟢 | `eval_javascript` | `eval_javascript(code)` | Executa JS arbitrário no browser e devolve o resultado pro Python. Útil pra ler `navigator.userAgent`, geolocalização etc. |
| 🟢 | `local_storage_manager` | `local_storage_manager()` | Igual ao `cookie_manager`, mas para `localStorage` (com serialização JSON automática). |
| 🟢 | `redirect` | `redirect(url)` | Redireciona o usuário programaticamente para uma URL externa ou interna. |

### 5.6 Utilidades de desenvolvimento e debug

| Status | Módulo | Função | O que faz |
|---|---|---|---|
| 🟢 | `capture` | (utilitário interno) | Captura `stdout`/`stderr` do código rodando dentro do app. |
| 🟢 | `concurrency_limiter` | `@concurrency_limiter(max_concurrency=N)` | Decorator que **limita execuções concorrentes** de uma função (rate limiting interno). |
| 🟢 | `echo_expander` | (uso via `with`) | Como `st.echo`, mas com o código dentro de um `expander` colapsado. |
| 🟢 | `exception_handler` | `set_global_exception_handler(fn)` | Sobrescreve o handler global de exceções do Streamlit (mostrar mensagem custom em prod). |
| 🟢 | `function_explorer` | `function_explorer(fn)` | Gera **automaticamente** uma UI para qualquer função Python (inspeciona signature). Marcado como "muito alpha". |
| 🟢 | `jupyterlite` | `jupyterlite()` | Embeda um **JupyterLite** completo (Python no browser via Pyodide) dentro do Streamlit. |
| 🟢 | `sandbox` | `sandbox(code)` | Executa código Streamlit **não-confiável** num sandbox (via [stlite](https://github.com/whitphx/stlite)). |

---

## 6. Extras depreciados (e seus substitutos nativos)

Esta tabela é a **mais importante** se você está começando hoje. Estes 6 extras estão marcados com `__deprecated__ = True` no código-fonte:

| Extra                  | Substituto nativo                                                                                                  | Quando o core ganhou |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------- |
| `add_vertical_space`   | `st.write("")` em loop, ou `[theme]` com mais `padding`                                                            | sempre existiu       |
| `app_logo`             | [`st.logo(image)`](https://docs.streamlit.io/develop/api-reference/media/st.logo)                                  | Streamlit 1.35       |
| `colored_header`       | [`st.header(divider="rainbow")`](https://docs.streamlit.io/develop/api-reference/text/st.header) (aceita `red`, `blue`, `green`, `orange`, `violet`, `gray`, `rainbow`) | Streamlit 1.27       |
| `row`                  | [`st.columns(gap=...)`](https://docs.streamlit.io/develop/api-reference/layout/st.columns) ou [`st.container(horizontal=True)`](https://docs.streamlit.io/develop/api-reference/layout/st.container) | Streamlit 1.30+      |
| `stylable_container`   | [`st.container(key="meu-card")`](https://docs.streamlit.io/develop/api-reference/layout/st.container) — a `key` é exposta como classe CSS, então um `st.markdown("<style>...")` mira nela | Streamlit 1.40+      |
| `tags`                 | [`st.badge`](https://docs.streamlit.io/develop/api-reference/text/st.badge) e [`st.pills`](https://docs.streamlit.io/develop/api-reference/widgets/st.pills)                                                                                                          | Streamlit 1.43+      |

> 💡 **Padrão recomendado:** se um arquivo do seu projeto importa qualquer um desses 6 extras, troque pelo equivalente nativo ao tocar nele.

---

## 7. Como contribuir

A barreira pra adicionar um extra é deliberadamente baixa. O fluxo é:

1. **Fork** do repositório <https://github.com/arnaudmiribel/streamlit-extras>.
2. Criar pasta `src/streamlit_extras/seu_extra/` com:
   - `__init__.py` definindo a função pública decorada com `@extra` e os metadados (`__title__`, `__desc__`, `__icon__`, `__author__`, `__examples__`).
   - Opcionalmente `frontend/` se for componente React (Custom Component v2).
3. Rodar `uv sync` localmente e testar com a galeria.
4. Abrir Pull Request com a flag de "new extra".

Guia oficial: <https://arnaudmiribel.github.io/streamlit-extras/contributing/>

Estrutura mínima de um extra (baseado no `stoggle`):

```python
from datetime import date
import streamlit as st
from .. import extra

@extra
def meu_componente(arg: str) -> None:
    """Docstring que aparece na galeria."""
    st.write(f"Hello {arg}")

def example():
    meu_componente("world")

__title__ = "Meu Componente"
__desc__ = "Descrição curta para a galeria."
__icon__ = "🎈"
__examples__ = [example]
__author__ = "Seu Nome"
__created_at__ = date(2026, 4, 30)
```

---

## 8. Links úteis

### Oficiais (`streamlit-extras`)
- 🌐 Documentação: <https://arnaudmiribel.github.io/streamlit-extras/>
- 📦 Repositório: <https://github.com/arnaudmiribel/streamlit-extras>
- 🐍 PyPI: <https://pypi.org/project/streamlit-extras/>
- 🤝 Guia de contribuição: <https://arnaudmiribel.github.io/streamlit-extras/contributing/>

### Streamlit oficial (referências citadas neste guia)
- API Reference: <https://docs.streamlit.io/develop/api-reference>
- Tema/config: <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>
- `st.logo`: <https://docs.streamlit.io/develop/api-reference/media/st.logo>
- `st.header` (com `divider`): <https://docs.streamlit.io/develop/api-reference/text/st.header>
- `st.container`: <https://docs.streamlit.io/develop/api-reference/layout/st.container>
- `st.columns`: <https://docs.streamlit.io/develop/api-reference/layout/st.columns>
- `st.badge`: <https://docs.streamlit.io/develop/api-reference/text/st.badge>
- `st.pills`: <https://docs.streamlit.io/develop/api-reference/widgets/st.pills>
- Custom Components: <https://docs.streamlit.io/develop/concepts/custom-components>

### Pacotes especializados (fora do `streamlit-extras`)
Quando você precisa de algo mais robusto que um extra, considere:
- **`streamlit-aggrid`** — tabelas avançadas (filtro, edição, paginação): <https://github.com/PablocFonseca/streamlit-aggrid>
- **`streamlit-folium`** — mapas Leaflet/Folium: <https://github.com/randyzwitch/streamlit-folium>
- **`streamlit-elements`** — Material UI completo no Streamlit: <https://github.com/okld/streamlit-elements>
- **`streamlit-option-menu`** — menus de navegação ricos: <https://github.com/victoryhb/streamlit-option-menu>
- **`streamlit-authenticator`** — auth completo: <https://github.com/mkhorasani/Streamlit-Authenticator>
- **`stlite`** — Streamlit rodando 100% no browser via Pyodide: <https://github.com/whitphx/stlite>

---

> **Observação final.** Como `streamlit-extras` é volátil, sempre que for adotar um extra crítico, **inspecione o código** em `src/streamlit_extras/<extra>/__init__.py` no repositório para verificar se ele já não foi marcado como `__deprecated__` na main branch antes do próximo release.
