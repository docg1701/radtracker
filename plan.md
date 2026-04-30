# Implementation Plan — radtracker Visual & UX Overhaul

## Goal
Transform radtracker from a functional Streamlit app into a **professional, polished SaaS dashboard** — following Cal.com's monochrome, clean design principles, implementing official Streamlit skill recommendations, and avoiding deprecated streamlit-extras.

---

## Phase 0: Foundation Fixes (Quick Wins)

*Priority: P0 — critical. These fix bugs and localization issues with minimal risk. Each is independent.*

### Task 0.1 — Translate date picker placeholder
- **File:** `src/ui/sidebar.py` (line ~47)
- **Change:** Add `help="Selecione uma data"` or use `label` parameter. The native `st.date_input` placeholder cannot be translated via parameter — instead, use `st.date_input("📅 Selecione uma data", ...)` to make the label itself the Portuguese instruction.
- **Acceptance:** Date picker no longer shows "Select a date." in English.
- **Ref:** analise-visual.md §2.4 (placeholder em inglês)

### Task 0.2 — Fix RX spinbutton step in Config tab
- **File:** `src/ui/settings.py` (line ~82)
- **Change:** Replace `step=0.01` (already correct) — verify current value. If the issue is that `+`/`-` goes by 1.0, ensure `step=0.01` is set on the `st.number_input` for RX. Actually, re-read: the current code already has `step=0.01`. The real issue per analise-visual.md §2.5 is decimal sensitivity. The fix: set `step=0.50` for RX to make increments meaningful (R$0.50 instead of R$0.01).
- **Acceptance:** RX +/- buttons change by R$0.50 increments.
- **Ref:** analise-visual.md §2.5

### Task 0.3 — Hide Deploy button and Streamlit Cloud branding
- **File:** `.streamlit/config.toml`
- **Change:** Add `[browser]` section if not present, include:
  ```toml
  [browser]
  gatherUsageStats = false
  ```
  And add to `app.py` (within `st.set_page_config` or right after):
  ```python
  st.set_page_config(
      page_title="radtracker",
      page_icon=":material/monitor_heart:",  # or keep medical icon
      layout="wide",
      initial_sidebar_state="auto",
  )
  ```
  The Deploy button is part of Streamlit Cloud — it appears when the app is detected as deployable. To suppress it, ensure `.streamlit/config.toml` has `[server] headless = true` (already present). If still visible, add `[server] enableStaticServing = false`. The hamburger menu can be hidden with the theme — ensure it doesn't obscure the Deploy button.
- **Note:** Streamlit deliberately shows Deploy on cloud. If running locally, it shouldn't appear. If on Streamlit Cloud, it's expected. Mark this as **verified fixed** if local; **won't fix** if on cloud.
- **Acceptance:** No Deploy button visible on local runs.
- **Ref:** analise-visual.md §2.2

### Task 0.4 — Remove st.divider() from sidebar
- **File:** `src/ui/sidebar.py` (line ~71)
- **Change:** Replace `st.divider()` with `st.space("small")` or simply remove it — Streamlit's default spacing between the button and caption is sufficient.
- **Acceptance:** Sidebar footer looks cleaner without heavy divider line.
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
- **Acceptance:** Toggle works; dark theme uses dark surface (#101010, matching Cal.com footer).
- **Ref:** creating-streamlit-themes section on light/dark modes

---

## Phase 2: Layout & Responsiveness

*Priority: P1 — high. Structural improvements that make the dashboard feel like a dashboard.*

### Task 2.1 — Restructure sidebar (cleaner, professional)
- **File:** `src/ui/sidebar.py`
- **Change:**
  1. Replace `st.title("📊 radtracker")` with clean `st.logo()` for branding (if a logo exists) or keep minimal.
  2. Replace `st.markdown("Olá, **Galvani** 👋")` with `st.caption("Olá, Galvani")` — cleaner, less shouty.
  3. Update `st.date_input("📅 Data", ...)` → `st.date_input("Data", ...)` using Material icon via `label` parameter or omit icon in label. Actually: date_input doesn't support icon parameter natively, so use clean label: `st.date_input("Data", ...)`.
  4. Replace `st.button("💾 Salvar produção", ...)` → `st.button("Salvar produção", icon=":material/save:", ...)` using native `icon` param.
  5. Add a loading spinner simulation on save: use `st.session_state` flag to show spinner while saving.
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

### Task 2.4 — Add vertical_alignment to center content in tall cards
- **File:** `src/ui/today.py`, `src/ui/month.py`
- **Change:** Add `vertical_alignment="center"` to KPI containers when card height exceeds content.
- **Acceptance:** Content is vertically centered in metric cards.
- **Ref:** streamlit_pro_tips.md Dica 6

### Task 2.5 — Make donut chart compact (side-by-side with KPIs or reduced)
- **File:** `src/ui/today.py` (line ~66)
- **Change:** Reduce donut chart height. Instead of full `width="stretch"`, wrap it in a container with limited height. Option: show donut in a 2-column layout with the sparkline:
  ```python
  col_left, col_right = st.columns(2)
  with col_left:
      st.plotly_chart(donut, width="stretch")
  with col_right:
      st.plotly_chart(sparkline, width="stretch")
  ```
  Alternatively, reduce donut to 300px height via chart config.
- **Acceptance:** Donut doesn't dominate the "Hoje" tab; KPIs are the primary visual element.
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
- **Change:** Use `on_click` callback pattern to show spinner/loading state:
  1. Add `st.session_state.saving = True` in the callback
  2. Show spinner wrapper around the save logic
  3. Set `saving = False` on completion
  This requires restructuring the button to use `st.form` or `on_click` + `st.fragment` for partial rerun.
  **Better approach:** Wrap the entire sidebar form in `st.form()` so Streamlit handles the submit lifecycle natively.
  ```python
  with st.sidebar:
      with st.form("daily_entry"):
          # ... inputs ...
          submitted = st.form_submit_button("Salvar produção", icon=":material/save:", use_container_width=True)
          if submitted:
              # save logic
              st.toast(...)
              st.rerun()
  ```
- **Acceptance:** Button shows loading state during save; native form boundary prevents premature reruns.
- **Ref:** analise-visual.md §2.6, streamlit_pro_tips.md Dica 9

### Task 3.4 — Add skeleton loading states for historical data
- **File:** `src/ui/analysis.py`
- **Change:** While `compute_historical_stats` runs (it shows a spinner), also render skeleton placeholders for the charts section using `streamlit_extras.skeleton`:
  ```python
  from streamlit_extras.skeleton import skeleton
  skeleton()
  ```
  This gives a polished loading experience instead of a blank spinner.
- **Acceptance:** Loading state shows animated skeleton cards.
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
  1. Today empty state: Already good — keep the illustration card. Replace emoji 📋 with `:material/content_paste:` at large size.
  2. Month empty state: Replace `st.info(...)` with a proper empty-state card matching the Today pattern (centered, bordered container, guidance text).
  3. Analysis empty state: Replace `st.info(...)` with a proper empty-state card.
- **Acceptance:** All empty states are consistent bordered cards with Material icons.
- **Ref:** streamlit_pro_tips.md Dica 14, improving-streamlit-design skill

### Task 3.7 — Use st.badge for status indicators where applicable
- **File:** `src/ui/today.py` (in KPI row)
- **Change:** In the KPI "Meta mensal" card, instead of plain text in delta, use `st.badge()` to show the MTD progress:
  ```python
  st.badge(f"{pct:.0f}%", icon=":material/target:", color="green" if pct >= 50 else "orange")
  ```
  Or keep current layout but add a badge for "on track" / "behind" status.
- **Acceptance:** Status is communicated via colored badges.
- **Ref:** improving-streamlit-design skill ("Badges for status")

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
- **File:** Potentially `src/chart_colors.py` or chart functions
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
  star_rating(stars=stars, max_stars=5, key="monthly_rating")
  ```
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

### Task 5.4 — Add floating button for quick data entry on mobile
- **File:** `app.py`
- **Change:** On mobile viewports, add a floating "+" button that opens a dialog for quick data entry:
  ```python
  from streamlit_extras.floating_button import floating_button
  if floating_button("+", icon=":material/add:"):
      show_quick_entry_dialog()
  ```
  Or more practically, just ensure the sidebar is accessible and collapsible.
- **Acceptance:** Easy data entry access on mobile.
- **Ref:** streamlit_extras_guide.md §5.2

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

### Task 5.6 — Add app version badge to footer
- **File:** `app.py` or new footer component
- **Change:** After the tabs, add a subtle footer:
  ```python
  st.space("large")
  with st.container():
      _, col_center, _ = st.columns([1, 2, 1])
      with col_center:
          st.caption(
              "radtracker v1.1 · Feito com :material/favorite: para radiologistas · "
              "[Sugerir melhoria](https://github.com/user/radtracker/issues)"
          )
  ```
- **Acceptance:** Subtle footer at the bottom of every page.
- **Ref:** DESIGN.md footer pattern, improving-streamlit-design skill (caption over info)

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `app.py` | 0, 2, 3, 5 | `page_icon` → Material icon, `st.set_page_config` updates, footer |
| `.streamlit/config.toml` | 0, 1, 4 | Full theme overhaul, dark mode, fonts, colors, hide deploy |
| `src/ui/sidebar.py` | 0, 2, 3 | Translate label, remove divider, Material icons, `st.form` pattern |
| `src/ui/today.py` | 2, 3, 4 | Bordered KPI containers, stretch heights, donut resize, Material icons |
| `src/ui/month.py` | 2, 3, 5 | Card containers, empty state card, star rating, celebration |
| `src/ui/analysis.py` | 3, 5 | AI UX improvements, Material icons, skeleton loading |
| `src/ui/settings.py` | 0 | RX step fix, Material icons |
| `src/chart_colors.py` | 4 | Progress gauge gradient (teal monochrome) |
| `src/charts.py` | 4 | Donut height reduction, tooltip Portuguese check |
| `src/charts_analysis.py` | 4 | Dark mode adaptation, tooltip Portuguese check |

## New Files

| File | Phase | Purpose |
|------|-------|---------|
| None strictly required | — | All changes fit within existing file structure. Optional: `src/ui/footer.py` if footer becomes reusable. |

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

2. **Dark mode chart legibility** — Plotly charts with `rgba(0,0,0,0)` backgrounds inherit the page background but text annotations may need explicit color adjustment. Risk: Medium. Mitigation: Use `st.context.theme.base` to branch chart styling.

3. **st.form migration in sidebar** — Converting the sidebar to a form changes the interaction model (all inputs reset on submit unless managed). Risk: Low. Mitigation: form is the idiomatic pattern and actually improves UX.

4. **streamlit-extras volatility** — As noted in the guide, extras can be deprecated when core absorbs features. Risk: Low (for polish extras). Mitigation: Only adopt extras from Group B ("gain from core") or Group C ("polish"): `skeleton`, `let_it_rain`, `star_rating`, `stoggle`. Avoid Group A (deprecated).

5. **Deploy button on Streamlit Cloud** — If the user deploys to Streamlit Cloud, the Deploy button is a platform feature and cannot be hidden. Risk: Low. Mitigation: Document this as expected; it's only an issue on local runs.

6. **Config.toml font loading delay** — Google Fonts load via CDN; first cold load may show fallback fonts briefly. Risk: Low. Mitigation: The fallback stack (`Inter` → sans-serif) is acceptable for the split second before fonts load.

## Priority Summary

| Priority | Count | Tasks |
|----------|-------|-------|
| P0 (critical) | 4 | 0.1–0.4: Bug fixes and localization |
| P1 (high) | 13 | 1.1–1.4, 2.1–2.6, 3.1–3.3: Theme, layout, icons |
| P2 (medium) | 7 | 3.4–3.7, 4.1–4.5: Polish, charts |
| P3 (nice-to-have) | 5 | 5.1–5.6: Extras, celebrations |

---

## Quick Reference: What NOT to Do

Per official Streamlit skills:
- ❌ No custom CSS (`st.markdown(unsafe_allow_html=True)`, `st.html()` style blocks) for theming — use config.toml
- ❌ No deprecated streamlit-extras: `add_vertical_space`, `app_logo`, `colored_header`, `row`, `stylable_container`, `tags`
- ❌ No `st.cache_resource` for data (use `st.cache_data`)
- ❌ No more than 4 columns in a single row
- ❌ No `st.divider()` (use natural spacing or `st.space()`)
- ❌ No emojis as functional icons (use Material icons); emojis only for celebrations
- ❌ No Title Case labels (use sentence casing)
- ❌ No `st.info()` for simple metadata (use `st.caption()`)
