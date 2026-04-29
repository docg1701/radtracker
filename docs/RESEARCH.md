# Relatório de Pesquisa — Telerrad Report

**Data**: 2026-04-29
**Objetivo**: Levantar documentação atualizada, preços, APIs e boas práticas para implementar o dashboard de produtividade de telerradiologia.

---

## 1. Resumo Executivo

O projeto é inteiramente viável com stack 100% Python open-source:

| Componente | Tecnologia | Status |
|---|---|---|
| Interface | Streamlit 1.54 | Documentação completa, maduro |
| Gráficos | Plotly Express / Graph Objects | Integração nativa com Streamlit |
| Cálculos | Pandas + NumPy | Série temporal, médias móveis, projeções |
| Banco | SQLite (built-in Python) | Zero configuração, arquivo único |
| LLM | Ollama Cloud (DeepSeek V4 Flash) | Plano Free suficiente, API Python |
| Tema | Streamlit config.toml | Customizável, suporte a light/dark |

---

## 2. Streamlit — Interface e Componentes

### 2.1 Versão atual: 1.54.0

Fonte: [Streamlit GitHub](https://github.com/streamlit/streamlit)
Instalação: `pip install streamlit`

### 2.2 Componentes principais que usaremos

#### Tabs (abas)
```python
tab1, tab2, tab3, tab4 = st.tabs(["📊 Hoje", "📅 Mês Atual", "📈 Análise", "⚙️ Config"])
with tab1:
    st.write("Conteúdo da aba Hoje")
```
Fonte: Context7 `/streamlit/streamlit`

#### Sidebar (entrada de dados)
```python
with st.sidebar:
    st.date_input("Data", value=date.today())
    rm = st.number_input("RM", min_value=0, step=1)
    tc = st.number_input("TC", min_value=0, step=1)
    rx = st.number_input("RX", min_value=0, step=1)
    if st.button("💾 Salvar"):
        save_daily(rm, tc, rx)
```

#### KPIs com st.metric
```python
col1, col2, col3 = st.columns(3)
col1.metric("💰 Faturamento Hoje", "R$ 1.250", "+12%")
col2.metric("📊 Meta Diária", "R$ 1.730", "-R$ 480", delta_color="inverse")
col3.metric("⏱️ Horas Estimadas", "5.2h")
```

#### Gráficos Plotly
```python
fig = px.line(df, x='date', y='earnings', title='Faturamento Diário')
st.plotly_chart(fig, use_container_width=True)
```

#### Progresso
```python
st.progress(41, text="R$ 18.450 / R$ 45.000 (41%)")
```

#### Cache de dados
```python
@st.cache_data(ttl=300)  # 5 minutos
def load_month_data(year_month: str) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM daily_production WHERE date LIKE ?", conn, params=[f"{year_month}%"])
```

#### Sessão (persistência entre reruns)
```python
if 'today_date' not in st.session_state:
    st.session_state.today_date = date.today()
if 'rm_count' not in st.session_state:
    st.session_state.rm_count = 0
```

#### Conexão SQLite nativa do Streamlit
```python
conn = st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")
df = conn.query("SELECT * FROM daily_production WHERE date = :date", params={"date": "2026-04-29"}, ttl=0)
```
Fonte: Context7 `/streamlit/streamlit` — `st.connection`

### 2.3 Tema customizado

Arquivo `.streamlit/config.toml`:
```toml
[theme]
base = "dark"
primaryColor = "#2196F3"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1E1E2E"
textColor = "#EAEAEA"
font = "sans serif"

[theme.light]
base = "light"
primaryColor = "#1565C0"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
```

Fonte: [Streamlit Theming Docs](https://docs.streamlit.io/develop/concepts/configuration/theming)

---

## 3. Plotly — Gráficos

### 3.1 Tipos de gráficos que usaremos

```python
import plotly.express as px
import plotly.graph_objects as go

# Linha — faturamento diário + linha de tendência
fig = px.line(df, x='date', y='earnings', title='Faturamento Diário')
fig.add_hline(y=daily_target, line_dash="dash", line_color="red",
              annotation_text="Meta diária")

# Barra — exames por dia
fig = px.bar(df, x='date', y=['rm_count', 'tc_count', 'rx_count'],
             title='Exames por modalidade', barmode='stack')

# Pizza — distribuição do mês
fig = px.pie(df_month, values='total_earnings', names='modality',
             title='Distribuição por Modalidade', hole=0.4)

# Área — média móvel 7d + 30d
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['date'], y=df['ma7'], name='Média 7d',
                         fill='tozeroy', line=dict(width=2)))
fig.add_trace(go.Scatter(x=df['date'], y=df['ma30'], name='Média 30d',
                         line=dict(width=2, dash='dash')))
st.plotly_chart(fig, use_container_width=True)
```

Fonte: [Plotly.py Docs](https://github.com/plotly/plotly.py)

---

## 4. Pandas — Cálculos e Séries Temporais

### 4.1 Operações essenciais

```python
import pandas as pd
import numpy as np

# Rolling (média móvel)
df['ma7'] = df['earnings'].rolling(window=7, min_periods=1).mean()
df['ma30'] = df['earnings'].rolling(window=30, min_periods=1).mean()

# Resample semanal
weekly = df.resample('W-MON', on='date')['earnings'].sum()

# Dias úteis (seg-sáb)
from pandas.tseries.offsets import CustomBusinessDay
work_days = CustomBusinessDay(weekmask='Mon Tue Wed Thu Fri Sat')

# Dias restantes no mês
from pandas.tseries.offsets import MonthEnd
today = pd.Timestamp.today()
month_end = today + MonthEnd(0)
remaining = len(pd.date_range(today, month_end, freq=work_days))

# Leitura do SQLite
df = pd.read_sql("SELECT * FROM daily_production", conn, parse_dates=['date'])
df.set_index('date', inplace=True)

# Projeção linear
from numpy.polynomial.polynomial import polyfit
x = np.arange(len(df))
y = df['earnings'].values
coefs = polyfit(x, y, 1)
projection = coefs[0] + coefs[1] * (len(df) + remaining_days)
```

Fonte: [Pandas Docs](https://pandas.pydata.org/docs/)

### 4.2 Business days customizados

```python
# Dias de trabalho: Segunda a Sábado
weekmask = 'Mon Tue Wed Thu Fri Sat'
holidays = []  # Pode adicionar feriados
bday_br = CustomBusinessDay(weekmask=weekmask, holidays=holidays)

# Dias úteis restantes no mês
today = pd.Timestamp.today().normalize()
month_end = today + pd.offsets.MonthEnd(0)
remaining_days = len(pd.date_range(start=today, end=month_end, freq=bday_br))
```

---

## 5. SQLite — Banco de Dados

### 5.1 Schema final (revisado)

```sql
CREATE TABLE IF NOT EXISTS daily_production (
    date        TEXT PRIMARY KEY,
    rm_count    INTEGER NOT NULL DEFAULT 0,
    tc_count    INTEGER NOT NULL DEFAULT 0,
    rx_count    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS exam_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rm_price    REAL NOT NULL,
    tc_price    REAL NOT NULL,
    rx_price    REAL NOT NULL,
    effective_from TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS monthly_goals (
    year_month  TEXT PRIMARY KEY,
    goal_reais  REAL NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

### 5.2 UPSERT (INSERT OR REPLACE) — crucial para entrada múltipla diária

```python
def upsert_daily(date_str: str, rm: int, tc: int, rx: int):
    conn.execute("""
        INSERT INTO daily_production (date, rm_count, tc_count, rx_count, updated_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(date) DO UPDATE SET
            rm_count = excluded.rm_count,
            tc_count = excluded.tc_count,
            rx_count = excluded.rx_count,
            updated_at = datetime('now','localtime')
    """, [date_str, rm, tc, rx])
    conn.commit()
```

### 5.3 Conexão via Streamlit (recomendado)

```python
# Em secrets.toml ou direto:
conn = st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")
```

Isso gerencia pool, fecha conexão automaticamente, e permite queries com cache.

---

## 6. Ollama Cloud — LLM para Insights

### 6.1 Planos e Preços

| Plano | Preço | Uso | Concorrência |
|---|---|---|---|
| Free | $0 | Leve (chat, avaliação) | 1 modelo |
| Pro | $20/mês | 50x mais que Free | 3 modelos |
| Max | $100/mês | 5x mais que Pro | 10 modelos |

Fonte: [Ollama Pricing](https://ollama.com/pricing)

> **Para o nosso uso**: O plano Free é suficiente. Vamos fazer ~10-50 chamadas/dia com prompts pequenos (~500-2000 tokens). O LLM é consultado apenas quando o usuário abre a aba "Análise" ou uma vez por hora.

### 6.2 Modelo: DeepSeek V4 Flash

- **Nome no Ollama**: `deepseek-v4-flash:cloud`
- **Parâmetros**: 284B total, 13B ativados (MoE)
- **Contexto**: 1M tokens
- **Modos**: Non-think, Thinking, Max Thinking
- **Preço OpenRouter**: $0.14/M input, $0.28/M output tokens
- **Preço Ollama Cloud**: Incluso no plano (não cobra por token separadamente no Free)

Fonte: [Ollama Library](https://ollama.com/library/deepseek-v4-flash:cloud), [OpenRouter](https://openrouter.ai/deepseek/deepseek-v4-flash)

### 6.3 API Python — código de integração

```python
# Instalação: pip install ollama

import os
from ollama import Client

client = Client(
    host="https://ollama.com",
    headers={'Authorization': f'Bearer {os.environ["OLLAMA_API_KEY"]}'}
)

def generate_insights(stats_json: str) -> str:
    """Envia estatísticas e recebe insights em português."""
    response = client.chat(
        model='deepseek-v4-flash:cloud',
        messages=[
            {
                'role': 'system',
                'content': (
                    'Você é um analista de produtividade para um médico radiologista '
                    'chamado Galvani. Analise os dados e forneça 3-5 insights acionáveis '
                    'em português, tom amigável e direto. Inclua comparações com períodos '
                    'anteriores e sugestões práticas de otimização do mix de exames (RM, TC, RX).'
                )
            },
            {
                'role': 'user',
                'content': f'Dados do período:\n{stats_json}'
            }
        ],
        options={'temperature': 0.3}  # Mais determinístico para análise
    )
    return response.message.content
```

### 6.4 Autenticação

1. Criar API key em: https://ollama.com/settings/keys
2. Guardar em `.env` (NUNCA commitado):
   ```
   OLLAMA_API_KEY=sk_xxxxxxxxxxxx
   ```
3. Carregar com `python-dotenv`:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

### 6.5 Prompt template para análise

```python
stats_prompt = f"""
=== META ===
Meta mensal: R$ {goal:,.2f}
Dias trabalhados: {days_worked} de {total_work_days}
Dias restantes: {remaining_days}

=== FATURAMENTO ===
Acumulado no mês: R$ {mtd:,.2f} ({pct_goal:.1f}% da meta)
Média diária: R$ {daily_avg:,.2f}
Projeção fim do mês: R$ {projection:,.2f}
Faltam: R$ {remaining_needed:,.2f} → R$ {daily_target:,.2f}/dia

=== TENDÊNCIAS ===
Média móvel 7 dias: R$ {ma7:,.2f}
Média móvel 30 dias: R$ {ma30:,.2f}
Variação vs semana anterior: {wow_change:+.1f}%

=== MIX DE EXAMES (este mês) ===
RM: {rm_pct:.0f}% | TC: {tc_pct:.0f}% | RX: {rx_pct:.0f}%
Total exames: RM={total_rm} TC={total_tc} RX={total_rx}

=== ÚLTIMOS 7 DIAS ===
{last_7_days_table}

Forneça insights sobre: ritmo vs meta, tendências, sugestão de mix,
comparação com períodos anteriores, e recomendações práticas.
"""
```

---

## 7. Estrutura do Projeto (Final)

```
telerrad-report/                    # ← renomear depois
├── .streamlit/
│   └── config.toml                 # Tema, cores, fonte
├── .env                            # OLLAMA_API_KEY (gitignored)
├── .env.example                    # Template sem segredos
├── .gitignore
├── requirements.txt
├── README.md
├── app.py                          # Streamlit entrypoint
├── src/
│   ├── __init__.py
│   ├── db.py                       # SQLite schema, conexão, CRUD
│   ├── calculations.py             # Projeções, médias, estimativas
│   ├── insights_rules.py           # Regras de insight (sem LLM)
│   ├── llm_client.py               # Cliente Ollama Cloud
│   ├── charts.py                   # Fábrica de gráficos Plotly
│   └── ui/
│       ├── __init__.py
│       ├── sidebar.py              # Entrada de dados
│       ├── today.py                # Aba "Hoje"
│       ├── month.py                # Aba "Mês Atual"
│       ├── analysis.py             # Aba "Análise & Insights"
│       └── settings.py             # Aba "Configurações"
├── data/                           # .gitkeep
│   └── telerrad.db                 # Banco SQLite (gitignored)
└── tests/
    ├── __init__.py
    ├── conftest.py                 # Fixtures: banco em memória
    ├── test_calculations.py
    ├── test_db.py
    └── test_insights.py
```

---

## 8. Dependências (requirements.txt)

```
streamlit>=1.54.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
ollama>=0.4.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

Todas são open-source (MIT, BSD, Apache 2.0).

---

## 9. Decisões Técnicas Importantes

### 9.1 Por que SQLite e não JSON?
- Queries temporais com SQL (`WHERE date BETWEEN`, `GROUP BY strftime('%Y-%m', date)`)
- UPSERT atômico (evita corrupção em entrada múltipla/dia)
- Backup é copiar 1 arquivo
- Pandas lê diretamente com `read_sql()`
- Streamlit tem `st.connection` nativo para SQLite

### 9.2 Por que Streamlit e não Flask/FastAPI + React?
- Zero HTML/CSS/JS — tudo Python
- Gráficos Plotly renderizam nativamente
- Recarregamento automático em dev
- Sidebar, tabs, columns são built-in
- Perfeito para dashboards de 1 usuário local

### 9.3 LLM: Ollama Cloud vs API direta da DeepSeek
- **Ollama Cloud**: Plano Free cobre uso leve, API Python simples, sem se preocupar com cobrança por token
- **DeepSeek API direta**: $0.14/M input + $0.28/M output. Para 100 análises/mês com ~1K tokens cada = ~$0.05/mês
- **Decisão**: Começar com Ollama Cloud Free. Se atingir limite, migrar para API direta (custo irrisório).

### 9.4 Tratamento de erros do LLM
- Se `OLLAMA_API_KEY` não estiver configurado → fallback para insights baseados em regras
- Se API falhar (timeout, rate limit) → mostra mensagem amigável + insights por regras
- O LLM é um "plus", não uma dependência crítica

---

## 10. Ambiente Atual (Galvani)

| Item | Status |
|---|---|
| Python | 3.12.3 ✅ |
| Streamlit | Não instalado (pip install) |
| Plotly | Não instalado |
| Pandas | Não instalado |
| Ollama | Não instalado (pip install ollama) |
| .streamlit/config.toml | Não existe (criar) |
| Ollama API Key | A criar em ollama.com/settings/keys |

---

## 11. Estimativa de Tokens e Custos do LLM

Cenário de uso típico:
- 1 análise ao abrir a aba "Insights" (~2-3x/dia)
- Prompt: ~1200 tokens (dados estruturados)
- Resposta: ~400 tokens (3-5 insights)

| Plano | Custo mensal estimado |
|---|---|
| Ollama Cloud Free | $0 (se dentro do limite) |
| Ollama Cloud Pro | $20/mês (se Free não bastar) |
| DeepSeek API direta | ~$0.05-0.20/mês |

**Recomendação**: Começar com Free. Migrar para API direta da DeepSeek se necessário (mais barato que Pro).

---

## 12. Próximos Passos

1. ✅ Pesquisa concluída
2. ⬜ Definir nome do projeto
3. ⬜ Criar repositório GitHub privado
4. ⬜ Instalar dependências
5. ⬜ Implementar Fase 1: db.py + app.py com sidebar
6. ⬜ Fase 2: Aba "Hoje"
7. ⬜ Fase 3: Aba "Mês Atual"
8. ⬜ Fase 4: Aba "Análise"
9. ⬜ Fase 5: LLM + Configurações
10. ⬜ Testes e polimento

---

## Fontes

1. [Streamlit Documentation](https://docs.streamlit.io/) — Context7 `/streamlit/streamlit` v1.54.0
2. [Plotly Python Docs](https://plotly.com/python/) — Context7 `/plotly/plotly.py`
3. [Pandas Documentation](https://pandas.pydata.org/docs/) — Context7 `/pandas-dev/pandas`
4. [Ollama Cloud Docs](https://docs.ollama.com/cloud) — Autenticação e API
5. [Ollama Pricing](https://ollama.com/pricing) — Planos Free/Pro/Max
6. [DeepSeek V4 Flash on Ollama](https://ollama.com/library/deepseek-v4-flash:cloud) — Modelo Cloud
7. [OpenRouter DeepSeek V4 Flash](https://openrouter.ai/deepseek/deepseek-v4-flash) — Preços por token
8. [Streamlit Theming](https://docs.streamlit.io/develop/concepts/configuration/theming) — Configuração de temas
