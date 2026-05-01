# Implementation Plan — radtracker Visual & UX Overhaul

## Goal
Transform radtracker from a functional Streamlit app into a **professional, polished SaaS dashboard** — following Cal.com's monochrome, clean design principles, implementing official Streamlit skill recommendations, and avoiding deprecated streamlit-extras.

---

## Phase Tracking

| Phase | Descrição | Tarefas | Status | Worker | Reviewer |
|-------|-----------|---------|--------|--------|----------|
| **0** | Foundation fixes | 0.1–0.4 (4) | ✅ Done | worker | reviewer (4×) |
| **1** | Theme & typography | 1.1–1.4 (4) | ✅ Done | worker | reviewer (2×) |
| **2** | Layout & responsiveness | 2.1–2.6 (6) | ✅ Done | worker | reviewer (2×) |
| **3** | Visual polish & configurability | 3.1–3.11 (11) | ✅ Done | worker | reviewer (3×) |
| **4** | Chart & data refinements | 4.1–4.7 (7) | ✅ Done | worker | reviewer (3×) |
| **5** | UX enhancements | 5.1–5.5 (3) | ⬜ Pending | — | — |

**Workflow por phase:** `worker (1×) → reviewer (1+×) → ✅ Done`

---

## Dependencies

```
Phase 0 (independently executable tasks)
    ↓
Phase 1 (theme config — needed before visual polish)
    ↓
Phase 2 (layout changes — depend on theme for color consistency)
    ↓
Phase 3 (visual polish — depends on layout structure from Phase 2)
    ↓
Phase 4 (chart refinements — depends on theme colors from Phase 1)
    ↓
Phase 5 (UX enhancements — can be done anytime after Phase 1)
```

## Risks

1. **Cal Sans substitute fidelity** — Manrope at 600 weight is the best free geometric display font, but it doesn't perfectly match Cal Sans's condensed, precise character. Risk: Medium. Mitigation: Accept Manrope; it's close enough for a non-Cal.com product.

2. **Dark mode chart legibility** — Plotly charts with `rgba(0,0,0,0)` backgrounds inherit the page background but text annotations may need explicit color adjustment. Risk: Medium. Mitigation: Use `st.context.theme.base` to branch chart styling, and replace hardcoded annotation colors (e.g., `#0F172A` in `build_progress_gauge`) with theme-aware values.

3. **st.form migration in sidebar — BLOCKER** — Wrapping the sidebar in `st.form` breaks date-dependent pre-fill because widgets inside a form do not trigger reruns on value changes. If the user picks a new date, the modality inputs (`rm`, `tc`, `rx`) below it will retain stale defaults until submit, causing data to be saved to the wrong date. Risk: High. Mitigation: Do **not** wrap the date picker + modality inputs in a form. Keep the current imperative save button and use `st.spinner()` for loading feedback.

4. **streamlit-extras not in dependencies** — Tasks 3.4, 5.1–5.5 all import `streamlit-extras`, but `requirements.txt` does not list it. Risk: Medium. Mitigation: Add `streamlit-extras>=1.5.0` to `requirements.txt` before implementing Phase 3/5.

5. **streamlit-extras volatility** — As noted in the guide, extras can be deprecated when core absorbs features. Risk: Low (for polish extras). Mitigation: Only adopt extras from Group B ("gain from core") or Group C ("polish"): `skeleton`, `let_it_rain`, `star_rating`, `stoggle`. Avoid Group A (deprecated).

6. **Deploy button on Streamlit Cloud** — If the user deploys to Streamlit Cloud, the Deploy button is a platform feature and cannot be hidden. Risk: Low. Mitigation: Document this as expected; it's only an issue on local runs. The current config already has the relevant flags.

7. **Config.toml font loading delay** — Google Fonts load via CDN; first cold load may show fallback fonts briefly. Risk: Low. Mitigation: The fallback stack (`Inter` → sans-serif) is acceptable for the split second before fonts load.

8. **Missing source document for verification** — `analise-visual.md` is cited as a source in 10+ tasks but is not present in the repo. Risk: Low (only affects review confidence). Mitigation: Regenerate or locate the file before implementation if exact section references matter.

9. **Test regressions from chart color changes** — Task 4.1 preserves existing key names (`progress_danger`, `progress_warning`, etc.) and only changes hex values. The existing test in `tests/test_chart_colors.py` only asserts key existence and that values start with `#` — it will not break. Risk: None after verification.

10. **DB migration for user_settings** — Adding a new table uses `CREATE TABLE IF NOT EXISTS` in `init_db()`, which is non-breaking and idempotent — the existing code already follows this pattern. Risk: Low.

## Priority Summary

| Priority | Count | Tasks |
|----------|-------|-------|
| P0 (critical) | 4 | 0.1–0.4: Bug fixes and localization |
| P1 (high) | 13 | 1.1–1.4, 2.1–2.6, 3.1–3.3: Theme, layout, icons |
| P2 (medium) | 15 | 3.4–3.11, 4.1–4.7: Polish, configurability, charts, docs, dead-code |
| P3 (nice-to-have) | 3 | 5.1–5.5: Extras, celebrations |

## Quick Reference: What NOT to Do

Per official Streamlit skills:
- ❌ No custom CSS (`st.markdown(unsafe_allow_html=True)`, `st.html()` style blocks) for theming — use config.toml
- ❌ No deprecated streamlit-extras: `add_vertical_space`, `app_logo`, `colored_header`, `row`, `stylable_container`, `tags`
- ❌ No `st.cache_resource` for data (use `st.cache_data`)
- ❌ No more than 4 columns in a single row
- ❌ No `st.divider()` — remove all occurrences (use natural spacing or `st.space()`)
- ❌ No emojis as functional icons (use Material icons); emojis only for celebrations
- ❌ No Title Case labels (use sentence casing)
- ❌ No `st.info()` for simple metadata (use `st.caption()`)

---

## Phase 0: Foundation Fixes (Quick Wins)

*Priority: P0 — critical. These fix bugs and localization issues with minimal risk. Each is independent.*

### Task 0.1 — Translate date picker label
- **File:** `src/ui/sidebar.py` (line ~37)
- **Change:** The current label is `"📅 Data"`. Since `st.date_input` has no native `placeholder` parameter (only `label`), rename to `"Data"` (the Portuguese word itself is sufficient — the user sees a calendar widget on click, so no extra instruction is needed). The emoji and any English `"Select a date."` tooltip go away.
- **Acceptance:** Date picker shows `"Data"` as label; no English text visible.
- **Note:** Merged with Task 2.1 — implement only once.
- **Ref:** analise-visual.md §2.4 (placeholder em inglês)

### Task 0.2 — Fix RX spinbutton step in Config tab
- **File:** `src/ui/settings.py` (line ~66, inside `_render_settings_form`)
- **Change:** The current `st.number_input` for RX uses `step=0.01`, which makes the `+`/`-` buttons change by R$0.01 — too fine for a monetary value. Change to `step=0.50` so increments are meaningful (R$0.50 at a time).
- **Acceptance:** RX +/- buttons change by R$0.50 increments.
- **Ref:** analise-visual.md §2.5

### Task 0.3 — Hide Deploy button and Streamlit Cloud branding
- **File:** `.streamlit/config.toml` (verification only)
- **Status:** Already complete. The current `config.toml` already contains `[browser] gatherUsageStats = false` and `[server] headless = true`. No additional changes can hide the Deploy button on Streamlit Cloud (it is a platform feature).
- **Acceptance:** Verify existing config is in place; accept Deploy button on Cloud as expected.
- **Ref:** analise-visual.md §2.2

### Task 0.4 — Remove all st.divider() calls
- **Files:** `src/ui/sidebar.py` (line ~58), `src/ui/settings.py` (line ~43)
- **Change:** Remove both `st.divider()` calls. The sidebar's divider separates the save button from the version caption — default spacing is enough. The settings divider separates the form from the danger zone — the section headers already provide enough visual separation.
- **Acceptance:** No heavy divider lines anywhere in the app.
- **Ref:** improving-streamlit-design skill ("Dividers look heavy")

---

## Phase 1: Theme & Typography

*Priority: P1 — high. Professional theming is the foundation for all visual improvements. Use config.toml only (no CSS).*

### Task 1.1 — Implement Cal.com-inspired monochrome theme
- **File:** `.streamlit/config.toml`
- **Change:** Replace current `[theme]` with a Cal.com-inspired light theme:
  ```toml
  [theme]
  base = "light"
  primaryColor = "#111111"          # near-black CTA (Cal.com signature)
  backgroundColor = "#FFFFFF"       # white canvas
  secondaryBackgroundColor = "#F8F9FA"  # surface-soft
  textColor = "#0F172A"             # ink color
  linkColor = "#3B82F6"             # brand accent (sparing use)
  borderColor = "#E5E7EB"           # hairline
  showWidgetBorder = true
  showSidebarBorder = true
  baseRadius = "8px"                # buttons, inputs (rounded.md)
  buttonRadius = "8px"
  ```
- **Rationale:** Monochrome at the action layer (Cal.com never uses blue CTAs), white canvas, light-gray secondary backgrounds.
- **Acceptance:** Buttons are near-black (#111111), white canvas, subtle borders.
- **Ref:** DESIGN.md colors section; creating-streamlit-themes skill

### Task 1.2 — Configure Google Fonts (Inter + Manrope)
- **File:** `.streamlit/config.toml`
- **Change:** Add to `[theme]`:
  ```toml
  # Body: Inter (matches Cal.com's body type)
  font = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
  # Headings: Manrope (geometric, close to Cal Sans substitute)
  headingFont = "Manrope:https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap"
  baseFontSize = 14
  baseFontWeight = 400
  headingFontSizes = ["28px", "22px", "18px", "16px", "14px", "12px"]
  headingFontWeights = [600, 600, 600, 500, 500, 500]
  linkUnderline = false
  ```
- **Rationale:** DESIGN.md recommends Cal Sans (display) + Inter (body). Cal Sans is proprietary; Manrope at weight 600 is the closest geometric substitute. Inter at 400 for body.
- **Acceptance:** Headings render in Manrope (geometric, slightly condensed feel), body in Inter.
- **Ref:** DESIGN.md typography section, streamlit_pro_tips.md Dica 22, creating-streamlit-themes font section

### Task 1.3 — Define semantic colors and chart palette
- **File:** `.streamlit/config.toml`
- **Change:** Add to `[theme]`:
  ```toml
  # Semantic colors
  redColor = "#EF4444"
  greenColor = "#10B981"
  blueColor = "#3B82F6"
  orangeColor = "#F59E0B"
  violetColor = "#8B5CF6"
  grayColor = "#6B7280"

  # Chart categorical colors (modality colors)
  chartCategoricalColors = ["#2563EB", "#D97706", "#0891B2", "#0D9488", "#111111", "#6B7280", "#94A3B8"]

  # Dataframe styling
  dataframeBorderColor = "#E5E7EB"
  dataframeHeaderBackgroundColor = "#F8F9FA"
  ```
- **Acceptance:** Status badges, chart traces use defined palette. Semantic colors consistent with DESIGN.md.
- **Ref:** creating-streamlit-themes colors section

### Task 1.4 — Add light + dark mode support
- **File:** `.streamlit/config.toml`
- **Change:** After `[theme]` block, add:
  ```toml
  [theme.dark]
  primaryColor = "#F8F9FA"
  backgroundColor = "#101010"
  secondaryBackgroundColor = "#1A1A1A"
  textColor = "#E5E7EB"
  borderColor = "#2A2A2A"
  linkColor = "#60A5FA"
  baseRadius = "8px"
  buttonRadius = "8px"

  chartCategoricalColors = ["#60A5FA", "#F59E0B", "#22D3EE", "#2DD4BF", "#F8F9FA", "#9CA3AF", "#6B7280"]
  ```
  Users can now toggle via ☰ → Settings → Theme → Dark.
- **Acceptance:** Toggle works; dark theme uses dark surface (#101010).
- **Ref:** creating-streamlit-themes section on light/dark modes

---

## Phase 2: Layout & Responsiveness

*Priority: P1 — high. Structural improvements that make the dashboard feel like a dashboard.*

### Task 2.1 — Restructure sidebar (cleaner, professional)
- **File:** `src/ui/sidebar.py`
- **Change:**
  1. Replace `st.title("📊 radtracker")` with a clean `st.markdown("**radtracker**")` (no logo asset exists in the repo, so `st.logo()` is not applicable without creating one first).
  2. Replace `st.markdown("Olá, **Galvani** 👋")` with `st.caption("Olá, Galvani")` — cleaner, less shouty.
  3. Rename `st.date_input("📅 Data", ...)` → `st.date_input("Data", ...)` — the label itself is the Portuguese instruction. Date input doesn't support a native `icon` parameter.
  4. Replace `st.button("💾 Salvar produção", ...)` → `st.button("Salvar produção", icon=":material/save:", ...)` using native `icon` param.
  5. Add a loading spinner on save (see Task 3.3 for full implementation).
- **Note:** The emoji removals in this task overlap with the global Phase 3 Task 3.1. This task handles the sidebar specifically; Task 3.1 will sweep the remaining files.
- **Acceptance:** Sidebar is minimal, professional, no emojis, all Material icons.
- **Ref:** improving-streamlit-design skill (icons over emojis), using-streamlit-layouts skill (sidebar content guidelines)

### Task 2.2 — Add bordered containers to KPI cards
- **File:** `src/ui/today.py` (function `_render_kpi_row`)
- **Change:** Wrap each KPI `st.metric` inside `st.container(border=True)`:
  ```python
  with k1.container(border=True):
      st.metric(...)
  ```
  Same for k2, k3, k4. This gives each metric a proper card appearance.
- **Acceptance:** KPIs render as bordered cards with subtle elevation.
- **Ref:** streamlit_pro_tips.md Dica 4, using-streamlit-layouts skill (bordered containers)

### Task 2.3 — Align KPI card heights with height="stretch"
- **File:** `src/ui/today.py`
- **Change:** When the 4 columns might have different content lengths, ensure equal heights:
  ```python
  cols = st.columns(4)
  for col in cols:
      with col.container(border=True, height="stretch"):
          ...
  ```
  But this requires restructuring `_render_kpi_row` to use a uniform approach.
- **Acceptance:** All 4 KPI cards have equal height regardless of content length.
- **Ref:** streamlit_pro_tips.md Dica 5

### Task 2.4 — Center KPI content vertically inside bordered cards
- **File:** `src/ui/today.py`, `src/ui/month.py`
- **Change:** Use `col.container(border=True, height="stretch", vertical_alignment="center")` when wrapping each `st.metric`. The `vertical_alignment` parameter IS valid on the container returned by a column object per `streamlit_pro_tips.md` Dica 6 and the documented API.
  ```python
  k1, k2, k3, k4 = st.columns(4, vertical_alignment="center")
  with k1.container(border=True, height="stretch", vertical_alignment="center"):
      st.metric(label="Faturamento hoje", ...)
  ```
- **Acceptance:** Content is vertically centered in all KPI metric cards.
- **Ref:** streamlit_pro_tips.md Dica 5–6

### Task 2.5 — Make donut chart compact (side-by-side with sparkline)
- **Files:** `src/ui/today.py` (~line 66), `src/charts.py` (`build_modality_donut`)
- **Change:** Restructure the "Hoje" tab so the donut and sparkline share a 2-column row, with the donut in the left column and the sparkline in the right. This requires moving the sparkline data computation (`add_earnings_column`, loading) earlier in `render_today_tab` so both charts can render together. Also applies Task 4.2 (280 px height reduction) to the donut factory.
  ```python
  col_left, col_right = st.columns(2)
  with col_left:
      st.plotly_chart(donut, use_container_width=True)
  with col_right:
      st.plotly_chart(sparkline, use_container_width=True)
  ```
- **Acceptance:** Donut no longer dominates the tab; it shares equal space with the sparkline below the KPI row.
- **Ref:** analise-visual.md §2.1

### Task 2.6 — Improve sidebar responsiveness
- **File:** `app.py`
- **Change:** In `st.set_page_config`, set `initial_sidebar_state="auto"` — Streamlit auto-collapses on narrow viewports (<768px). Also ensure main content columns use proper responsive wrapping (columns auto-stack on narrow).
- **Acceptance:** Sidebar collapses on narrow screens; content uses full width.
- **Ref:** analise-visual.md §2.1, using-streamlit-layouts skill

---

## Phase 3: Visual Polish

*Priority: P1 — high. These changes make the app feel professional and polished.*

### Task 3.1 — Replace all emojis with Material icons
- **Files:** `app.py`, `src/ui/today.py`, `src/ui/month.py`, `src/ui/analysis.py`, `src/ui/settings.py`, `src/ui/sidebar.py`
- **Changes (systematic):**
  | Current Emoji | Material Icon | Context |
  |---|---|---|
  | 📊 | `:material/bar_chart:` | App title, tab icons |
  | 📅 | `:material/calendar_month:` | Tab, date label |
  | 📈 | `:material/trending_up:` | Analysis tab |
  | ⚙️ | `:material/settings:` | Config tab |
  | 💰 | `:material/payments:` | Earnings metric |
  | 📋 | `:material/content_paste:` | Exam count |
  | ⏱️ | `:material/timer:` | Hours metric |
  | 🎯 | `:material/target:` | Goal metric |
  | 💾 | `:material/save:` | Save button |
  | 🗑️ | `:material/delete:` | Delete button |
  | ✅ | `:material/check_circle:` | Success toast |
  | 📝 | `:material/edit_note:` | Update toast |
  | ⚠️ | `:material/warning:` | Alert |
  | 💡 | `:material/lightbulb:` | Insights |
  | 🧠 | `:material/psychology:` | AI button |
  | 🤖 | `:material/smart_toy:` | AI response |

  For `st.tabs`, use Material icons:
  ```python
  st.tabs([
      ":material/today: Hoje",
      ":material/calendar_month: Mês Atual",
      ":material/trending_up: Análise",
      ":material/settings: Config",
  ])
  ```
  Note: `st.tabs()` labels support Markdown, so Material icon syntax works.
- **Acceptance:** Zero emojis in the UI — all Material icons.
- **Ref:** improving-streamlit-design skill ("Use Material icons for a cleaner, more professional look")

### Task 3.2 — Replace emoji icon in page_icon
- **File:** `app.py`
- **Change:** `page_icon="📊"` → `page_icon=":material/monitor_heart:"` or `page_icon=":material/radiology:"`
- **Acceptance:** Browser tab shows Material icon.
- **Ref:** streamlit_pro_tips.md Dica 1

### Task 3.3 — Improve Save button feedback with loading state
- **File:** `src/ui/sidebar.py`
- **Change:** Wrap the save action in a lightweight loading indicator using session state and a spinner, **without converting the sidebar to a full `st.form`**. Use the native `icon` parameter for the Material icon (not Markdown in the label).
  > ⚠️ **BLOCKER WARNING:** `st.form` suppresses widget-driven reruns. Inside a form, changing the date picker would **not** update the default values of the modality inputs (`rm`, `tc`, `rx`) below it, because `load_daily(conn, date_str)` is computed at render time and forms only rerun on submit. This causes data to be saved for the wrong date. Keep the date picker and modality inputs outside any form.

  Correct approach: keep the imperative save button and use a spinner wrapper:
  ```python
  if st.button("Salvar produção", icon=":material/save:", type="primary", use_container_width=True):
      with st.spinner("Salvando..."):
          upsert_daily(conn, date_str, rm, tc, rx)
      st.session_state.pop("historical_cache", None)
      formatted = selected_date.strftime("%d/%m")
      action = "atualizada" if existing else "salva"
      st.toast(f"Produção de {formatted} {action}!", icon=":material/check_circle:")
      st.rerun()
  ```
  If needed, you can also gate double-clicks with `st.session_state` flags, but `st.spinner` already gives adequate feedback.
- **Acceptance:** Button click shows a spinner while saving; date-dependent pre-fill continues to work correctly.
- **Ref:** analise-visual.md §2.6, streamlit_pro_tips.md Dica 9

### Task 3.4 — Add skeleton loading states for historical data
- **File:** `src/ui/analysis.py`
- **Change:** Render skeleton placeholders **before** running the expensive computation, then replace them with actual charts once data loads:
  ```python
  from streamlit_extras.skeleton import skeleton

  # Step 1: Show skeleton placeholders while computing
  sk1, sk2 = st.columns(2)
  with sk1:
      skeleton(height=280)
  with sk2:
      skeleton(height=280)
  skeleton(height=280)  # full-width placeholder

  # Step 2: Compute data
  with st.spinner("Analisando dados históricos..."):
      stats = compute_historical_stats(...)

  # Step 3: Clear skeletons (rerun or empty replacement)
  ... render actual charts ...
  ```
  `skeleton()` requires a `height` parameter per the `streamlit_extras_guide.md`.
- **Acceptance:** Loading state shows animated skeleton cards before charts render.
- **Ref:** streamlit_extras_guide.md §5.1 (skeleton)

### Task 3.5 — Improve AI interaction UX
- **File:** `src/ui/analysis.py`
- **Change:**
  1. Add `st.caption("Exemplos: 'Qual dia foi mais produtivo?', 'Minha média é consistente?'")` below the AI button.
  2. Improve the in-flight guard message: use `st.status()` for a multi-step progress indicator instead of `st.info("⏳ Aguarde...")`.
  3. Add a "Cancelar" button that sets a flag to abort (even if LLM call continues server-side, the UI reflects cancellation intent).
  4. When no API key is configured, show a helpful empty state with link to OpenRouter instead of just disabled button.
- **Acceptance:** AI section has example prompts, better loading UX, and a cancel mechanism.
- **Ref:** analise-visual.md §3.5, §3.6

### Task 3.6 — Improve empty states across tabs
- **File:** `src/ui/today.py`, `src/ui/month.py`, `src/ui/analysis.py`
- **Change:**
  1. Today empty state: Remove the `unsafe_allow_html=True` + inline CSS `<div style="text-align:center;font-size:64px;">📋</div>`. Replace with `st.container(horizontal_alignment="center")` containing `st.markdown(":material/content_paste:", text_alignment="center")`. Note: the container's `horizontal_alignment` centers the container block, while `text_alignment` on the markdown centers the icon text within it — both are needed. The icon will render at default markdown size (~16 px) since the 64 px CSS is removed.
  2. Month empty state: Replace `st.info(...)` with a proper empty-state card matching the Today pattern (centered, bordered container, guidance text).
  3. Analysis empty state: Replace `st.info(...)` with a proper empty-state card.
  3. Fix existing Title Case labels:
     - `st.subheader("⚠️ Zona de Perigo")` → `"Zona de perigo"` (in `src/ui/settings.py`)
     - `st.subheader("Meta Mensal")` → `"Meta mensal"` (in `src/ui/settings.py`)
- **Acceptance:** All empty states are consistent bordered cards with Material icons and zero custom CSS/unsafe HTML. No `st.info()` for non-critical messages.
- **Ref:** streamlit_pro_tips.md Dica 14, improving-streamlit-design skill, creating-streamlit-themes skill ("No custom CSS unless explicitly requested")

### Task 3.7 — Use st.badge for status indicators where applicable
- **File:** `src/ui/today.py` (in KPI row)
- **Change:** In the KPI "Meta mensal" card, instead of plain text in delta, use `st.badge()` to show the MTD progress:
  ```python
  st.badge(f"{pct:.0f}%", icon=":material/target:", color="green" if pct >= 50 else "orange")
  ```
  Or keep current layout but add a badge for "on track" / "behind" status.
- **Acceptance:** Status is communicated via colored badges.
- **Ref:** improving-streamlit-design skill ("Badges for status")

### Task 3.8 — Configurable user name
- **Files:** `src/db.py`, `src/ui/settings.py`, `src/ui/sidebar.py`, `src/ui/month.py`
- **Change:** Replace the hardcoded name `"Galvani"` with a user-configurable value stored in the database.
  1. **DB:** Add a `user_settings` table (key/value pairs) in `init_db()` with default `user_name = "Galvani"`. Add `load_setting(conn, key, default)` and `save_setting(conn, key, value)` functions.
  2. **Config tab:** Add `st.text_input("Seu nome", value=..., key="cfg_name")` to the settings form, saved alongside prices and goal.
  3. **Sidebar greeting:** Load `user_name` via `ensure_settings()` into `st.session_state`. Replace hardcoded `"Galvani"` with the session variable (already covered by Task 2.1).
  4. **Rhythm alert:** Replace hardcoded `"Galvani, você está atrás..."` in `src/ui/month.py` (near line ~155 in `_render_rhythm_alert`) with `f"{st.session_state.user_name}, você está atrás..."`.
- **Acceptance:** User can set their name in Config; greeting and alerts use it.
- **Ref:** analise-visual.md §3 (personalização)

### Task 3.9 — Movable API key from .env to Config tab
- **Files:** `src/ui/settings.py`, `src/db.py`, `src/llm_client.py`, `src/ui/analysis.py`, `app.py`
- **Change:** Eliminate the `.env` file requirement. Store the OpenRouter API key in the DB and expose it via `session_state`.
  1. **DB:** Extend `user_settings` table (from Task 3.8) with `api_key` entry, default empty string.
  2. **Config tab:** Add `st.text_input("Chave API OpenRouter", type="password", value=..., key="cfg_apikey")` to the settings form.
  3. **LLMClient:** Already accepts `api_key` as a constructor parameter — no change needed to the class signature. Just pass `st.session_state.api_key` at instantiation time in the analysis tab.
  4. **Analysis tab:** Replace `api_key = os.environ.get("OPENROUTER_API_KEY")` (~line 120) with `api_key = st.session_state.get("api_key", "")`.
  5. **app.py:** Remove `from dotenv import load_dotenv` and `load_dotenv()` — the `.env` file is no longer needed.
  6. **Empty state:** When the key is empty, show `st.caption("Configure sua chave API na aba ⚙️ Config para ativar a análise com IA.")` and disable the button.
- **Acceptance:** No `.env` file needed; API key configured entirely within the UI.
- **Ref:** analise-visual.md §3.6 (empty state para IA); KISS principle

### Task 3.10 — Editable AI prompt
- **Files:** `src/ui/settings.py`, `src/db.py`, `src/llm_client.py`
- **Dependency:** Task 3.8 must be done first — the default prompt text currently hardcodes `"chamado Galvani"` and should use the configurable user name.
- **Change:** Let the user customize the system prompt sent to the LLM.
  1. **DB:** Extend `user_settings` table with `llm_prompt` entry, defaulting to the current `SYSTEM_PROMPT` text from `src/llm_client.py` (but parameterized with the user name from Task 3.8).
  2. **Config tab:** Add `st.text_area("Prompt da IA", value=..., height=200, key="cfg_prompt")` to the settings form, with `st.caption("Use {stats} como placeholder para os dados.")`.
  3. **LLMClient:** Accept the prompt as an optional constructor parameter (`prompt: str | None = None`). If not provided, fall back to reading `st.session_state.llm_prompt`.
- **Acceptance:** User can edit the AI prompt; changes take effect on the next analysis.
- **Ref:** analise-visual.md §3.6 (flexibilidade da IA)

### Task 3.11 — Update repository documentation
- **Files:** `README.md`, `.env.example` (remove)
- **Change:** The migration of API key from `.env` to the Config tab (Task 3.9) makes `.env.example` obsolete and invalidates the current installation instructions.
  1. **Remove** `.env.example` from the repository.
  2. **README.md — Instalação:** Remove the `cp .env.example .env` step. Installation is now just `pip install -r requirements.txt`.
  3. **README.md — IA (OpenRouter):** Replace the `.env`-based instructions with: "Configure sua chave API na aba ⚙️ **Config** > Chave API OpenRouter. A chave é salva localmente no banco SQLite."
  4. **README.md — Estrutura:** Remove `.env.example` from the project tree diagram.
  5. **README.md — Funcionalidades:** Update to mention user name configurability and editable AI prompt.
- **Acceptance:** README accurately reflects the Config-tab-only setup; no `.env` references remain anywhere in the repo.
- **Ref:** KISS principle; analise-visual.md §3 (usabilidade)

---

## Phase 4: Chart & Data Refinements

*Priority: P2 — medium. Makes charts more beautiful, accessible, and informative.*

### Task 4.1 — Improve progress gauge color scheme
- **File:** `src/chart_colors.py`
- **Change:** Replace red/amber/green scheme with a single-hue gradient from the app's primary teal:
  ```python
  "progress_danger": "#CCFBF1",     # teal-50 (lightest) for 0-25%
  "progress_warning": "#5EEAD4",     # teal-300 for 25-50%
  "progress_on_track": "#14B8A6",    # teal-500 for 50-75%
  "progress_achieved": "#0F766E",    # teal-700 for 75-100%
  ```
  This avoids red = "error" misinterpretation and creates a cohesive monochrome feel.
- **Acceptance:** Progress gauge uses teal gradient instead of traffic-light colors.
- **Ref:** analise-visual.md §3.3, creating-streamlit-themes ("Color harmony — monochromatic")

### Task 4.2 — Resize donut chart to be compact
- **File:** `src/charts.py` (`build_modality_donut`)
- **Change:** Reduce the chart's height and margins:
  ```python
  fig.update_layout(
      height=280,
      margin=dict(l=10, r=10, t=40, b=10),
  )
  ```
  Also reduce donut `hole=0.5` for more ring visibility.
- **Acceptance:** Donut fits alongside content without dominating.
- **Ref:** analise-visual.md §2.1

### Task 4.3 — Explicitly set chart colors via chartCategoricalColors
- **File:** All chart modules (`src/charts.py`, `src/charts_analysis.py`)
- **Change:** The Plotly charts already use explicit colors from `CHART_COLORS`. Verify that chart colors in `config.toml` match what charts use. Update `chartCategoricalColors` in both `[theme]` and `[theme.dark]` to match the `CHART_COLORS` dictionary or vice versa.
  ```python
  # In chart_colors.py, consider importing from config or keeping them synced manually.
  # For now: ensure config.toml chartCategoricalColors matches CHART_COLORS values.
  ```
- **Acceptance:** Both theme and explicit chart colors are consistent.
- **Ref:** streamlit_pro_tips.md Dica 18

### Task 4.4 — Improve chart tooltips formatting
- **File:** `src/charts.py`, `src/charts_analysis.py`
- **Change:** Ensure all tooltips use Portuguese labels:
  - `"Revenue"` → `"Faturamento"`
  - `"Day"` → `"Dia"`
  - `"R$"` formatting already correct via `fmt_brl`
  Verify all `hovertemplate` strings are in Portuguese.
- **Acceptance:** All chart tooltips read in Portuguese.
- **Ref:** analise-visual.md §1 (consistency)

### Task 4.5 — Add dark mode chart color adaptation
- **File:** `src/chart_colors.py` or chart functions
- **Change:** Use `st.context.theme.base` to detect dark mode and swap colors:
  ```python
  if st.context.theme.base == "dark":
      # Use lighter versions of the colors
  else:
      # Use standard colors
  ```
  This ensures charts remain readable on dark background.
- **Acceptance:** Charts are legible in both light and dark themes.
- **Ref:** creating-streamlit-themes skill on st.context

### Task 4.6 — Fix hardcoded annotation colors for dark mode legibility
- **File:** `src/charts.py` (`build_progress_gauge`, ~line 147)
- **Change:** The annotation text in the progress gauge hardcodes `font=dict(size=16, color="#0F172A")` — near-black. On the dark theme (`backgroundColor: #101010`), this is unreadable. Replace with a theme-aware value:
  ```python
  text_color = "#E5E7EB" if st.context.theme.base == "dark" else "#0F172A"
  ```
  Apply the same branching to any other chart annotation, `add_hline` label, or `add_vline` that hardcodes a text/line color incompatible with dark backgrounds.
- **Acceptance:** Progress gauge percentage and vertical marker are readable in both themes.
- **Ref:** creating-streamlit-themes skill ("Detecting current theme"); second-round reviewer finding #6

### Task 4.7 — Remove dead code and data assumptions
- **Files:** `src/ui/month.py`, `src/charts_analysis.py`
- **Change:**
  1. Remove unused function `_safe()` in `src/ui/month.py` (lines 94–95). It is never called.
  2. Replace hardcoded year `"Faturamento por Mês — 2026"` in `build_ytd_earnings_chart` (near line ~190 of `src/charts_analysis.py`) with the actual year from `year_month[:4]`.
- **Acceptance:** No dead code; chart titles show the correct year.
- **Ref:** KISS principle; second-round reviewer finding #8

---

## Phase 5: UX Enhancements & Polish

*Priority: P2–P3. Optional enhancements that add significant polish.*

### Task 5.1 — Add celebration effect on goal achievement
- **File:** `src/ui/month.py` or `src/ui/today.py`
- **Change:** When `pct_goal >= 100`, trigger `rain()` from streamlit-extras:
  ```python
  from streamlit_extras.let_it_rain import rain
  if pct >= 100:
      rain(emoji="🎉", font_size=36, falling_speed=5, animation_length=3)
  ```
  Use as a one-time celebration.
- **Acceptance:** Fun confetti-style animation when monthly goal is met.
- **Ref:** streamlit_extras_guide.md §5.3 (let_it_rain)

### Task 5.2 — Add star_rating for monthly performance
- **File:** `src/ui/month.py`
- **Change:** Show a star rating based on goal achievement:
  ```python
  from streamlit_extras.star_rating import star_rating
  stars = min(5, int(pct_goal / 20))
  star_rating(stars)
  ```
  Note: the guide documents `star_rating(value)` with a single positional argument, not `stars=`/`max_stars=`/`key=` kwargs. Verify the actual signature before implementing.
- **Acceptance:** Visual 5-star rating reflects monthly performance.
- **Ref:** streamlit_extras_guide.md §5.2

### Task 5.3 — Add stoggle for "Ver dados brutos" sections
- **File:** `src/ui/today.py` (potential new feature)
- **Change:** Add a collapsible section using `streamlit_extras.stoggle`:
  ```python
  from streamlit_extras.stoggle import stoggle
  stoggle("Ver dados brutos de hoje", st.dataframe(today_data))
  ```
- **Acceptance:** Raw data is accessible but hidden by default.
- **Ref:** streamlit_extras_guide.md §5.2

### Task 5.4 — (REMOVED — replaced by Task 2.6)
- **Rationale:** Detecting mobile viewports in Streamlit requires custom JavaScript or CSS, which violates the skill's theming rules. The sidebar auto-collapse from Task 2.6 (`initial_sidebar_state="auto"`) already provides adequate mobile access. Drop this task.

### Task 5.5 — Local persistence for preferences
- **File:** New utility module (optional)
- **Change:** Use `streamlit_extras.cookie_manager` to remember user preferences (theme, last tab) across sessions without server-side storage:
  ```python
  from streamlit_extras.cookie_manager import cookie_manager
  cookies = cookie_manager()
  last_tab = cookies.get("last_tab", "0")
  ```
- **Acceptance:** User returns to the same tab they left on.
- **Ref:** streamlit_extras_guide.md §5.5

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `app.py` | 0, 2, 3 | `page_icon` → Material icon, `st.set_page_config` updates, remove dotenv |
| `.streamlit/config.toml` | 0, 1, 4 | Full theme overhaul, dark mode, fonts, colors, hide deploy |
| `src/ui/sidebar.py` | 0, 2, 3 | Translate label, remove divider, Material icons, save spinner, use user_name from session_state |
| `src/ui/today.py` | 2, 3, 4 | Bordered KPI containers, stretch heights, donut resize, Material icons, remove unsafe_allow_html |
| `src/ui/month.py` | 2, 3, 5 | Card containers, empty state card, star rating, celebration, user name in rhythm alert |
| `src/ui/analysis.py` | 3, 5 | AI UX improvements, Material icons, skeleton loading, use session_state API key |
| `src/ui/settings.py` | 0, 3 | RX step fix, remove st.divider(), Material icons, user name / API key / prompt fields |
| `src/db.py` | 3 | Add `user_settings` table + load/save for name, API key, prompt |
| `src/llm_client.py` | 3 | Accept prompt + API key from parameters instead of hardcoded string / os.environ |
| `src/chart_colors.py` | 4 | Progress gauge gradient (teal monochrome) |
| `src/charts.py` | 4 | Donut height reduction, tooltip Portuguese check |
| `src/charts_analysis.py` | 4 | Dark mode adaptation, tooltip Portuguese check |
| `requirements.txt` | 3, 5 | Add `streamlit-extras>=1.5.0` |
| `README.md` | 3 | Replace .env-based setup with Config tab instructions |
| `.env.example` | 3 | Remove — API key now configured in UI |


## New Files

| File | Phase | Purpose |
|------|-------|---------|
| None strictly required | — | All changes fit within existing file structure. |

