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
    "web.settings.section.modalities": {"en": "Modalities", "pt": "Modalidades"},
    "web.settings.modalities.caption": {
        "en": "Configure name, price ($) and productivity (exams/hour) for each "
              "modality. Check **Active** to show it in the sidebar. "
              "Modalities without price or productivity do not appear on the dashboard.",
        "pt": "Configure nome, preço ($) e produtividade (exames/hora) de cada "
              "modalidade. Marque **Ativo** para que apareça na barra lateral. "
              "Modalidades sem preço ou produtividade não aparecem no dashboard.",
    },
    "web.settings.grid.modality": {"en": "Modality", "pt": "Modalidade"},
    "web.settings.grid.price": {"en": "Price ($)", "pt": "Preço ($)"},
    "web.settings.grid.exams_h": {"en": "Exams/h", "pt": "Exames/h"},
    "web.settings.grid.color": {"en": "Color", "pt": "Cor"},
    "web.settings.grid.active": {"en": "Active", "pt": "Ativo"},
    "web.settings.grid.name_a11y": {"en": "Name {slug}", "pt": "Nome {slug}"},
    "web.settings.grid.price_a11y": {"en": "Price {slug}", "pt": "Preço {slug}"},
    "web.settings.grid.eph_a11y": {"en": "Exams/h {slug}", "pt": "Exames/h {slug}"},
    "web.settings.grid.color_a11y": {"en": "Color {slug}", "pt": "Cor {slug}"},
    "web.settings.grid.active_a11y": {"en": "Active {slug}", "pt": "Ativo {slug}"},
    "web.settings.grid.delete_help": {
        "en": "Deactivate {label}",
        "pt": "Desativar {label}",
    },
    "web.settings.grid.confirm_deactivate": {
        "en": "Deactivate **{label}**? Production history is preserved "
              "(the modality becomes inactive and can be reactivated by "
              "adding it again).",
        "pt": "Desativar **{label}**? A produção histórica é preservada "
              "(a modalidade fica inativa e pode ser reativada ao "
              "adicioná-la de novo).",
    },
    "web.settings.grid.deactivate": {"en": "Deactivate", "pt": "Desativar"},
    "web.settings.grid.cancel": {"en": "Cancel", "pt": "Cancelar"},
    "web.settings.grid.save": {"en": "Save modalities", "pt": "Salvar modalidades"},
    "web.settings.grid.no_changes": {
        "en": "No pending changes.",
        "pt": "Nenhuma alteração pendente.",
    },
    "web.settings.grid.add": {"en": "Add modality", "pt": "Adicionar modalidade"},
    "web.settings.grid.new_name": {
        "en": "New modality name",
        "pt": "Nome da nova modalidade",
    },
    "web.settings.grid.new_name_ph": {
        "en": "E.g. Brain CT",
        "pt": "Ex: Tomografia de Crânio",
    },
    "web.settings.grid.slug": {"en": "Slug: {slug}", "pt": "Slug: {slug}"},
    "web.settings.grid.added_toast": {
        "en": "{label} added!",
        "pt": "{label} adicionada!",
    },
    "web.settings.grid.slug_exists": {
        "en": "Slug '{slug}' already exists. Choose another name.",
        "pt": "Slug '{slug}' já existe. Escolha outro nome.",
    },
    "web.settings.grid.saved_toast": {
        "en": "Modalities saved! Sidebar updated.",
        "pt": "Modalidades salvas! Barra lateral atualizada.",
    },
    "web.settings.section.personal": {"en": "Personalization", "pt": "Personalização"},
    "web.settings.personal.name": {"en": "Your name", "pt": "Seu nome"},
    "web.settings.personal.goal": {
        "en": "Monthly goal ($)",
        "pt": "Meta mensal ($)",
    },
    "web.settings.section.ai": {
        "en": "Artificial Intelligence",
        "pt": "Inteligência Artificial",
    },
    "web.settings.ai.api_key": {
        "en": "OpenRouter API key",
        "pt": "Chave API OpenRouter",
    },
    "web.settings.ai.model": {
        "en": "OpenRouter model (full slug)",
        "pt": "Modelo OpenRouter (slug completo)",
    },
    "web.settings.ai.invalid_slug": {
        "en": "Invalid slug: use the provider/model format "
              "(e.g. openai/gpt-oss-120b:free).",
        "pt": "Slug inválido: use o formato provedor/modelo "
              "(ex: openai/gpt-oss-120b:free).",
    },
    "web.settings.ai.thinking": {
        "en": "Enable thinking mode",
        "pt": "Ativar thinking mode",
    },
    "web.settings.ai.thinking_help": {
        "en": "Model generates internal reasoning before answering. "
              "Higher analytical quality, higher token cost.",
        "pt": "Modelo gera raciocínio interno antes da resposta. "
              "Mais qualidade analítica, maior custo de tokens.",
    },
    "web.settings.ai.mode_effort": {
        "en": "Thinking effort",
        "pt": "Esforço de pensamento",
    },
    "web.settings.ai.mode_budget": {
        "en": "Token budget",
        "pt": "Orçamento de tokens",
    },
    "web.settings.ai.effort": {
        "en": "Effort level",
        "pt": "Nível de esforço",
    },
    "web.settings.ai.effort_help": {
        "en": "Controls how many tokens the model spends thinking. "
              "xhigh = deeper analysis. OpenRouter translates it to each "
              "model's native format.",
        "pt": "Controla quantos tokens o modelo gasta pensando. "
              "xhigh = análise mais profunda. "
              "O OpenRouter traduz para o formato nativo de cada modelo.",
    },
    "web.settings.ai.budget": {
        "en": "Reasoning tokens",
        "pt": "Tokens de reasoning",
    },
    "web.settings.ai.budget_help": {
        "en": "Sets exactly how many tokens the model may spend reasoning. "
              "OpenRouter translates it to each model's native format.",
        "pt": "Define exatamente quantos tokens o modelo pode gastar "
              "em raciocínio. O OpenRouter traduz para o formato "
              "nativo de cada modelo.",
    },
    "web.settings.ai.temperature": {"en": "Temperature", "pt": "Temperatura"},
    "web.settings.ai.temperature_help": {
        "en": "Controls randomness (0 = deterministic, 2 = creative). "
              "Some models ignore it when thinking is on. "
              "Recommended: 0.3 for analysis.",
        "pt": "Controla aleatoriedade (0 = determinístico, 2 = criativo). "
              "Alguns modelos ignoram com thinking ligado. "
              "Recomendado: 0.3 para análises.",
    },
    "web.settings.ai.prompt": {"en": "System prompt", "pt": "Prompt inicial"},
    "web.settings.ai.prompt_hint": {
        "en": "Use {user_name} as a placeholder for the user name.",
        "pt": "Use {user_name} como placeholder para o nome do usuário.",
    },
    "web.settings.ai.save": {"en": "Save settings", "pt": "Salvar configurações"},
    "web.settings.ai.err.name": {
        "en": "User name is required.",
        "pt": "Nome do usuário é obrigatório.",
    },
    "web.settings.ai.err.goal": {
        "en": "Monthly goal must be greater than zero.",
        "pt": "Meta mensal deve ser maior que zero.",
    },
    "web.settings.ai.err.api_key": {
        "en": "OpenRouter API key is required.",
        "pt": "Chave API OpenRouter é obrigatória.",
    },
    "web.settings.ai.err.prompt": {
        "en": "System prompt is required.",
        "pt": "Prompt inicial é obrigatório.",
    },
    "web.settings.ai.err.model": {
        "en": "LLM model is required.",
        "pt": "Modelo LLM é obrigatório.",
    },
    "web.settings.ai.err.model_slug": {
        "en": "Invalid LLM model slug (format: provider/model).",
        "pt": "Slug do modelo LLM inválido (formato: provedor/modelo).",
    },
    "web.settings.ai.saved_toast": {
        "en": "Settings saved!",
        "pt": "Configurações salvas!",
    },
    "web.settings.danger.title": {"en": "Danger zone", "pt": "Zona de perigo"},
    "web.settings.danger.clear": {
        "en": "Clear all data",
        "pt": "Limpar todos os dados",
    },
    "web.settings.danger.confirm": {
        "en": "Are you sure? **This action cannot be undone.** "
              "All production data and settings will be removed.",
        "pt": "Tem certeza? **Esta ação não pode ser desfeita.** "
              "Todos os dados de produção e configurações serão removidos.",
    },
    "web.settings.danger.yes": {
        "en": "Yes, clear everything",
        "pt": "Sim, limpar tudo",
    },
    "web.settings.danger.cleared_toast": {
        "en": "All data was removed.",
        "pt": "Todos os dados foram removidos.",
    },
    "web.chat.need_api_key": {
        "en": "Configure your **OpenRouter API key** in the "
              ":material/settings: **Settings** tab to enable the AI chat.",
        "pt": "Configure sua **chave API OpenRouter** na aba "
              ":material/settings: **Configuração** para ativar "
              "o chat com inteligência artificial.",
    },
    "web.chat.need_modalities": {
        "en": "No active modalities. Configure them in the "
              ":material/settings: **Settings** tab.",
        "pt": "Nenhuma modalidade ativa. Configure na aba "
              ":material/settings: **Configuração**.",
    },
    "web.chat.need_name": {
        "en": "Configure your **name** in the "
              ":material/settings: **Settings** tab.",
        "pt": "Configure seu **nome** na aba "
              ":material/settings: **Configuração**.",
    },
    "web.chat.need_goal": {
        "en": "Configure the **monthly goal** in the "
              ":material/settings: **Settings** tab.",
        "pt": "Configure a **meta mensal** na aba "
              ":material/settings: **Configuração**.",
    },
    "web.chat.need_prompt": {
        "en": "Configure the **AI prompt** in the "
              ":material/settings: **Settings** tab.",
        "pt": "Configure o **prompt da IA** na aba "
              ":material/settings: **Configuração**.",
    },
    "web.chat.get_key": {
        "en": "[Get a free key from OpenRouter](https://openrouter.ai/keys)",
        "pt": "[Obter chave gratuita no OpenRouter](https://openrouter.ai/keys)",
    },
    "web.chat.intro": {
        "en": "The assistant analyzes your production data and answers "
              "questions in English.",
        "pt": "O assistente analisa seus dados de produção "
              "e responde perguntas em português.",
    },
    "web.chat.start": {"en": "Start analysis", "pt": "Iniciar análise"},
    "web.chat.input_ph": {
        "en": "Ask something about your data...",
        "pt": "Pergunte algo sobre seus dados...",
    },
    "web.chat.suggestions_label": {
        "en": "Suggested questions:",
        "pt": "Sugestões de perguntas:",
    },
    "web.chat.sugg.q1": {
        "en": "What was the most productive day?",
        "pt": "Qual dia foi mais produtivo?",
    },
    "web.chat.sugg.q2": {
        "en": "Is my average consistent?",
        "pt": "Minha média é consistente?",
    },
    "web.chat.sugg.q3": {
        "en": "How is the modality mix looking?",
        "pt": "Como está o mix de modalidades?",
    },
    "web.chat.sugg.q4": {
        "en": "What is the projection to close the month?",
        "pt": "Qual a projeção para fechar o mês?",
    },
    "web.chat.sugg.q5": {
        "en": "Compare this week with the previous one",
        "pt": "Compare esta semana com a anterior",
    },
    "web.chat.new": {"en": "New chat", "pt": "Novo chat"},
    "web.chat.initial_report": {
        "en": "Generate a complete report of my productivity.",
        "pt": "Gere um relatório completo da minha produtividade.",
    },
    "web.chat.error.unavailable": {
        "en": "Could not generate a response. "
              "Check your connection or API key.",
        "pt": "Não foi possível gerar a resposta. "
              "Verifique sua conexão ou chave de API.",
    },
    "web.chat.error.unexpected": {
        "en": "Unexpected error generating the response. Details: {detail}",
        "pt": "Erro inesperado ao gerar a resposta. Detalhes: {detail}",
    },
    "web.charts.modality_bar_title": {
        "en": "Distribution by Modality",
        "pt": "Distribuição por Modalidade",
    },
    "web.charts.modality_bar_hover": {
        "en": "%{y}: %{x} exams<extra></extra>",
        "pt": "%{y}: %{x} exames<extra></extra>",
    },
    "web.charts.sparkline_title": {
        "en": "Revenue — Last 7 Days",
        "pt": "Faturamento — Últimos 7 Dias",
    },
    "web.charts.gauge_title": {
        "en": "Monthly Goal Progress",
        "pt": "Progresso da Meta Mensal",
    },
    "web.charts.gauge_remaining": {"en": "remaining", "pt": "restante"},
    "web.charts.monthly_revenue": {"en": "Revenue", "pt": "Faturamento"},
    "web.charts.monthly_target": {"en": "Daily target", "pt": "Alvo diário"},
    "web.charts.monthly_hover_day": {
        "en": "Day %{x}: $ %{y:,.2f}<extra></extra>",
        "pt": "Dia %{x}: $ %{y:,.2f}<extra></extra>",
    },
    "web.charts.monthly_hover_target": {
        "en": "Target: $ %{y:,.2f}<extra></extra>",
        "pt": "Alvo: $ %{y:,.2f}<extra></extra>",
    },
    "web.charts.today_annotation": {"en": "Today", "pt": "Hoje"},
    "web.charts.donut_fallback": {"en": "Month", "pt": "Mês"},
    "web.charts.ma7_hover": {
        "en": "MA7 day %{x}: $ %{y:,.2f}<extra></extra>",
        "pt": "MA7 dia %{x}: $ %{y:,.2f}<extra></extra>",
    },
    "web.charts.ma30_hover": {
        "en": "MA30 day %{x}: $ %{y:,.2f}<extra></extra>",
        "pt": "MA30 dia %{x}: $ %{y:,.2f}<extra></extra>",
    },
    "web.charts.wow_last_week": {
        "en": "Last week ({label})",
        "pt": "Semana passada ({label})",
    },
    "web.charts.wow_this_week": {
        "en": "This week ({label})",
        "pt": "Esta semana ({label})",
    },
    "web.charts.wow_extra_last": {"en": "Last week", "pt": "Semana passada"},
    "web.charts.wow_extra_this": {"en": "This week", "pt": "Esta semana"},
    "web.charts.ytd_goal": {"en": "Goal: $", "pt": "Meta: $"},
    "web.insights.no_data": {
        "en": "No records yet. Log your production in the **sidebar** "
              "and come back once you have a few days of work.",
        "pt": "Nenhum registro ainda. Registre sua produção na **barra lateral** "
              "e volte quando tiver alguns dias de trabalho.",
    },
    "web.insights.above": {"en": "above", "pt": "acima"},
    "web.insights.below": {"en": "below", "pt": "abaixo"},
    "web.insights.day_one_remaining": {
        "en": "1 day remaining",
        "pt": "1 dia restante",
    },
    "web.insights.day_many_remaining": {
        "en": "{count} days remaining",
        "pt": "{count} dias restantes",
    },
    "web.insights.status_beat_closed": {
        "en": "**Goal reached** — {mtd} of {goal} ({pct}%).",
        "pt": "**Meta batida** — {mtd} de {goal} ({pct}%).",
    },
    "web.insights.status_closed_under": {
        "en": "The month closed at {mtd} — {pct}% of the {goal} goal ({gap}).",
        "pt": "O mês fechou em {mtd} — {pct}% da meta de {goal} ({gap}).",
    },
    "web.insights.status_beat_remaining": {
        "en": "**Goal reached** — {mtd} of {goal} ({pct}%), with {days} ahead.",
        "pt": "**Meta batida** — {mtd} de {goal} ({pct}%), com {days} pela frente.",
    },
    "web.insights.status_current": {
        "en": "Revenue is currently at **{mtd}** — {pct}% of the {goal} goal. "
              "{missing} to go.",
        "pt": "Hoje o faturamento está em **{mtd}** — {pct}% da meta "
              "de {goal}. Faltam {missing}.",
    },
    "web.insights.mom_compare": {
        "en": "That is {pct}% {word} the same point of {month} ({value}).",
        "pt": "Isso é {pct}% {word} do mesmo ponto de {month} ({value}).",
    },
    "web.insights.projection": {
        "en": "At the current pace, the month closes at ~{proj}{note} — "
              "{gap} the goal.",
        "pt": "No ritmo atual, o mês fecha em ~{proj}{note} — "
              "{gap} da meta.",
    },
    "web.insights.projection_note": {
        "en": " (preliminary projection, few days)",
        "pt": " (projeção preliminar, poucos dias)",
    },
    "web.insights.needed": {
        "en": "To hit the goal, {missing} to go in {days}: "
              "{needed}/day from here to the end.",
        "pt": "Para bater a meta, faltam {missing} em {days}: "
              "{needed}/dia daqui ao fim.",
    },
    "web.llm.answer_instruction": {
        "en": "Answer in American English.",
        "pt": "Responda em português brasileiro.",
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
