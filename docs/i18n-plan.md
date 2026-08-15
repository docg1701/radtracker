# Bilingual UX Plan — EN-US native, PT-BR option

Status: approved design, pending implementation. Delete this file after implementation;
fold the durable bits (i18n architecture) into `docs/context.md` + `docs/meta-prompt.md`.

## 0. Project direction (owner decision)

- **English is the native language of the project.** Web UX defaults to
  American English; PT-BR is an opt-in. All code, comments, docstrings,
  logs, and docs are English. User data (modality labels, user name,
  custom LLM prompt) is never translated — the user registers it in their
  own language.
- **Web UX language and auth CLI language are configured separately:**
  web → `user_settings` DB row `language` (default `"en"`); CLI →
  `cli_language` key in `auth.json` (default `"en"`).
- Untranslatable / out-of-scope items confirmed by owner (do NOT touch):
  Plotly modebar tooltips, browser-native calendar popup locale, browser
  chrome (autofill, context menus), free-form LLM output, DB-stored user
  data, brand name, modality slugs, Material icon names.

## 1. Research findings (find-docs / ctx7)

- **Streamlit has no native i18n API.** Official docs return nothing for
  internationalization/localization queries — no translation mechanism,
  no locale setting.
- **Python industry standard is stdlib `gettext`.** Its *global* API is
  process-wide — unsafe in Streamlit (one process serves all sessions).
  The *class-based* API needs `.po`/`.mo` toolchain and file I/O.
- **Community practice for fixed languages in Streamlit:** a typed dict
  catalog + a `t()` helper — the gettext `_()` pattern without the toolchain.

**Decision:** dict catalog in `src/i18n.py`. Not gettext: two fixed
languages, no translator teams, no plural engine, `.po` tooling buys
nothing. Stdlib-only (no new dependencies — hard constraint).

## 2. Design

### 2.1 Translation catalog — `src/i18n.py` (new)

```python
LANGUAGES = ("en", "pt")
TRANSLATIONS: dict[str, dict[str, str]] = {
    "web.kpi.earnings_today": {
        "en": "Today's revenue",
        "pt": "Faturamento hoje",
    },
    "cli.menu.2fa_enable": {
        "en": "Enable / reconfigure 2FA (QR code)",
        "pt": "Ativar / reconfigurar 2FA (QR code)",
    },
    ...
}

def translate(key: str, lang: str, **fmt) -> str:
    """Pure: TRANSLATIONS[lang][key]; KeyError = fail loud."""
    text = TRANSLATIONS[lang][key]
    return text.format(**fmt) if fmt else text

def t(key: str, **fmt) -> str:
    """Web wrapper: reads st.session_state.lang (default 'en')."""
    return translate(key, st.session_state.get("lang", "en"), **fmt)
```

- Keys: stable ASCII snake_case ids, namespaced `web.*` / `cli.*` — one
  catalog serves both the Streamlit app and the SSH CLI (DRY).
- EN values are the **canonical source strings**; PT values are the current
  PT-BR strings, so PT mode keeps today's wording.
- Missing key = `KeyError` (fail loud).
- Call sites apply `md_escape()` exactly as today (EN strings contain `R$` too).
- **No `translate()` at module level** (defaults evaluated at import). Resolve
  language inside functions.

### 2.2 Web language state + toggle (default EN)

- `st.session_state.lang`, default `"en"`.
- Toggle: `st.segmented_control` options `["English", "Português (Brasil)"]`,
  label `:material/translate:` + `t("web.lang.label")`, `key="lang_selector"`,
  `on_change` sets `st.session_state.lang`.
- Rendered in `app.py` right after `set_page_config`, **before the auth
  gate** — the gate calls `st.stop()` when unauthenticated, so the login
  screen is bilingual too.
- Persistence: `user_settings` row `language` (`en`/`pt`).
  - Load: in `ensure_settings`, only when `"lang" not in st.session_state`.
  - Save: toggle `on_change` → `save_setting(get_connection(), "language",
    lang)` only when authenticated (DB not booted pre-login).
- Tab radio (`key="main_tabs"`) stores selection by index — language switch
  keeps the tab; labels re-render. No change needed.

### 2.3 Auth CLI — `scripts/manage_auth.py` (mandatory, owner decision)

- Fully English-native menu, prompts, status, and errors.
- Menu gains a language option **before "0) Exit"**:

  ```
  ┌──────────────────────────────────────────┐
  │ Radtracker — Authentication management   │
  ├──────────────────────────────────────────┤
  │ 1) Enable / reconfigure 2FA (QR code)    │
  │ 2) Disable 2FA                           │
  │ 3) Change password                       │
  │ 4) Change username                       │
  │ 5) Web session (days)                    │
  │ 6) Repair auth.json                      │
  │ 7) Status                                │
  │ 8) Language / Idioma (EN)                │
  │ 0) Exit                                  │
  └──────────────────────────────────────────┘
  ```

- Option 8 toggles en↔pt, persists `cli_language` in `auth.json`
  (via existing `save_auth` — atomic, 0600), reprints the menu in the new
  language. Label flips: PT mode shows `8) Idioma / Language (PT)`.
- **Default is English** when `cli_language` is absent (existing
  production `auth.json` files must keep working — optional key).
- `src/auth_store.py`: `_validate` gains optional `cli_language: str`
  (validated as `"en"`/`"pt"` when present; absent = `"en"`). Separate from
  the web `user_settings` row — the two languages are independently
  configurable, as required.
- `src/auth_bootstrap.py` is already English ("created"/"exists", English
  errors) — no change.
- CLI uses `translate(key, cli_lang)` directly (no Streamlit session).

### 2.4 Dates (decision: MM/DD/YYYY in EN, DD/MM/YYYY in PT)

- `src/formatting.py`: month names per language; `month_abbr()`,
  `month_name()` gain `lang: str = "en"` (chart tests updated or defaulted).
- `sidebar.py`: date_input `format="MM/DD/YYYY"` (en) / `"DD/MM/YYYY"` (pt);
  toast date `strftime("%m/%d")` / `("%d/%m")`.
- Chart x-axes use day numbers / ISO strings — locale-neutral, no change.
- The date-picker popup itself follows the browser locale — untouchable
  (see §3).

### 2.5 Currency (decision: bare `$` everywhere, localized notation)

- **Symbol: `$` only — no `US$`, no `R$`.** It marks money generically;
  the user knows the values are reais. Language-neutral and internet-safe.
- `fmt_brl()` is **replaced** by a single `fmt_money(value, lang)` in
  `src/formatting.py` (two divergent PT formatters are a trap):
  - `en` → `$1,250.00` (US separators, HALF_UP quantization),
  - `pt` → `$1.250,00` (BR separators),
  - nan/inf/negative handling unchanged (minus sign stays a real minus).
- All call sites (UI, `llm_client.py` RAG context) switch to
  `fmt_money(..., lang)`; `fmt_brl` is deleted; its tests migrate.
- `md_escape()` unchanged — every `$` is escaped for markdown exactly as
  today (LaTeX pairs only form on unescaped `$`).
- **`src/text_sanitize.py` rewrite (mandatory):** the currency-escape regex
  `(?<=R)\$(?![a-zA-Z\\])` depends on the "R" prefix. Replace with a
  currency-context rule: escape `$` adjacent to digits that is NOT part of
  a `$$...$$` math pair the sanitizer itself introduces. LLM output still
  says "R$" sometimes — the rule must catch both. Update
  `tests/test_text_sanitize.py` with regression cases.
- Charts: `tickprefix="R$ "` → `"$ "`; hovertemplates `R$ %{y:,.2f}` →
  `$ %{y:,.2f}` (d3 US grouping in hovers stays as-is — pre-existing,
  out of scope).
- Settings captions: "Preço (R$)" → "$".

### 2.6 LLM / insights language (decision: follows the UI)

- Default is English everywhere: `_DEFAULT_LLM_PROMPT`, RAG context
  (`build_rag_context`), weekday names, `insights_rules` narrative.
- In PT mode, append one instruction line to the effective system prompt —
  `t("web.llm.answer_language_pt")` ("Responda em português brasileiro.") —
  instead of rewriting the user's stored custom prompt. EN mode appends
  nothing.
- `src/insights_rules.py`: `generate_rule_insights(stats)` →
  `generate_rule_insights(stats, lang="en")`; sentences become `t()`
  templates; plurals via explicit plural keys.
- `src/ui/chat.py`: `_SUGGESTIONS` per language (they become user
  messages); initial-report trigger message and empty-state copy → `t()`.
- `src/llm_client.py`: RAG context template per language; user-visible
  error strings → `t()`.

### 2.7 Code hygiene (owner decision)

- Sweep existing PT comments/docstrings in code to English (e.g. PT
  comments in `src/ui/chat.py`, PT docstrings in `src/llm_client.py`,
  `scripts/manage_auth.py` after its translation).
- All logs in English.
- Docs already English; `docs/meta-prompt.md` hard-constraint "PT-BR for
  all user-facing text" must be updated to the EN-native policy (part of
  Phase 5).

## 3. Untranslatable / out of scope (confirmed — do NOT touch)

1. Plotly modebar tooltips (Zoom/Pan/Download) — hardcoded English in
   plotly.js, no Python API. English in both modes.
2. Date-picker popup calendar — follows the browser/OS locale, not the app.
3. Browser chrome — autofill hints, password-manager prompts, context menu.
4. Free-form LLM output — prompt steered, not deterministically controlled.
5. DB-stored user data — modality labels, user name, custom LLM prompt
   (user registers in their own language; never auto-translated).
6. Brand name, modality slugs, Material icon names — language-neutral.

## 4. Conversion inventory (by file, ~200 keys)

| File | Scope |
|------|-------|
| `src/i18n.py` | **new** — catalog (`web.*` + `cli.*`), `translate()`, `t()` |
| `src/formatting.py` | month names/abbr per lang, `fmt_money()` |
| `src/ui/common.py` | empty-state default title (resolve inside), cache spinner to call site |
| `app.py` | 5 tab labels, auth-config error, navigation label, toggle render |
| `src/ui/login.py` | login/TOTP forms, errors, footer captions (2FA), Logout |
| `src/ui/sidebar.py` | greeting, Date label, empty-modality info, Save/Saving/toast |
| `src/ui/today.py` | 4 KPI cards, deltas, badges, empty states, Overview, raw data expander |
| `src/ui/month.py` | KPI row, rhythm alert, celebration toast, empty states, raw data expander, "projected"/"remaining"/"Target: X/day" |
| `src/ui/analysis.py` | expander label, 4 subheaders, captions, empty states |
| `src/ui/chat.py` | empty states, suggestions, buttons, streaming status/errors, initial report |
| `src/ui/settings.py` | grid headers/captions/buttons/toasts/warnings, AI labels + `help=`, thinking radio format_func, validation errors, danger zone |
| `src/charts.py` | 3 titles, legend names, hovertemplates, "Today" annotation, gauge label, month title → `month_name(lang)`; `tickprefix="$"` |
| `src/charts_analysis.py` | legend names (1–2 strings) |
| `src/insights_rules.py` | narrative rewrite → lang param, default EN |
| `src/llm_client.py` | RAG context templates, weekdays, error strings, PT answer-instruction append; `fmt_money` in context |
| `src/text_sanitize.py` | currency-escape regex without the `R` lookbehind (digit-context, math-pair safe) |
| `scripts/manage_auth.py` | **full EN translation + language menu option before Exit + `cli_language` persistence** |
| `src/auth_store.py` | `_validate` gains optional `cli_language` |

Chart builders are pure functions — add `lang: str = "en"` param; UI passes
the active language.

## 4.1 Complete `R$` / `$` / currency touchpoint catalog

Snapshot of every place the currency symbol, `fmt_brl`, `MONTHS_PT`, and the
`$` sanitizer regexes appear (line numbers = current master; re-verify with
the Phase 6 greps below after each phase lands).

### A. `src/formatting.py` — formatter rewrite
- L6–19: `MONTHS_PT` → per-language month names (EN default).
- L22–31: `month_abbr()`, `month_name()` → `lang` param; `M1`/`Mês` fallbacks → EN.
- L39: `md_escape()` docstring (“containing R$") → “$".
- L49–72: `fmt_brl()` deleted → `fmt_money(value, lang)`; literal outputs
  `"R$ —"`, `"R$ ∞"`, `"−R$ ∞"`, `f"R$ {int_str},{decimal_part:02d}"`.

### B. `src/text_sanitize.py` — the LLM regex core (highest-risk file)
- L24–27: `_CURRENCY_DOLLAR_RE = (?<=R)\$(?![a-zA-Z\\])` → replaced by a
  digit-context rule **with math-pair protection**: a new paired-`$`
  detector (`$...$`, lazy/DOTALL) marks math pairs first; only unpaired `$`
  followed by digit gets escaped. Behavior deltas:
  - `$50` (bare, unpaired) → NOW `\$50` (was left alone),
  - `$25\times4 = 100$` (paired) → unchanged,
  - `R$ 100` / `R$100` (LLM still says R$) → unchanged.
- L55–56: `sanitize_token()` step 3 — same new rule.
- L80–83: `sanitize_text()` step 3 — new rule must run after legacy `\\$`
  strip and **before** `\(...\)`/`\[...\]` conversion (converted pairs are
  added after escaping, so they stay math — same order as today).
- Docstrings L11–17, 24–26, 47–48: examples “R$ 100", “R$100" → “$100".

### C. `src/llm_client.py` — RAG context + errors
- L39–56: `_RAG_TEMPLATE` — all PT section headers (`=== DATA ATUAL ===`, …)
  → per-language template (EN default).
- L96–97: `SEMANA` PT weekday list → per-language.
- L107: fallback `"R$ 0,00"` → `fmt_money(0.0, lang)`.
- L152–154: modality line `f"ticket R$ {ticket_exame:.2f}/exame"`,
  `f"≈ R$ {rec_hora:.2f}/h"`, `"exames"` → `$` + `fmt_money` + per-language
  labels (whole line is a template).
- L159: fallback `"R$ 0,00"`.
- L169–179: block template — `Faturamento`, `Dias trabalhados`, `Média
diária`, `Ticket médio`, `Horas estimadas`, `h/dia`, `Receita/h`, `Melhor
dia`, `Total exames`, `Modalidades:` → per-language; 5× `fmt_brl` → `fmt_money`.
- L190/192: `"(sem dados mensais)"`, `"(sem dados diários)"` → per-language.
- L201–208: daily-table header `"Data"` → per-language (abbreviation logic
  stays — operates on user labels, not translated).
- L213–214: `"{day} de {MONTHS_PT[...]} de {year} ({SEMANA[...]})"` →
  per-language date template.
- L217–228: 6× `fmt_brl` in the enriched dict → `fmt_money(..., lang)`.
- L239/241: `LLMUnavailableError("API key não configurada")`,
  `"Modelo LLM não configurado"` → `t()`.
- L354: `"Erro de conexão com OpenRouter: {exc}"` → `t()`.
- `build_rag_context()` signature gains `lang`.

### D. `src/charts.py`
- L129: sparkline hover `"%{x}: R$ %{y:,.2f}<extra></extra>"` → `$`.
- L142, L291: `tickprefix="R$ "` → `"$ "`.
- L247: `"Dia %{x}: R$ %{y:,.2f}"` → `"Day %{x}: ..."` + `$`.
- L256: `"Alvo: R$ %{y:,.2f}"` → `"Target: ..."` + `$`.
- L278, L358–365: `MONTHS_PT` titles, `"Mês"` fallback → `month_name(lang)`.
- Plus PT chrome from the §4 table: L77, L135, L203 titles; L185 `restante`;
  L244 `Faturamento`; L253 `Alvo diário`; L270 `Hoje` annotation.
- `tests/test_charts.py`: no `R$` assertions today (verified) — nothing breaks;
  add `$` assertions for the new hovertemplates.

### E. `src/charts_analysis.py`
- L53, L60: MA hovers `"MA7 dia %{x}: R$ %{y:,.2f}"` → `$` + EN.
- L76, L154, L299: `tickprefix="R$ "` → `"$ "`.
- L135: `<extra>Semana passada</extra>` → `Last week`.
- L141: `<extra>Esta semana</extra>` → `This week`.
- L276–277: YTD hover + `text=[f"R$ {v:,.0f}"...]` → `$`.
- L286: `text=f"Meta: R$ {goal:,.0f}"...` → `"Goal: $"`.
- L197, L262: `month_abbr(ym)` → `lang` param.

### F. `src/insights_rules.py`
- L16: import `MONTHS_PT, fmt_brl` → `fmt_money` + per-language months.
- L20: `_gap_label` docstring `'R$ X acima'` → `$` + per-language words
  (`acima/abaixo` → `above/below`).
- L23: `_plural` `dia restante/dias restantes` → per-language.
- L33–35: `_prev_month_label` `MONTHS_PT[prev].lower()` → per-language.
- L41–end: full narrative → `t()` templates; 8× `fmt_brl` → `fmt_money`.

### G. UI call sites (`fmt_brl` consumers)
- `src/ui/today.py`: import; raw-data lines (`Faturamento:`, `Horas:`),
  KPI card value, meta delta `md_escape(fmt_brl(mtd))` → `fmt_money(lang)`.
- `src/ui/month.py`: import; KPI deltas (`projetado`, `restantes`,
  `Alvo: .../dia`), rhythm alert (4 amounts, one markdown paragraph —
  `md_escape` each) → `fmt_money(lang)`.

### H. `src/ui/settings.py`
- L117: caption `"preço (R$)"` → `"price ($)"` / `t()`.
- L129: header `"**Preço (R$)**"` → `$`.
- L332: label `"Meta mensal (R$)"` → `$`.

### I. Tests with `R$` expectations (must be updated in the same phase)
- `tests/test_formatting.py` L7–36: 10 `fmt_brl` tests → `fmt_money` both
  langs; L41–44: `MONTHS_PT` → per-language months.
- `tests/test_text_sanitize.py` L10, 31, 44, 52, 55, 75–79, 108–118, 168–173:
  keep passing (R$ still appears in LLM output); L17, 21, 34–35, 58–59:
  **expected values change** (`$50` now escapes; legacy `\\$ 100` after
  strip becomes `\$ 100`); L64–71, 89–103, 145–148: math pairs must stay
  unchanged (regression net for the new rule).
- `tests/test_llm_client.py` L117 (`"R$" in detail`), L465 (`"R$ 3.915,00"`),
  L601–606 (`"R$ 250,00"`, `"R$ 400,00" not in`, `"R$ 25.00/exame"`) → `$`
  + EN expectations.
- `tests/test_insights.py` L75–166: ~12 assertions → `$` + EN expectations.
- `tests/test_charts.py`, `tests/test_ui_month.py`: no `R$` pins (verified).

### J. Docs mentioning `R$` / `fmt_brl` / `MONTHS_PT`
- `docs/meta-prompt.md` L43, L123, L130 (sanitize order description),
  L135, L140 → update to `$` + `fmt_money` + EN-native policy.
- `docs/context.md` L36, L103.
- `README.md` L75.
- `AGENTS.md`: no hits (verified).

### K. Code comments mentioning `R$`
- `src/calculations.py` L243 (`R$/dia corrido`) — English sweep anyway.
- `src/formatting.py`, `src/text_sanitize.py`, `src/insights_rules.py`
  docstrings — covered in A/B/F.

### Phase 6 verification greps (must return only intended leftovers)

```bash
grep -rn 'R\$' app.py src/ scripts/        # only text_sanitize docstrings/LLM-keeps-R$ cases
grep -rn 'fmt_brl\|MONTHS_PT' app.py src/ scripts/ tests/
grep -rn 'tickprefix="R\$' src/charts*.py
grep -rn 'R\$' tests/                       # only sanitizer R$-still-valid cases
```

## 5. Phases

**Phase 0 — Foundation:** `src/i18n.py` + `tests/test_i18n.py`:
- en/pt key parity (same key set in both languages),
- `translate()`/`t()` lookup, missing key raises, default lang = en,
- `fmt_money()` both notations + nan/inf/negative parity with `fmt_brl`,
- `month_name`/`month_abbr` per language.

**Phase 1 — Web toggle + gate:** toggle in `app.py` (pre-gate, default EN),
session state + DB persistence (`language` default `"en"`), convert `app.py`,
`login.py`, `sidebar.py`, `common.py`. Login screen and sidebar bilingual,
English by default.

**Phase 2 — Core tabs:** `today.py`, `month.py`, `analysis.py`.

**Phase 3 — Settings + Chat:** `settings.py`, `chat.py`.

**Phase 4 — Data-driven text:** `formatting.py` call sites, `charts.py`,
`charts_analysis.py`, `insights_rules.py`, `llm_client.py`,
`text_sanitize.py` (currency regex rewrite + regression tests). Work file
by file through the **§4.1 catalog** (A–K) and update the matching test
file in the same phase.

**Phase 5 — Auth CLI:** `scripts/manage_auth.py` EN-native + language option
(before Exit) + `cli_language` in `auth.json`; `auth_store.py` validation;
update `tests/test_manage_auth.py`.

**Phase 6 — Code hygiene + audit:**
- Sweep PT comments/docstrings → English across `src/`, `app.py`, `scripts/`.
- Update `docs/meta-prompt.md` (EN-native constraint), `docs/context.md`
  (module notes), README if it mentions PT-BR UI.
- `grep` sweep for remaining PT literals in UI code.
- Run the **§4.1 Phase 6 verification greps** — nothing in the catalog may
  remain outside the intended leftovers.
- Manual pass: login screen, 5 tabs, charts, toasts in both languages,
  toggling mid-session; CLI in both languages, language persisted across
  runs.
- Full quality gate (AGENTS.md): pytest, ruff, mypy, hadolint, yamllint,
  actionlint, markdownlint, ansible-lint.

## 6. Tests

- New: `tests/test_i18n.py` (parity, lookup, fail-loud, `fmt_money`,
  per-language months, EN/PT insight narrative spot-checks, RAG context
  language instruction).
- Updated: `tests/test_manage_auth.py` (EN strings, language option toggles
  + persists `cli_language`), `tests/test_auth_store.py` (optional
  `cli_language` validation), `tests/test_text_sanitize.py` (`$` currency
  regression cases), anything touching changed signatures (`month_name`,
  `month_abbr`, `generate_rule_insights`, chart builders).
- Existing suite must pass after every phase.

## 7. Risks / constraints honored

- No new dependencies; stdlib only (gettext rejected — see §1).
- No `st.cache_data` keys gain `lang` (stats are language-neutral); spinner
  moves from decoration to call site.
- No custom CSS added; toggle is a native widget.
- `md_escape()` discipline unchanged.
- No `translate()` at import time.
- `key=` names unchanged across language switches (widget identity).
- `auth.json` gains one optional key (`cli_language`) — backward compatible
  with existing production files; web language lives in the DB, CLI language
  in `auth.json` — never shared state.
