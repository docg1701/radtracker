# radtracker

Dashboard pessoal de produtividade para telerradiologia.
Acompanhe faturamento, metas e tendências com Streamlit + SQLite.

## Funcionalidades

- 📅 **Hoje**: KPI cards, distribuição por modalidade, sparkline de 7 dias
- 📆 **Mês Atual**: progresso da meta, faturamento diário, alertas de ritmo
- 📈 **Análise**: médias móveis (MA7/MA30), comparação semanal, evolução do mix
- 🤖 **Insights IA**: GPT-OSS 120B via OpenRouter (fallback para regras se offline)
- ⚙️ **Config**: preços por exame, meta mensal, seu nome, chave API, prompt da IA

## Pré-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)

## Instalação

```bash
git clone https://github.com/docg1701/radtracker.git
cd radtracker
uv sync                       # instala todas as dependências
```

## Uso

```bash
uv run streamlit run app.py   # http://localhost:8501
```

## IA (OpenRouter)

Para insights gerados por IA:

1. Crie uma conta gratuita em https://openrouter.ai
2. Gere uma API key
3. Na aba **Config**, cole sua chave no campo "Chave API OpenRouter"
4. Opcionalmente, personalize o nome e o prompt da IA na mesma aba
5. Na aba "Análise", clique em "Perguntar à IA"
6. Sem chave, o fallback baseado em regras é usado automaticamente

A chave é salva localmente no banco SQLite — sem arquivos `.env`.

## Executando os testes

```bash
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

## Estrutura do projeto

```
radtracker/
├── app.py                  # Entry point Streamlit
├── src/
│   ├── db.py               # SQLite schema + CRUD (4 tables)
│   ├── calculations.py     # Business logic (earnings, MA, projections)
│   ├── charts.py           # Plotly charts (donut, gauge, line)
│   ├── charts_analysis.py  # Analysis charts (MA, WoW, mix evolution)
│   ├── chart_colors.py     # Shared color palette + hex_to_rgba
│   ├── formatting.py       # fmt_brl, MONTHS_PT
│   ├── insights_rules.py   # Rule-based insights engine
│   ├── llm_client.py       # OpenRouter GPT-OSS 120B client
│   └── ui/
│       ├── sidebar.py      # Data entry form
│       ├── today.py        # "Hoje" tab
│       ├── month.py        # "Mês Atual" tab
│       ├── analysis.py     # "Análise" tab
│       └── settings.py     # "Config" tab
├── tests/                  # Test suite (96 testes)
├── data/                   # SQLite DB (gitignored)
├── docs/                   # Sprint plans
├── pyproject.toml          # Project metadata + dependencies
├── uv.lock                 # Locked dependency versions
└── README.md
```

## Stack

- Streamlit ≥1.54
- Pandas + NumPy
- Plotly
- SQLite (via SQLAlchemy)
- httpx (OpenRouter API)
- streamlit-extras (skeleton loading)
- pytest + pytest-cov

## Licença

MIT
