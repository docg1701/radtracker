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
    "web.common.view_raw_data": {"en": "View raw data", "pt": "Ver dados brutos"},
    "web.tabs.no_modalities_bold": {
        "en": "No active modalities. Configure them in the **Settings** tab.",
        "pt": "Nenhuma modalidade ativa. Configure na aba **Configuração**.",
    },
    "web.tabs.no_modalities_plain": {
        "en": "No active modalities. Configure them in the Settings tab.",
        "pt": "Nenhuma modalidade ativa. Configure na aba Configuração.",
    },
    "web.today.start_hint": {
        "en": "Start by logging today's production in the **sidebar**.",
        "pt": "Comece registrando sua produção de hoje na **barra lateral**.",
    },
    "web.today.start_caption": {
        "en": "Data will appear here once you save.",
        "pt": "Os dados aparecerão aqui assim que você salvar.",
    },
    "web.today.overview": {"en": "Overview", "pt": "Visão geral"},
    "web.today.kpi.earnings": {"en": "Today's revenue", "pt": "Faturamento hoje"},
    "web.today.kpi.exams": {"en": "Today's exams", "pt": "Exames hoje"},
    "web.today.kpi.hours": {"en": "Estimated hours", "pt": "Horas estimadas"},
    "web.today.kpi.goal": {"en": "Monthly goal", "pt": "Meta mensal"},
    "web.today.kpi.vs_yesterday": {
        "en": "{delta} vs yesterday",
        "pt": "{delta} vs ontem",
    },
    "web.today.kpi.no_yesterday": {
        "en": "— no data from yesterday",
        "pt": "— sem dados de ontem",
    },
    "web.today.badge.on_pace": {"en": "On pace", "pt": "No ritmo"},
    "web.today.badge.watch": {"en": "Watch out", "pt": "Atenção"},
    "web.today.raw.revenue": {"en": "Revenue:", "pt": "Faturamento:"},
    "web.today.raw.hours": {"en": "Hours:", "pt": "Horas:"},
    "web.month.start_hint": {
        "en": "Start by logging your production in the **sidebar**.",
        "pt": "Comece registrando sua produção na **barra lateral**.",
    },
    "web.month.start_caption": {
        "en": "Monthly data will appear here.",
        "pt": "Os dados mensais aparecerão aqui.",
    },
    "web.month.kpi.mtd": {"en": "MTD revenue", "pt": "Faturamento MTD"},
    "web.month.kpi.projected": {"en": "{value} projected", "pt": "{value} projetado"},
    "web.month.kpi.goal_pct": {"en": "% of goal", "pt": "% da meta"},
    "web.month.kpi.days": {"en": "Days worked", "pt": "Dias trabalhados"},
    "web.month.kpi.days_value": {"en": "{worked} of {total}", "pt": "{worked} de {total}"},
    "web.month.kpi.remaining": {"en": "{count} left", "pt": "{count} restantes"},
    "web.month.kpi.daily_avg": {"en": "Daily average", "pt": "Média diária"},
    "web.month.kpi.target": {"en": "Target: {value}/day", "pt": "Alvo: {value}/dia"},
    "web.month.chart.daily": {"en": "Daily revenue", "pt": "Faturamento diário"},
    "web.month.chart.by_modality": {
        "en": "Revenue by Modality",
        "pt": "Receita por Modalidade",
    },
    "web.month.chart.no_daily": {
        "en": "No data for the daily chart.",
        "pt": "Sem dados para o gráfico diário.",
    },
    "web.month.day_one": {"en": "1 day", "pt": "1 dia"},
    "web.month.day_many": {"en": "{count} days", "pt": "{count} dias"},
    "web.month.goal_toast": {
        "en": "Monthly goal reached! Congratulations!",
        "pt": "Meta do mês atingida! Parabéns!",
    },
    "web.month.rhythm_alert": {
        "en": ":material/warning: **Pace warning**\n\n"
              "{name}, you are behind pace to hit the goal of {goal}.\n\n"
              "{missing} to go in {days} — you need **{needed}/day** from here on.\n\n"
              "Your current average: {avg}/day.",
        "pt": ":material/warning: **Atenção ao ritmo**\n\n"
              "{name}, você está atrás do ritmo para bater a meta "
              "de {goal}.\n\n"
              "Faltam {missing} em {days} — "
              "você precisa de **{needed}/dia** "
              "daqui pra frente.\n\n"
              "Sua média atual: {avg}/dia.",
    },
    "web.analysis.insights": {"en": "Insights", "pt": "Insights"},
    "web.analysis.insights_caption": {
        "en": "Automatic analysis based on your data",
        "pt": "Análise automática baseada nos seus dados",
    },
    "web.analysis.start_hint": {
        "en": "Log your production in the **sidebar**.",
        "pt": "Registre sua produção na **barra lateral**.",
    },
    "web.analysis.start_caption": {
        "en": "Historical analyses will appear here.",
        "pt": "As análises históricas aparecerão aqui.",
    },
    "web.analysis.moving_avg": {"en": "Moving averages", "pt": "Médias móveis"},
    "web.analysis.no_current_month": {
        "en": "No data for the current month.",
        "pt": "Nenhum dado no mês atual.",
    },
    "web.analysis.weekly": {"en": "Weekly comparison", "pt": "Comparação semanal"},
    "web.analysis.mix": {
        "en": "Modality mix evolution",
        "pt": "Evolução do mix de modalidades",
    },
    "web.analysis.mix_no_data": {
        "en": "Insufficient data for the mix evolution.",
        "pt": "Dados insuficientes para evolução do mix.",
    },
    "web.analysis.by_month": {"en": "Revenue by month", "pt": "Faturamento por mês"},
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
