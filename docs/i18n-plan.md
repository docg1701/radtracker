# Bilingual UX Plan — PT-BR ↔ EN-US toggle

Status: approved design, pending implementation. Delete this file after implementation;
fold the durable bits (i18n architecture) into `docs/context.md` + `docs/meta-prompt.md`.

## 1. Research findings (find-docs / ctx7)

- **Streamlit has no native i18n API.** Official docs return nothing for
  internationalization/localization queries — there is no translation
  mechanism, no locale setting, no `lang` option.
- **Python industry standard is stdlib `gettext`.** Its *global* API
  (`gettext.install`, builtins `_()`) is process-wide — unsafe in Streamlit,
  where one server process serves all browser sessions concurrently
  (language would leak across sessions). The *class-based* API is per-instance
  but requires `.po`/`.mo` toolchain (`msgfmt`), file I/O, and locale plumbing.
- **Community practice for 2 fixed languages in Streamlit:** a typed dict
  catalog + a `t(key)` helper reading a session-state language — the gettext
  `_()` pattern without the toolchain.

**Decision:** dict catalog in `src/i18n.py` + `t()`. Not gettext: two fixed
languages, one developer, no translator teams, no plural engine needed, and
`.po` tooling buys nothing here. Stdlib-only (no new dependencies — hard
constraint).

## 2. Design

### 2.1 Translation catalog — `src/i18n.py` (new)

```python
LANGUAGES = ("pt", "en")
TRANSLATIONS: dict[str, dict[str, str]] = {
    "kpi.earnings_today": {
        "pt": "Faturamento hoje",
        "en": "Today's revenue",
    },
    ...
}

def t(key: str, **fmt) -> str:
    """Return the string for st.session_state.lang (default 'pt')."""
    lang = st.session_state.get("lang", "pt")
    text = TRANSLATIONS[lang][key]      # KeyError = fail loud
    return text.format(**fmt) if fmt else text
```

- Keys: stable ASCII snake_case ids. PT values = **current strings verbatim**
  → zero visual change in PT mode (the default).
- Missing key = `KeyError` (fail loud, per project philosophy).
- Call sites apply `md_escape()` exactly as today (only on `R$` strings).
- **No `t()` in module-level defaults** (empty-state default args, decorated
  cache params, `_SUGGESTIONS`) — evaluated at import, before session state
  exists. Resolve language inside functions.

### 2.2 Language state + toggle

- `st.session_state.lang`, default `"pt"`.
- Toggle: `st.segmented_control` (Streamlit ≥1.38; project is ≥1.54) in the
  **sidebar, above everything**, options `["Português", "English"]`, label
  `:material/translate:` + `t("lang.label")`, `key="lang_selector"` with
  `on_change` that sets `st.session_state.lang` from the widget value.
- **Rendered in `app.py` immediately after `set_page_config`** — before the
  auth gate. The gate calls `st.stop()` when unauthenticated, so anything
  rendered after it never appears on the login screen. The login screen must
  be bilingual too.
- Persistence: `user_settings` row `language` (`pt`/`en`).
  - Load: in `ensure_settings`, only when `"lang" not in st.session_state`
    (a pre-login toggle must not be clobbered after login).
  - Save: toggle `on_change` writes to DB via `save_setting(get_connection(),
    "language", lang)` only when `auth_authenticated` (DB isn't booted
    pre-login; `get_connection()` opens it on demand — same pattern as
    `_delete_all_data` in settings.py).
- No cookie work: DB persistence reuses existing infra; the CCv2 cookie
  machinery stays untouched.
- Tab radio (`key="main_tabs"`) stores selection by index — language switch
  keeps the tab, labels re-render translated. No change needed.

### 2.3 Dates (decision: MM/DD/YYYY in EN)

- `src/formatting.py`: `MONTHS` becomes per-language (`months_en`, keep
  `MONTHS_PT` name for compatibility or one dict of dicts); `month_abbr()`,
  `month_name()` gain a `lang` param (default `"pt"` — chart tests unchanged).
- `sidebar.py`: date_input `format="MM/DD/YYYY"` in EN; toast date
  `strftime("%m/%d")` in EN.
- Chart x-axes use day numbers / ISO strings — locale-neutral, no change.

### 2.4 Currency (decision: R$ stays, US number notation in EN)

- Keep `fmt_brl()` as the PT canonical formatter (untouched, tests green).
- Add `fmt_money(value, lang) -> str` in `src/formatting.py`:
  - `pt` → `fmt_brl()` (`R$ 1.250,00`)
  - `en` → same HALF_UP quantization, US separators (`R$ 1,250.00`), same
    nan/inf/negative handling (shared helper, no duplication).
- Currency symbol stays `R$` in both languages — the data is Brazilian reais;
  only the number notation changes.
- All UI call sites switch `fmt_brl(...)` → `fmt_money(..., lang)`.
- Pre-existing note (out of scope): Plotly hovertemplates already use
  d3 US format (`R$ %{y:,.2f}`) in both modes today; not made worse, aligned
  later if it ever matters.

### 2.5 LLM / insights language (decision: follows the UI)

- `src/llm_client.py`: RAG context template (`build_rag_context`) becomes
  per-language (current PT text → i18n keys with `{placeholders}`); weekday
  names per language; user-visible `LLMUnavailableError`/error strings → `t()`.
- Custom user prompts (stored in DB, PT by default): in EN mode, append one
  instruction line to the effective system prompt —
  `t("llm.answer_language_en")` ("Answer in American English.") — instead of
  rewriting the user's stored prompt. PT mode appends nothing.
- `src/insights_rules.py`: `generate_rule_insights(stats)` →
  `generate_rule_insights(stats, lang)`. Rewrite narrative sentences as `t()`
  templates with placeholders; plurals via explicit plural keys
  (`insights.day_remaining.one/many`).
- `src/ui/chat.py`: `_SUGGESTIONS` per language (they become user messages);
  initial-report trigger message and empty-state copy → `t()`.

## 3. Conversion inventory (by file, ~190 keys)

| File | Scope |
|------|-------|
| `src/i18n.py` | **new** — catalog + `t()` |
| `src/formatting.py` | month names/abbr per lang, `fmt_money()` |
| `src/ui/common.py` | empty-state default title (None → resolve inside), cache spinner (drop `show_spinner=` at decoration; wrap call site in `st.spinner(t(...))`) |
| `app.py` | 5 tab labels, auth-config error, navigation label |
| `src/ui/login.py` | login/TOTP forms, errors, footer captions (2FA), Sair |
| `src/ui/sidebar.py` | greeting, Data label, empty-modality info, Salvar/Salvando/toast |
| `src/ui/today.py` | 4 KPI cards, deltas, badges, empty states, Visão geral, raw data expander + lines |
| `src/ui/month.py` | KPI row, rhythm alert (multi-sentence), celebration toast, empty states, raw data expander, "projetado"/"restantes"/"Alvo: X/dia" |
| `src/ui/analysis.py` | expander label, 4 subheaders, captions, empty states, insufficient-data info |
| `src/ui/chat.py` | empty states, suggestions, buttons, streaming status/errors, initial report |
| `src/ui/settings.py` | largest file: grid headers/captions/buttons/toasts/warnings, AI section labels + `help=` texts, thinking radio format_func, validation errors, danger zone |
| `src/charts.py` | 3 titles, legend names, hovertemplates ("Dia"/"Alvo"), "Hoje" annotation, gauge label, month title → `month_name(lang)` |
| `src/charts_analysis.py` | legend names (1–2 strings) |
| `src/insights_rules.py` | full narrative rewrite → lang param |
| `src/llm_client.py` | RAG context templates, weekdays, error strings, appended answer-language instruction |

Chart builders are pure functions — add a `lang: str = "pt"` param (default
keeps existing tests untouched); UI passes the active language.

**Not translated:** DB-stored modality labels (user-editable data, not chrome),
auth CLI (`scripts/manage_auth.py`, SSH-side), log output.

## 4. Phases

**Phase 0 — Foundation:** `src/i18n.py` + `tests/test_i18n.py`:
- pt/en key parity (same key set in both languages),
- `t()` respects `st.session_state.lang`, missing key raises,
- `fmt_money()` both notations + nan/inf/negative parity with `fmt_brl`,
- `month_name`/`month_abbr` per language.

**Phase 1 — Toggle + gate:** toggle in `app.py` (pre-gate), session state +
DB persistence, convert `app.py`, `login.py`, `sidebar.py`, `common.py`.
Login screen and sidebar fully bilingual.

**Phase 2 — Core tabs:** `today.py`, `month.py`, `analysis.py`.

**Phase 3 — Settings + Chat:** `settings.py`, `chat.py`.

**Phase 4 — Data-driven text:** `formatting.py` (dates/currency call sites),
`charts.py`, `charts_analysis.py`, `insights_rules.py`, `llm_client.py`.

**Phase 5 — Audit & gate:**
- `grep` sweep for remaining PT literals in `src/ui/`, `app.py`, chart titles
  (accents + known phrases).
- Manual pass: login screen, all 5 tabs, charts, toasts — in both languages,
  toggling mid-session (widget keys must survive the switch).
- Full quality gate (AGENTS.md): pytest, ruff, mypy, hadolint, yamllint,
  actionlint, markdownlint.

## 5. Tests

- New: `tests/test_i18n.py` (parity, lookup, fail-loud, `fmt_money`,
  per-language months, EN insight narrative spot-checks, EN RAG context
  contains answer-language instruction).
- Updated: any test touching changed signatures (`month_name`, `month_abbr`,
  `generate_rule_insights`, chart builders with `lang`) — default args keep
  most green.
- Existing 292+ tests must pass after every phase.

## 6. Risks / constraints honored

- No new dependencies; stdlib only (gettext rejected — see §1).
- No `st.cache_data` keys gain `lang` (stats are language-neutral); only the
  spinner moves from decoration to call site.
- No custom CSS added; toggle is a native widget.
- `md_escape()` discipline unchanged (EN strings still contain `R$`).
- No t() at import time (module-level defaults).
- `key=` names unchanged across language switches (widget identity).
