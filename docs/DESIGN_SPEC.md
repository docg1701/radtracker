# Design Spec — radtracker

**Version**: 1.0 — 2026-04-29
**Context**: Personal, local-only Streamlit dashboard for a Brazilian radiologist (Galvani) to track daily teleradiology production: RM (MRI), TC (CT), RX (X-ray).
**Design system reference**: Cal.com marketing surface — monochrome-first, confident-but-not-shouting, generous whitespace, hierarchical border radius.

---

## 1. Design Principles

| Principle | Manifestation |
|---|---|
| **Data-first, chrome-second** | Charts and KPIs dominate the viewport; UI chrome recedes. No decorative cards that don't carry data. |
| **Calm professionalism** | The dashboard should feel like a well-designed medical device — precise, clean, never flashy. |
| **One glance = one answer** | Every KPI card, every chart answers exactly one question. No multi-purpose visualizations. |
| **Color carries meaning** | Color is never decorative. Every hue maps to a semantic state (success/warning/danger) or a modality (RM/TC/RX). |
| **Galvani by name** | The LLM insights address him directly. The sidebar greets him. The tool feels personal, not generic SaaS. |
| **Progressive disclosure** | Today's data is one click away (default tab). Historical analysis is two clicks. Settings are out of sight until needed. |

---

## 2. Color Palette

### 2.1 Brand & Semantic Colors

| Token | Hex | Use |
|---|---|---|
| `--color-primary` | `#0D9488` | Primary CTAs, KPI accent lines, chart accent, progress bar fill, active tab underline. Teal-600 — modern, medical-adjacent, distinctive from hospital blue. |
| `--color-primary-active` | `#0F766E` | Button press state, darker hover. Teal-700. |
| `--color-primary-subtle` | `#CCFBF1` | Very light teal wash — selected row highlight, subtle chart area fill. Teal-100. |
| `--color-success` | `#16A34A` | "Meta batida" states: green KPI delta, success badges, goal-achieved progress segments. Green-600. |
| `--color-success-subtle` | `#DCFCE7` | Success card background, green-coded chart segments. Green-100. |
| `--color-warning` | `#CA8A04` | "Abaixo da meta" states: amber warning icons, below-goal progress segments. Yellow-600. |
| `--color-warning-subtle` | `#FEF9C3` | Warning card background. Yellow-100. |
| `--color-danger` | `#DC2626` | "Crítico" states: red KPI deltas (negative), danger badges, critically-low progress. Red-600. |
| `--color-danger-subtle` | `#FEE2E2` | Danger card background. Red-100. |
| `--color-info` | `#2563EB` | Informational badges, neutral chart annotations, LLM insight icon. Blue-600. |

### 2.2 Modality Colors (Colorblind-Safe)

Chosen for distinguishability under protanopia, deuteranopia, and tritanopia. The blue/orange/cyan triad is the most robust 3-color palette for categorical data visualization.

| Token | Hex | Modality | Rationale |
|---|---|---|---|
| `--color-modality-rm` | `#2563EB` | RM (Ressonância Magnética) | Blue-600 — strong blue, universally distinguishable. Most common colorblind types retain blue perception. |
| `--color-modality-tc` | `#D97706` | TC (Tomografia Computadorizada) | Amber-600 — warm orange, maximum contrast against blue for protanopia/deuteranopia. |
| `--color-modality-rx` | `#0891B2` | RX (Raio-X) | Cyan-600 — distinct from both blue and amber in hue and luminance. Readable for all CVD types. |

**Colorblind validation**: Simulated with Coblis (color-blindness simulator). All three remain distinguishable as distinct hues under protanopia, deuteranopia, and tritanopia. In grayscale, luminance ordering is TC (darkest) → RM (mid) → RX (lightest), providing a secondary encoding axis.

### 2.3 Surface & Background Hierarchy

Following Cal.com's surface rhythm: light canvas → light-gray cards → white product-mockup cards → dark footer. Adapted for a dashboard where the "product" IS the data.

| Token | Hex | Tailwind Equivalent | Use |
|---|---|---|---|
| `--color-canvas` | `#FFFFFF` | white | Main page background (light mode default). |
| `--color-surface-soft` | `#F8FAFC` | slate-50 | Section dividers, sidebar background. |
| `--color-surface-card` | `#F1F5F9` | slate-100 | KPI metric cards, insight cards, settings cards. |
| `--color-surface-strong` | `#E2E8F0` | slate-200 | Disabled inputs, progress bar track background, chart gridlines. |
| `--color-hairline` | `#CBD5E1` | slate-300 | Input borders, table dividers, card outlines. |
| `--color-hairline-soft` | `#E2E8F0` | slate-200 | Subtle dividers between same-surface sections. |
| `--color-surface-dark` | `#0F172A` | slate-900 | Dark mode canvas. |
| `--color-surface-dark-elevated` | `#1E293B` | slate-800 | Dark mode cards, sidebar. |

### 2.4 Text Colors

| Token | Hex | Use |
|---|---|---|
| `--color-ink` | `#0F172A` | All headlines, KPI numbers, primary text. Slate-900. |
| `--color-body` | `#334155` | Running paragraph text, chart axis labels, metric labels. Slate-700. |
| `--color-muted` | `#64748B` | Secondary information, chart annotations, sidebar hint text. Slate-500. |
| `--color-muted-soft` | `#94A3B8` | Captions, footnotes, placeholder text. Slate-400. |
| `--color-on-primary` | `#FFFFFF` | Text on primary-color buttons and badges. |
| `--color-on-dark` | `#F8FAFC` | Text on dark surfaces. |
| `--color-on-dark-soft` | `#94A3B8` | Muted text on dark surfaces. |

### 2.5 Quick Reference — All Colors

```
# Brand
Primary           #0D9488    Teal-600
Primary Active    #0F766E    Teal-700
Primary Subtle    #CCFBF1    Teal-100

# Semantic
Success           #16A34A    Green-600
Success Subtle    #DCFCE7    Green-100
Warning           #CA8A04    Yellow-600
Warning Subtle    #FEF9C3    Yellow-100
Danger            #DC2626    Red-600
Danger Subtle     #FEE2E2    Red-100
Info              #2563EB    Blue-600

# Modalities
RM                #2563EB    Blue-600
TC                #D97706    Amber-600
RX                #0891B2    Cyan-600

# Surfaces (Light)
Canvas            #FFFFFF
Surface Soft      #F8FAFC    Slate-50
Surface Card      #F1F5F9    Slate-100
Surface Strong    #E2E8F0    Slate-200
Hairline          #CBD5E1    Slate-300

# Surfaces (Dark)
Canvas Dark       #0F172A    Slate-900
Surface Dark      #1E293B    Slate-800

# Text
Ink               #0F172A    Slate-900
Body              #334155    Slate-700
Muted             #64748B    Slate-500
Muted Soft        #94A3B8    Slate-400
On Primary        #FFFFFF
On Dark           #F8FAFC
On Dark Soft      #94A3B8
```

---

## 3. Typography

### 3.1 Constraint

Streamlit does **not** support custom web fonts via `config.toml` alone. The `font` key accepts only `"sans serif"`, `"serif"`, or `"monospace"`. The actual rendered typeface depends on the user's operating system.

**System font stack** (what users actually see):
- **macOS**: San Francisco (SF Pro) — the OS default sans-serif
- **Windows**: Segoe UI — the OS default sans-serif
- **Linux**: system default (usually DejaVu Sans, Noto Sans, or similar)

This is acceptable for a personal tool — Galvani sees the same OS font he sees everywhere else. No custom font licensing, no `@import` hacks, no Google Fonts dependency.

### 3.2 Hierarchy via Streamlit Elements

Since we can't control exact font sizes with CSS-free Streamlit, we define the hierarchy through **which Streamlit element we use** plus approximate expected rendering.

| Role | Streamlit Element | Expected Size/Weight | Use |
|---|---|---|---|
| **App Title** | `st.title("📊 radtracker")` | ~2.25rem / 700 | Only once — top of sidebar or main area. Brand marker. |
| **Section Heading** | `st.header("Faturamento Hoje")` | ~1.75rem / 600 | Each major dashboard section. |
| **Subsection Heading** | `st.subheader("Por Modalidade")` | ~1.25rem / 600 | Chart titles, card group labels. |
| **KPI Value** | `st.metric(label="Faturamento", value="R$ 1.250")` | ~1.5rem / 600 (value), ~0.875rem / 400 (label) | The 3-4 big numbers at the top of each tab. |
| **KPI Delta** | `st.metric(delta="+12%")` | ~0.875rem / 400 | Below the KPI value. Green for positive, red for negative. |
| **Body Text** | `st.write()`, `st.markdown()` | ~1rem / 400 | Insight paragraphs, explanations, form labels. |
| **Caption / Fine Print** | `st.caption("Última atualização: 08:45")` | ~0.8rem / 400 | Timestamps, data source notes, footnote-level info. |
| **Button Label** | `st.button("💾 Salvar")` | ~0.9rem / 500 | Sidebar save button. |
| **Tab Label** | `st.tabs(["📊 Hoje", "📅 Mês", ...])` | ~0.9rem / 500 | Primary navigation. |
| **Code / Monospace** | `st.code()`, backtick markdown | ~0.85rem / 400 / monospace | File paths, SQL snippets, API response previews. |
| **Chart Title** | Plotly `title=dict(text="...", font=dict(size=16))` | 16px / 500 | Inside Plotly figures. |
| **Chart Axis Label** | Plotly `xaxis_title`, `yaxis_title` | 12px / 400 | Inside Plotly figures. |
| **Chart Annotation** | Plotly `add_annotation(font=dict(size=11))` | 11px / 400 | Callout lines, target markers. |

### 3.3 Typography Principles

1. **One headline per section.** Never stack `st.header()` + `st.subheader()` without body content between them.
2. **KPI numbers are sacred.** Never truncate, never abbreviate with "k"/"M" unless the number exceeds 6 digits. A radiologist thinks in exact reais and exact exam counts.
3. **Labels are sentence-case, not title-case.** "Faturamento hoje" not "Faturamento Hoje". Exception: proper names ("Galvani", "RM", "TC", "RX").
4. **Chart titles answer a question.** "Faturamento diário — Abril 2026" not just "Faturamento".
5. **No italic for emphasis.** Use `**bold**` sparingly for key numbers inline. Never italics — it reduces legibility at small sizes on screen.

---

## 4. Component Specifications

### 4.1 KPI Metric Card

The hero row of every tab: 4 cards in a horizontal `st.columns(4)` grid. Each card uses `st.metric()` styled with a `st.container(border=True)` wrapper for the card surface.

**Layout**:
```
┌──────────────────────────────────────────────────────┐
│  Faturamento Hoje       │  Exames Hoje          │
│  ┌──────────────────┐   │  ┌──────────────────┐ │
│  │ R$ 1.250,00      │   │  │ 24               │ │
│  │ +12% vs ontem    │   │  │ RM 8·TC 10·RX 6  │ │
│  └──────────────────┘   │  └──────────────────┘ │
│                         │                        │
│  Horas Estimadas        │  Meta Mensal           │
│  ┌──────────────────┐   │  ┌──────────────────┐ │
│  │ 5.2h              │   │  │ 41%              │ │
│  │ ~08:00–13:10      │   │  │ R$ 18.450/45.000 │ │
│  └──────────────────┘   │  └──────────────────┘ │
└──────────────────────────────────────────────────────┘
```

**Spec per card**:

| Card | `st.metric` label | `st.metric` value | `st.metric` delta | Color rule |
|---|---|---|---|---|
| **Faturamento Hoje** | `"💰 Faturamento hoje"` | `"R$ 1.250,00"` | `"+12% vs ontem"` or `"-8% vs ontem"` | Delta green if positive, red if negative. `delta_color="normal"`. |
| **Exames Hoje** | `"📋 Exames hoje"` | `"24"` | `"RM 8 · TC 10 · RX 6"` | Modality-colored pill indicators beside each count (see 4.1a). |
| **Horas Estimadas** | `"⏱️ Horas estimadas"` | `"5.2h"` | `"~08:00 – 13:10"` | No color — informational only. |
| **Meta Mensal** | `"🎯 Meta mensal"` | `"41%"` | `"R$ 18.450 / R$ 45.000"` | Progress color rule (see 4.2). |

**4.1a — Modality Pill Indicators** (inside Exames card):
```
RM ● 8   TC ● 10   RX ● 6
```
Each dot uses the modality color. Rendered as inline markdown with colored HTML spans:
```python
f'<span style="color:{modality_color}">●</span> {modality} {count}'
```

### 4.2 Monthly Progress Bar

Replaces `st.progress()` — Streamlit's native progress bar uses `primaryColor` only, which can't express the milestone gradient. Instead, render a **Plotly indicator gauge** or a custom horizontal stacked bar showing the 4 milestone segments.

**Milestone color map**:

| Progress Range | Color Token | Hex | Meaning |
|---|---|---|---|
| 0–25% | `--color-danger` | `#DC2626` | Crítico — far behind pace |
| 25–50% | `--color-warning` | `#CA8A04` | Abaixo — behind but recoverable |
| 50–75% | `--color-primary` | `#0D9488` | No ritmo — on pace |
| 75–100% | `--color-success` | `#16A34A` | Meta batida — ahead or achieved |

**Implementation**: Plotly horizontal bar (`go.Bar`) with 4 stacked traces, each colored by segment. The bar shows actual progress as filled width; the remaining space is rendered in `--color-surface-strong` (#E2E8F0).

```
├─ 0–25% ──┤├── 25–50% ──┤├────── 50–75% ──────┤├─ 75–100% ─┤
   RED         AMBER            TEAL                GREEN
[████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 41%
                                      ↑ current position
```

### 4.3 Insight Card

Displays LLM-generated (or rule-based fallback) analysis text. Rendered as `st.markdown()` inside a `st.container(border=True)` with a distinct background.

**Spec**:
- **Background**: `--color-surface-card` (#F1F5F9) — light gray card
- **Left border accent**: 4px solid `--color-primary` (#0D9488) on the card's left edge (achieved via `st.markdown` with inline CSS within a `st.container`)
- **Icon**: 💡 (lightbulb emoji) preceding the heading
- **Heading**: `st.subheader("💡 Insights")` or inline bold markdown
- **Body**: `st.markdown()` — paragraph text in `--color-body` (#334155)
- **Source indicator**: `st.caption("🤖 Gerado por DeepSeek V4 · 08:45")` — timestamp + model name in `--color-muted-soft`

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│ ┃  💡 Insights                                           │
│ ┃                                                        │
│ ┃  Galvani, seu ritmo está 12% acima da meta mensal.     │
│ ┃  O mix de exames mostra que RM está puxando o          │
│ ┃  faturamento — 58% da receita vs 35% no mês passado.  │
│ ┃                                                        │
│ ┃  📌 Sugestão: Se mantiver o ritmo atual, você baterá   │
│ ┃  a meta no dia 22. Isso te daria 4 dias de folga.      │
│ ┃                                                        │
│ ┃  🤖 Gerado por DeepSeek V4 · 29/04 08:45              │
└──────────────────────────────────────────────────────────┘
```

### 4.4 Sidebar Input Form

The primary data-entry surface. Lives in `st.sidebar`.

**Spec**:
- **Background**: Streamlit default sidebar background (inherits `secondaryBackgroundColor` from theme)
- **Header**: `st.sidebar.title("📊 radtracker")` — app name at top. Below it: `st.sidebar.markdown(f"Olá, **Galvani** 👋")` — personal greeting.
- **Date selector**: `st.sidebar.date_input("📅 Data", value="today")` — defaults to today. Brazilian date format (DD/MM/YYYY) via `format="DD/MM/YYYY"`.
- **Modality inputs**: Three `st.number_input()` fields in a compact layout:
  ```
  RM: [___]  TC: [___]  RX: [___]
  ```
  Each with `min_value=0`, `step=1`, no max. Labels use modality colors via emoji or colored markdown.
- **Save button**: `st.sidebar.button("💾 Salvar produção", type="primary", use_container_width=True)` — full-width, primary color fill.
- **Divider**: `st.sidebar.divider()` before secondary actions.
- **Secondary links**: `st.sidebar.page_link` or markdown links to tabs.
- **Version footer**: `st.sidebar.caption("radtracker v1.0 · local")` — subtle, bottom of sidebar.

**Button states**:
- **Default**: Teal background (#0D9488), white text, 8px border-radius (Streamlit default `type="primary"`).
- **Hover**: Darker teal (#0F766E) — handled by Streamlit automatically.
- **After click**: Brief success toast (see 7.4). Button returns to default state.

### 4.5 Charts (Plotly)

All charts use Plotly Express or Graph Objects, rendered with `st.plotly_chart(fig, use_container_width=True)`.

**Global chart style** (applied via a shared `layout` template or helper function):

| Property | Value |
|---|---|
| **Font family** | System sans-serif (inherit from Streamlit) |
| **Font color** | `--color-body` (#334155) |
| **Background** | Transparent (`paper_bgcolor='rgba(0,0,0,0)'`, `plot_bgcolor='rgba(0,0,0,0)'`) |
| **Gridlines** | `--color-surface-strong` (#E2E8F0), 1px, no vertical gridlines on bar/line charts |
| **Axis lines** | `--color-hairline` (#CBD5E1), 1px, only x-axis and y-axis zero-line |
| **Chart height** | 400px for detail charts, 250px for sparkline/mini charts |
| **Legend** | Top-right inside plot area, horizontal orientation when 3+ traces |
| **Hover tooltip** | Unified hover box (`hovermode='x unified'`), R$ formatted with 2 decimals |
| **Margin** | `dict(l=20, r=20, t=40, b=20)` — minimal padding since `use_container_width=True` handles width |

**Per-chart-type color assignments**:

| Chart Type | Color Source | Notes |
|---|---|---|
| **Daily earnings line** | `--color-primary` (#0D9488) for the line | Dashed horizontal line for daily target in `--color-muted` |
| **Modality stacked bar** | `--color-modality-rm`, `--color-modality-tc`, `--color-modality-rx` | In that order (RM bottom, TC middle, RX top) |
| **Modality pie/donut** | Same modality colors | `hole=0.4` for donut. Labels outside with leader lines. |
| **7d / 30d moving average** | `--color-primary` (7d, solid) + `--color-muted` (30d, dashed) | Fill to zero with 10% opacity for the 7d line |
| **Progress gauge** | Milestone colors (see 4.2) | Bullet-gauge or horizontal stacked bar |
| **Week-over-week comparison** | Current week in modality colors, previous week in muted grays | Side-by-side grouped bar |

### 4.6 Empty State

What Galvani sees on first use — no data in the database yet.

**Design**:
- **Center of tab area** (not sidebar): A large, friendly empty-state card.
- **Background**: `--color-surface-card` (#F1F5F9), full-width container with generous padding (48px).
- **Icon**: 📋 (clipboard) or 🏥 (hospital) — large emoji, centered, ~64px effective size.
- **Heading**: `st.subheader("Nenhum registro ainda")`
- **Body**: `st.markdown("Comece registrando sua produção de hoje na barra lateral →")`
- **Visual cue**: A subtle arrow or pointer toward the sidebar (rendered as `→` emoji or Unicode arrow).
- **Secondary CTA**: `st.button("📅 Registrar primeiro dia", type="primary")` — jumps focus to the sidebar date input (via `st.session_state` flag).

**No empty-state clutter**: No sample data, no "take a tour", no onboarding wizard. This is a personal tool — Galvani knows what it does.

### 4.7 Settings Panel

Minimal settings in the "⚙️ Config" tab.

**Layout**:
- **Preços dos exames**: Three `st.number_input()` fields for RM/TC/RX unit prices, with R$ prefix and 2 decimal places. Current values shown as labels.
- **Meta mensal**: One `st.number_input()` for monthly revenue goal in R$.
- **Save button**: `st.button("💾 Salvar configurações", type="primary")`
- **Danger zone** (at bottom, separated by divider): `st.button("🗑️ Limpar todos os dados", type="secondary")` — requires confirmation via `st.warning` + second click.

---

## 5. Spacing & Layout

### 5.1 Tab Structure

Four tabs, rendered with `st.tabs()`:

```
[ 📊 Hoje ] [ 📅 Mês Atual ] [ 📈 Análise ] [ ⚙️ Config ]
```

| Tab | Content | Default on load |
|---|---|---|
| **📊 Hoje** | Today's KPI row → today's modality breakdown chart → today's LLM insight card | ✅ Active |
| **📅 Mês Atual** | Month-to-date KPI row → monthly progress gauge → daily earnings trend line → modality distribution donut | — |
| **📈 Análise** | Full LLM analysis card → historical trend with moving averages → week-over-week comparison → modality mix evolution | — |
| **⚙️ Config** | Price settings → monthly goal → data management | — |

### 5.2 Column Grids

| Use | Columns | Width distribution |
|---|---|---|
| **KPI cards** | `st.columns(4)` | Equal width (4 × 25%). On narrow screens, Streamlit auto-wraps to 2×2 then 1×1. |
| **Chart row (side-by-side)** | `st.columns(2)` | Equal width (2 × 50%). Used for: modality donut + earnings trend on Mês tab. |
| **Settings form** | `st.columns([2, 1])` | 66% form inputs, 33% help text / current values display. |
| **Modality inputs in sidebar** | `st.columns(3)` | Equal width (3 × 33%). Compact number inputs for RM/TC/RX. |

### 5.3 Vertical Rhythm

Loosely following Cal.com's 4px base-unit system:

| Token | Value | Use |
|---|---|---|
| `spacing-sm` | 8px | Between label and input inside sidebar form. |
| `spacing-md` | 16px | Between KPI cards and chart section. Between sidebar input groups. |
| `spacing-lg` | 24px | Between major sections (KPI row → progress bar → chart grid → insight card). |
| `spacing-xl` | 32px | Internal padding of insight cards and empty state cards. |
| `spacing-section` | 48px | Top padding of each tab's content area. |

### 5.4 Responsive Behavior

Streamlit handles most responsiveness automatically. Additional notes:

- **KPI row**: 4 columns at desktop (>992px), 2 columns at tablet, 1 column at mobile. `st.metric` cards stack cleanly.
- **Chart rows**: 2 columns at desktop, 1 column at tablet/mobile.
- **Sidebar**: Streamlit collapses to hamburger at <576px. On a personal desktop tool this is unlikely but handled gracefully.
- **Plotly charts**: `use_container_width=True` ensures charts resize with the viewport.

---

## 6. Tone of Voice

### 6.1 Principles

- **Direct address**: Always "Galvani" or "você", never "o usuário" or "o médico".
- **Friendly but clinical**: Warm tone, but no jokes, no emoji overload. The dashboard is a professional tool.
- **Actionable, not diagnostic**: Every insight ends with a concrete suggestion. "Faça X para Y" not "Observa-se que X".
- **Present tense, active voice**: "Você está 12% acima da meta" not "A meta foi excedida em 12%".
- **Specific, never vague**: "Faltam R$ 3.200 para a meta — isso significa R$ 400/dia nos próximos 8 dias" not "Você precisa aumentar a produção".

### 6.2 Example Insights (Portuguese)

**Success — meta batida ("Você está acima do ritmo"):**
> Galvani, você está com **R$ 18.450 acumulados** — **12% acima** do ritmo necessário para bater a meta de R$ 45.000. Se mantiver a média atual de R$ 1.250/dia, você fecha o mês com **R$ 48.750** e ainda ganha 3 dias de folga. O destaque é a **RM**, que está representando 58% do faturamento (era 42% no mês passado).

**Warning — abaixo da meta ("Atenção ao ritmo"):**
> Galvani, você está **8% abaixo** do ritmo para a meta de R$ 45.000. Faltam R$ 26.550 em 12 dias úteis — você precisa de **R$ 2.212/dia** daqui pra frente. Sua média atual está em R$ 1.150/dia. Uma sugestão: os exames de **TC** estão com volume abaixo do seu padrão (15 exames/semana vs sua média de 22). Vale checar se houve mudança na distribuição dos laudos.

**Danger — crítico ("Alerta — ritmo muito abaixo"):**
> Galvani, você está **22% abaixo** do necessário. Com 8 dias restantes e R$ 28.000 faltando, a meta de R$ 45.000 exige **R$ 3.500/dia** — quase o triplo da sua média atual de R$ 1.200. Isso não é viável sem uma mudança significativa no volume. Recomendo revisar a meta para este mês nas ⚙️ Configurações e focar em consistência para o próximo ciclo.

**Trend — melhora recente ("Tendência positiva"):**
> Boa notícia: sua média móvel de 7 dias subiu para **R$ 1.380/dia**, um aumento de **18%** em relação à semana anterior. Se essa aceleração continuar, você alcança a meta no dia 26. O crescimento veio principalmente dos exames de RX — você fez 45% mais RX esta semana. Continua assim.

**Suggestion — mix de exames ("Otimize o mix"):**
> Galvani, seu mix atual está **RM 58% · TC 22% · RX 20%**. Comparando com sua média de 6 meses (RM 45% · TC 30% · RX 25%), a RM está com peso maior. Isso é positivo para o faturamento (RM paga mais), mas fique atento: se o volume de RM cair, o impacto será maior do que antes. Uma distribuição mais equilibrada protege contra variações de demanda.

### 6.3 Rule-Based Fallback Tone

When the LLM is unavailable, rule-based insights are shorter and more mechanical but follow the same principles:

> 📊 **Resumo automático**  
> Faturamento acumulado: R$ 18.450 (41% da meta de R$ 45.000).  
> Dias trabalhados: 12 de 22. Dias restantes: 10.  
> Média diária: R$ 1.537. Necessário: R$ 2.655/dia.  
> Ritmo: ⚠️ abaixo da meta.

No narrative flourish, but still uses Galvani's name and provides specific numbers.

---

## 7. Streamlit Theme Configuration

Two complete `config.toml` themes: light (default) and dark. Galvani chooses via Streamlit's built-in theme switcher in Settings (☰ → Settings → Theme).

### 7.1 Light Theme (Default)

```toml
# .streamlit/config.toml
[theme]
base = "light"
primaryColor = "#0D9488"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F1F5F9"
textColor = "#0F172A"
font = "sans serif"

[browser]
gatherUsageStats = false

[server]
headless = true
```

**Token mapping**:

| config.toml Key | Design Token | Hex | Notes |
|---|---|---|---|
| `primaryColor` | `--color-primary` | `#0D9488` | Buttons, links, progress bar, date picker accent, slider fill |
| `backgroundColor` | `--color-canvas` | `#FFFFFF` | Main page background |
| `secondaryBackgroundColor` | `--color-surface-card` | `#F1F5F9` | Sidebar background, `st.container(border=True)` backgrounds, dataframe headers |
| `textColor` | `--color-ink` | `#0F172A` | All body text, input text, metric values |

### 7.2 Dark Theme

```toml
# .streamlit/config.toml — add this block below [theme]
[theme.dark]
base = "dark"
primaryColor = "#2DD4BF"
backgroundColor = "#0F172A"
secondaryBackgroundColor = "#1E293B"
textColor = "#F1F5F9"
font = "sans serif"
```

**Token mapping (dark)**:

| config.toml Key | Design Token | Hex | Notes |
|---|---|---|---|
| `primaryColor` | Teal-400 | `#2DD4BF` | Lighter teal for adequate contrast on dark backgrounds |
| `backgroundColor` | `--color-surface-dark` | `#0F172A` | Dark canvas |
| `secondaryBackgroundColor` | `--color-surface-dark-elevated` | `#1E293B` | Dark cards, sidebar |
| `textColor` | `--color-on-dark` | `#F1F5F9` | Light text on dark |

**Why a lighter primary in dark mode?** `#0D9488` on `#0F172A` has poor contrast (~3.2:1). `#2DD4BF` (Teal-400) achieves ~5.5:1 — sufficient for UI elements. The primary color in dark mode should feel like the "light" version of the same hue.

### 7.3 Full config.toml (Combined)

```toml
# .streamlit/config.toml — radtracker theme configuration
# Light theme is the default. Dark theme activates via Streamlit Settings menu.

[theme]
base = "light"
primaryColor = "#0D9488"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F1F5F9"
textColor = "#0F172A"
font = "sans serif"

[theme.dark]
base = "dark"
primaryColor = "#2DD4BF"
backgroundColor = "#0F172A"
secondaryBackgroundColor = "#1E293B"
textColor = "#F1F5F9"
font = "sans serif"

[browser]
gatherUsageStats = false

[server]
headless = true
```

### 7.4 Theme Limitations (What config.toml Can't Do)

| Limitation | Workaround |
|---|---|
| `st.progress()` uses `primaryColor` only — no multi-color segments | Use Plotly gauge/stacked bar for progress (see 4.2) |
| No custom font loading | Accept system font stack. It's a personal tool — consistent within Galvani's OS. |
| No per-component color overrides (e.g., sidebar vs main area different card colors) | Accept the `secondaryBackgroundColor` for both. The design uses whitespace and typography hierarchy instead of color to differentiate surfaces. |
| `st.metric` delta color is binary (green/red) — no amber "warning" delta | Use `delta_color="off"` and render the delta as custom markdown with manual color control when amber is needed. |
| Chart colors inside Plotly are not themed by config.toml | Manually pass color values from the design palette into every Plotly `color_discrete_sequence` or `marker_color`. Use a shared `CHART_COLORS` dict imported across modules. |

---

## 8. State Handling

### 8.1 Empty State

**Trigger**: Database has zero rows (`SELECT COUNT(*) FROM daily_production = 0`).

**Visual**: See 4.6 — centered empty-state card with clipboard icon, heading, body, and CTA.

**Logic**:
```python
if df.empty:
    show_empty_state()
else:
    show_kpi_row()
    show_charts()
```

### 8.2 Loading State

**Trigger**: LLM API call in progress (`generate_insights()`). Chart computation is near-instant with local SQLite — no spinner needed for data queries.

**Visual**: Streamlit's `st.spinner("Analisando seus dados...")` wrapping the LLM call. The spinner shows a teal spinning animation with the message.

```python
with st.spinner("🧠 Gerando insights com DeepSeek V4..."):
    insights = generate_insights(stats)
st.markdown(insights)
```

**Timeout**: 15-second timeout on the Ollama API call. If exceeded → fallback to rule-based insights (see 8.3).

### 8.3 Error State — LLM Unavailable

**Triggers**:
- `OLLAMA_API_KEY` not set or invalid
- Ollama Cloud API returns 4xx/5xx
- Network timeout (>15s)
- Rate limit exceeded (Ollama Free plan cap)

**Visual**:
- Info banner: `st.info("🤖 Insight automático (LLM indisponível)")` — blue info box, not red error. The LLM is a "plus", not a critical dependency.
- Below it: rule-based insight text (see 6.3) — same insight card styling without the "Gerado por DeepSeek" caption.

**No retry button**: Don't prompt the user to retry. The fallback is good enough. If they want LLM insights, they'll naturally revisit the tab later (which triggers a fresh attempt).

### 8.4 Error State — Database Issue

**Triggers**:
- SQLite file corrupted or locked
- Schema mismatch (missing column after update)
- Disk full

**Visual**:
- `st.error("⚠️ Erro ao acessar o banco de dados. Verifique se o arquivo data/telerrad.db está acessível.")`
- Red error box with specific, non-technical message.
- Below: technical details in `st.code()` block (collapsed behind `st.expander("Detalhes técnicos")`).

### 8.5 Success Feedback

**Trigger**: User clicks "💾 Salvar produção" in sidebar.

**Visual**: `st.toast("✅ Produção de 29/04 salva!", icon="✅")` — brief toast notification that auto-dismisses after 4 seconds.

**Additional feedback**:
- The KPI row refreshes to show updated numbers.
- The save button briefly shows a checkmark (achieved by toggling `st.session_state.saved = True` and re-rendering the button label as "✅ Salvo!" for one cycle).
- If the user enters data for an already-saved date, the toast says "📝 Produção de 29/04 atualizada!" to distinguish insert vs update.

### 8.6 State Transition Diagram

```
┌──────────┐   first run    ┌──────────────┐   save data    ┌──────────────┐
│  EMPTY   │ ─────────────→ │  WITH DATA   │ ─────────────→ │   SUCCESS    │
│ (no rows)│                │  (dashboard) │                │ (toast + UI  │
│          │ ←───────────── │              │                │   refresh)   │
└──────────┘   delete all   └──────────────┘                └──────────────┘
                                  │
                                  │ LLM call
                                  ▼
                           ┌──────────────┐
                           │   LOADING    │
                           │  (spinner)   │
                           └──────────────┘
                              │         │
                        success│         │failure/timeout
                              ▼         ▼
                      ┌──────────┐  ┌──────────────┐
                      │ LLM      │  │ RULE-BASED   │
                      │ INSIGHT  │  │ FALLBACK     │
                      └──────────┘  └──────────────┘
```

---

## 9. Charts Color Reference (for Plotly Code)

A shared constant to import across all chart modules — ensures every chart uses the same palette without inline hex values:

```python
# src/chart_colors.py
CHART_COLORS = {
    # Modality colors — used in bar, pie, stacked charts
    "rm": "#2563EB",      # Blue-600
    "tc": "#D97706",      # Amber-600
    "rx": "#0891B2",      # Cyan-600

    # Semantic — used in progress gauge, delta indicators
    "success": "#16A34A",  # Green-600
    "warning": "#CA8A04",  # Yellow-600
    "danger": "#DC2626",   # Red-600

    # Chart accent
    "primary": "#0D9488",  # Teal-600 — main line/bar color
    "muted": "#94A3B8",    # Slate-400 — secondary lines, grid
    "neutral": "#64748B",  # Slate-500 — annotations

    # Progress milestone segments
    "progress_danger": "#DC2626",   # 0-25%
    "progress_warning": "#CA8A04",  # 25-50%
    "progress_on_track": "#0D9488", # 50-75%
    "progress_achieved": "#16A34A", # 75-100%
}
```

---

## 10. Summary Checklist

- [x] 10+ color palette with brand, semantic, modality, surface, and text tokens
- [x] Typography hierarchy mapped to Streamlit elements (no custom fonts)
- [x] 4 KPI metric cards with per-card spec
- [x] Monthly progress bar with 4 milestone colors
- [x] LLM insight card with layout, icon, typography
- [x] Sidebar input form with button states
- [x] Plotly chart global style and per-chart color assignments
- [x] Empty state design for first use
- [x] Settings panel layout
- [x] Tab structure (4 tabs) with content description
- [x] Column grids and spacing tokens
- [x] 5 example insights in Portuguese (success, warning, danger, trend, suggestion)
- [x] Rule-based fallback tone
- [x] Light theme config.toml with token mapping
- [x] Dark theme config.toml with adapted primary color
- [x] Loading, error, success, and empty state handling
- [x] State transition diagram
- [x] Shared Plotly color constant (`chart_colors.py`)

---

## Sources

- Cal.com design system — extracted via dembrandt from cal.com marketing surface [DESIGN.md](./DESIGN.md)
- Streamlit theming documentation — [docs.streamlit.io/develop/concepts/configuration/theming](https://docs.streamlit.io/develop/concepts/configuration/theming)
- Streamlit config.toml reference — [docs.streamlit.io/develop/api-reference/configuration/config.toml](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
- Plotly Python documentation — [plotly.com/python](https://plotly.com/python/)
- Colorblind-safe palettes — [plotset.com/blog/designing-blind-friendly-colors-in-data-visualization](https://plotset.com/blog/designing-blind-friendly-colors-in-data-visualization-a-guide-to-inclusion) · [colorblind.io/guides/data-visualization](https://colorblind.io/guides/data-visualization)
- Coblis color blindness simulator — used for modality color validation
