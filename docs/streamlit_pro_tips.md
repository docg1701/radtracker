# 25+ Streamlit PRO Tips — From basic script to professional dashboard

<!-- markdownlint-disable MD013 -->

An organized summary, explained and validated against the official docs, of the
video **"25+ Streamlit PRO Tips from a Co-founder Dashboard App"**
(`https://www.youtube.com/watch?v=pAPEP0j73QE`).

Each tip includes: what the video recommends, the reason, the equivalent code
snippet, and a direct link to the official documentation. Where the transcript
diverges from current docs, there is a **Correction** note.

---

## 1. Initial page configuration

### Tip 1 — `st.set_page_config` with wide layout, title and icon

Always start the app by defining the layout, browser-tab title and icon. This
uses the full screen width and gives the tab a visual identity.

```python
import streamlit as st

st.set_page_config(
    page_title="Stock Dashboard",
    page_icon=":material/show_chart:",
    layout="wide",
)
```

- `layout="wide"` makes the app fill the whole browser width.
- `page_title` shows in the browser tab.
- `page_icon` accepts an emoji, a file path, or Material UI icons in the
  `:material/icon_name:` format.

Docs: <https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config>

### Tip 2 — Inline Material UI icons

Streamlit supports the `:material/icon_name:` syntax in any markdown text
(titles, labels, `st.write`, `st.metric`, tabs, etc.).

```python
st.write(":material/trending_up: Performance")
st.button(":material/refresh: Refresh")
```

Icon names are written in **snake_case** (the "rounded" style). Full list:
<https://fonts.google.com/icons?icon.set=Material+Symbols&icon.style=Rounded>

Docs: <https://docs.streamlit.io/develop/api-reference/text/st.markdown>

---

## 2. Dashboard-style grid layout

### Tip 3 — Columns with unequal widths

Instead of `st.columns(2)` (equal columns), pass a list to define proportions.

```python
left, right = st.columns([1, 3])  # left = 25%, right = 75%
```

Docs: <https://docs.streamlit.io/develop/api-reference/layout/st.columns>

### Tip 4 — `border=True` containers for a "card" look

```python
with left.container(border=True):
    st.metric("Total", "1.2k", "+5%")
```

`border=True` draws a rounded border that gives the card look.

Docs: <https://docs.streamlit.io/develop/api-reference/layout/st.container>

### Tip 5 — `height="stretch"` to align card heights

Side-by-side cards can have different heights and break the grid. Force them
to fill all available height:

```python
with left.container(border=True, height="stretch"):
    ...
with right.container(border=True, height="stretch"):
    ...
```

Height accepts `"content"` (default), `"stretch"`, or an integer in pixels.

Docs: <https://docs.streamlit.io/develop/api-reference/layout/st.container>

### Tip 6 — `vertical_alignment="center"` to center card content

When the card is tall but the content is short, it "floats" at the top. Center it:

```python
with col.container(border=True, height="stretch", vertical_alignment="center"):
    st.metric("Winners", "12 / 20")
```

Accepted values: `"top"` (default), `"center"`, `"bottom"`, `"distribute"`.

> ℹ️ **Note:** `st.columns` also accepts `vertical_alignment`, but only
> `"top" | "center" | "bottom"` (no `"distribute"`).

Docs: <https://docs.streamlit.io/develop/api-reference/layout/st.container>

---

## 3. Data loading and caching

### Tip 7 — Data cache with TTL

Avoid re-downloading from the API on every interaction.

```python
@st.cache_data(ttl="6h", show_spinner=False)
def load_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    import yfinance as yf
    return yf.download(list(tickers), period="1y")
```

- `ttl="6h"` keeps the data cached for 6 hours (also accepts seconds or `timedelta`).
- The function argument must be **hashable** — hence `tuple` instead of `list`.

> ⚠️ **Correction vs. the transcript.** The video (in the automatic
> transcript) mentions `st.cache_resource` for `load_data`. The docs recommend
> **`st.cache_data`** when the return value is serializable data (DataFrame,
> dict, list, scalar). Use `st.cache_resource` only for shareable,
> non-serializable resources (DB connection, ML model, HTTP client).

Docs:

- `st.cache_data` → <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data>
- `st.cache_resource` → <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource>

### Tip 8 — `show_spinner=False` to hide the cache spinner

The default "Running load_data..." spinner breaks the polish. Hide it and, if
you want, show your own indicator.

```python
@st.cache_data(ttl="6h", show_spinner=False)
def load_data(tickers): ...
```

Custom text also works: `show_spinner="Fetching quotes..."`.

### Tip 9 — Don't poison the cache on errors

If the API returns a rate-limit error and you cache that error/empty value,
every user is stuck for 6 hours. Clear the cache entry on error:

```python
import streamlit as st
import yfinance as yf

@st.cache_data(ttl="6h", show_spinner=False)
def load_data(tickers):
    try:
        return yf.download(list(tickers), period="1y")
    except yf.exceptions.YFRateLimitError as e:
        load_data.clear()       # clears only this function's cache
        st.error(f"Yahoo Finance limit: {e}")
        st.stop()                # stops the rest of the app
```

- `function.clear()` wipes the cache **of that function only** (granular).
- `st.cache_data.clear()` wipes **all** data caches (more aggressive).

Docs: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data>

### Tip 10 — `st.stop()` to abort rendering

When data fails, drawing empty charts makes no sense. `st.stop()` halts the
script at that point without raising an exception.

Docs: <https://docs.streamlit.io/develop/api-reference/control-flow/st.stop>

---

## 4. Metrics and KPIs

### Tip 11 — `st.metric` with delta

Show relative change with an automatic colored arrow (green/red):

```python
st.metric(label="Winners", value="12", delta="+3 vs yesterday")
st.metric(label="Losses", value="8", delta="-2", delta_color="inverse")
```

- `delta_color="inverse"` flips the colors (useful when "up is bad").
- `border=True` adds the card style directly on the metric.

Docs: <https://docs.streamlit.io/develop/api-reference/data/st.metric>

---

## 5. Filters: multiselect and pills

### Tip 12 — `st.multiselect` with free text

Let the user **type new options** that were not in the original list:

```python
tickers = st.multiselect(
    "Tickers",
    options=["AAPL", "MSFT", "GOOG", "NVDA"],
    default=["AAPL", "MSFT"],
    accept_new_options=True,   # accepts text outside the options
    max_selections=10,         # good pair to limit growth
)
```

Docs: <https://docs.streamlit.io/develop/api-reference/widgets/st.multiselect>

### Tip 13 — `st.pills` with a label → value map

`st.pills` shows options as pill-shaped buttons. To display a nice label while
using a different internal value, keep a dict and use `format_func`:

```python
horizon_map = {"1D": "1d", "1W": "5d", "1M": "1mo", "1Y": "1y"}

choice = st.pills(
    "Horizon",
    options=list(horizon_map.keys()),  # shows "1D", "1W", ...
    default="1M",
    selection_mode="single",
)
period = horizon_map[choice]            # "1mo"
data = load_data(tickers, period=period)
```

Docs: <https://docs.streamlit.io/develop/api-reference/widgets/st.pills>

### Tip 14 — `st.info` for empty states

Instead of a blank chart, guide the user:

```python
if not tickers:
    st.info(":material/info: Select at least one ticker to start.")
    st.stop()
```

Docs: <https://docs.streamlit.io/develop/api-reference/status/st.info>

---

## 6. Data pipeline for charts

### Tip 15 — Normalize prices for fair comparison

Comparing a $100 stock with a $1,000 stock on the same axis distorts the
reading. Normalize everything to start at **1**:

```python
normalized = df.div(df.iloc[0])
```

### Tip 16 — Wide → long with `df.melt()` for Altair

Altair (and most grammar-of-graphics tools) prefers the **tidy / long** format.

```python
long = normalized.reset_index().melt(
    id_vars="Date",
    var_name="Ticker",
    value_name="Price",
)
```

### Tip 17 — Dynamic card grid with `enumerate`

To show one mini-chart per ticker in an N-column grid:

```python
cols = st.columns(4)
for i, ticker in enumerate(tickers):
    with cols[i % 4].container(border=True):
        st.altair_chart(make_chart(long, ticker), use_container_width=True)
```

---

## 7. Chart styling (Altair)

### Tip 18 — Fixed categorical color scale

Instead of random colors, define them explicitly:

```python
import altair as alt

color = alt.Color(
    "Ticker:N",
    scale=alt.Scale(range=["#E0413E", "#9AA0A6"]),  # red + gray
)
```

### Tip 19 — Interactive tooltips

Enable exploration on hover:

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

### Tip 20 — Legend at the bottom for small cards

In mini-charts, a side legend eats too much space. Move it down:

```python
color = alt.Color(
    "Ticker:N",
    legend=alt.Legend(orient="bottom"),
)
```

Altair docs (officially integrated with Streamlit):
<https://docs.streamlit.io/develop/api-reference/charts/st.altair_chart>

---

## 8. Professional custom theme

### Tip 21 — Create a `.streamlit/config.toml` with a custom dark theme

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

Main keys:

- `base` → `"light"` or `"dark"` (starting point).
- `primaryColor` → accent color (buttons, focus, selection).
- `backgroundColor` / `secondaryBackgroundColor` → app and widget backgrounds.
- `borderColor` → widget and container borders.
- `dataframeHeaderBackgroundColor` → `st.dataframe` header.

Docs: <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>

### Tip 22 — Custom Google Fonts font (e.g. Space Grotesk)

```toml
[theme]
font = "Space Grotesk"
headingFont = "Space Grotesk"
baseFontSize = 16
baseFontWeight = 400

# Sizes per heading level (h1..h6)
headingFontSizes = ["2.25rem", "1.75rem", "1.5rem", "1.25rem", "1.125rem", "1rem"]
headingFontWeights = [700, 700, 600, 600, 500, 500]

[[theme.fontFaces]]
family = "Space Grotesk"
url = "https://fonts.gstatic.com/s/spacegrotesk/v15/V8mDoQDjQSkFtoMM3T6r8E7mF71Q-gOoraIAEj7aUUM.woff2"
weight = "300 700"
style = "normal"
```

To host local fonts with your app, enable `server.enableStaticServing = true`.

Docs:

- Theme (colors and borders): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>
- Theme (fonts): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts>
- `[[theme.fontFaces]]`: <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts>

> ℹ️ **Important:** the theme does **not** apply automatically to
> Altair/Plotly charts. Define chart colors explicitly in the encoding (see Tip 18).

---

## 9. Sharing state via URL

### Tip 23 — Initialize `session_state` from the URL

Let users share a link with filters already applied.

```python
if "tickers" not in st.session_state:
    qp = st.query_params.get_all("stocks")  # list of strings
    st.session_state.tickers = qp or ["AAPL", "MSFT"]
```

Docs: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params>

### Tip 24 — Use `session_state` as the widget `default`

```python
selected = st.multiselect(
    "Tickers",
    options=ALL_TICKERS,
    default=[t for t in st.session_state.tickers if t in ALL_TICKERS],
    accept_new_options=True,
    key="tickers",
)
```

### Tip 25 — Sync the URL when the selection changes

After the user interacts, mirror the state back to the query string:

```python
st.query_params["stocks"] = selected   # accepts a list to repeat the key
# Resulting URL: ...?stocks=AAPL&stocks=MSFT
```

> 💡 **Modern shortcut:** widgets like `st.multiselect` and `st.pills` accept
> `bind="query-params"` to sync with the URL automatically, without the manual
> read/write steps. Check your Streamlit version (recent feature).

Docs: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params>

---

## 10. Final "professional look" checklist

Before publishing, make sure your app has:

- [ ] `st.set_page_config(layout="wide", page_title=..., page_icon=...)`
- [ ] Cards with `st.container(border=True, height="stretch")`
- [ ] Metrics with `delta`
- [ ] Filters grouped in a single sidebar column or header
- [ ] `st.cache_data(ttl=..., show_spinner=False)` on every external call
- [ ] Error handling with `function.clear()` + `st.stop()`
- [ ] `.streamlit/config.toml` with a custom palette and font
- [ ] Chart colors defined explicitly (don't trust the theme)
- [ ] `st.info` for empty states instead of blank charts
- [ ] URL reflecting the filters (shareable)

---

## Official references

- API Reference: <https://docs.streamlit.io/develop/api-reference>
- Theme (colors/borders): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders>
- Theme (fonts): <https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts>
- Caching: <https://docs.streamlit.io/develop/concepts/architecture/caching>
- `st.query_params`: <https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params>
- Original video: <https://www.youtube.com/watch?v=pAPEP0j73QE>
