"""Translation catalog and lookups for the bilingual UX (EN native, PT-BR option).

One catalog serves both the Streamlit app (`t()`, reads st.session_state.lang)
and the SSH auth CLI (`translate()`, pure). Keys are namespaced `web.*` / `cli.*`.
"""

from typing import Any

import streamlit as st

LANGUAGES: tuple[str, ...] = ("en", "pt")
DEFAULT_LANG: str = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "web.lang.label": {"en": "Language", "pt": "Idioma"},
    "web.tab.today": {"en": "Today", "pt": "Hoje"},
    "web.tab.month": {"en": "This Month", "pt": "Mês Atual"},
    "web.tab.analysis": {"en": "Analysis", "pt": "Análise"},
    "web.tab.chat": {"en": "AI Chat", "pt": "Chat IA"},
    "web.tab.settings": {"en": "Settings", "pt": "Configuração"},
    "web.nav.label": {"en": "Navigation", "pt": "Navegação"},
    "web.auth.unavailable": {
        "en": "Authentication unavailable on this server. Contact the administrator.",
        "pt": "Autenticação indisponível neste servidor. Contate o administrador.",
    },
    "web.auth.username": {"en": "Username", "pt": "Usuário"},
    "web.auth.password": {"en": "Password", "pt": "Senha"},
    "web.auth.login": {"en": "Log in", "pt": "Entrar"},
    "web.auth.invalid_credentials": {
        "en": "Invalid username or password.",
        "pt": "Usuário ou senha inválidos.",
    },
    "web.auth.totp_title": {
        "en": "Two-step verification",
        "pt": "Verificação em duas etapas",
    },
    "web.auth.totp_code": {"en": "Authenticator code", "pt": "Código do autenticador"},
    "web.auth.totp_verify": {"en": "Verify", "pt": "Verificar"},
    "web.auth.totp_invalid": {
        "en": "Invalid or expired code.",
        "pt": "Código inválido ou expirado.",
    },
    "web.auth.logout": {"en": "Log out", "pt": "Sair"},
    "web.footer.two_fa_on": {"en": "2FA enabled.", "pt": "2FA ativado."},
    "web.footer.two_fa_off": {"en": "2FA disabled.", "pt": "2FA desativado."},
    "web.sidebar.greeting": {"en": "Hello, {name}.", "pt": "Olá, {name}."},
    "web.sidebar.date_label": {"en": "Date:", "pt": "Data:"},
    "web.sidebar.no_modalities": {
        "en": "No active modalities. Configure prices and productivity in the "
              "**:material/settings: Settings** tab.",
        "pt": "Nenhuma modalidade ativa. Configure os preços e a "
              "produtividade na aba **:material/settings: Configuração**.",
    },
    "web.sidebar.save": {"en": "Save", "pt": "Salvar"},
    "web.sidebar.saving": {"en": "Saving...", "pt": "Salvando..."},
    "web.sidebar.saved_toast": {
        "en": "Production for {date} saved!",
        "pt": "Produção de {date} salva!",
    },
    "web.empty.default_title": {"en": "No records yet", "pt": "Nenhum registro ainda"},
    "web.common.loading_history": {
        "en": "Analyzing historical data...",
        "pt": "Analisando dados históricos...",
    },
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
