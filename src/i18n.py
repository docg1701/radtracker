"""Translation catalog and lookups for the bilingual UX (EN native, PT-BR option).

One catalog serves both the Streamlit app (`t()`, reads st.session_state.lang)
and the SSH auth CLI (`translate()`, pure). Keys are namespaced `web.*` / `cli.*`.
"""

from typing import Any

import streamlit as st

LANGUAGES: tuple[str, ...] = ("en", "pt")
DEFAULT_LANG: str = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "web.tab.today": {"en": "Today", "pt": "Hoje"},
    "web.tab.month": {"en": "This Month", "pt": "Mês Atual"},
    "web.tab.analysis": {"en": "Analysis", "pt": "Análise"},
    "web.tab.chat": {"en": "AI Chat", "pt": "Chat IA"},
    "web.tab.settings": {"en": "Settings", "pt": "Configuração"},
    "web.nav.label": {"en": "Navigation", "pt": "Navegação"},
    "web.sidebar.greeting": {"en": "Hello, {name}.", "pt": "Olá, {name}."},
}


def translate(key: str, lang: str, **fmt: Any) -> str:
    """Return TRANSLATIONS[lang][key] formatted with fmt. KeyError = fail loud.

    Usage:
        >>> translate("web.tab.today", "pt")
        'Hoje'
    """
    text = TRANSLATIONS[key][lang]
    return text.format(**fmt) if fmt else text


def t(key: str, **fmt: Any) -> str:
    """Web wrapper: translate for st.session_state.lang (default 'en').

    Usage:
        >>> t("web.sidebar.greeting", name="Galvani")
        'Hello, Galvani.'
    """
    return translate(key, st.session_state.get("lang", DEFAULT_LANG), **fmt)
