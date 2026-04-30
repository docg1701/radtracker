# radtracker

Dashboard pessoal de produtividade para telerradiologia.
Acompanhe faturamento, metas e tendências com Streamlit + SQLite.

## Funcionalidades

- 📊 **Hoje**: KPI cards, distribuição por modalidade, sparkline de 7 dias
- 📅 **Mês Atual**: progresso da meta, faturamento diário, alertas de ritmo
- 📈 **Análise**: médias móveis (MA7/MA30), comparação semanal, evolução do mix
- 🤖 **Insights IA**: GPT-OSS 120B via OpenRouter (fallback para regras se offline)
- ⚙️ **Config**: preços por exame, meta mensal, limpeza de dados

## Pré-requisitos

- Python 3.12+
- pip

## Instalação

```bash
git clone https://github.com/docg1701/radtracker.git
cd radtracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # opcional — para insights com IA
```

## Uso

```bash
streamlit run app.py          # http://localhost:8501
```

## IA (OpenRouter)

Para insights gerados por IA:

1. Crie uma conta gratuita em https://openrouter.ai
2. Gere uma API key
3. Adicione ao `.env`: `OPENROUTER_API_KEY=sk-or-v1-...`
4. Na aba "Análise", o insight será gerado por GPT-OSS 120B
5. Sem chave, o fallback baseado em regras é usado automaticamente

## Executando os testes

```bash
pip install -r requirements.txt    # já inclui pytest, pytest-cov, respx
python -m pytest tests/ -v
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

## Estrutura do projeto

```
radtracker/
├── app.py                  # Entry point Streamlit
├── src/
│   ├── db.py               # SQLite schema + CRUD
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
├── tests/                  # Test suite (93 testes)
├── data/                   # SQLite DB (gitignored)
├── docs/                   # Sprint plans
├── requirements.txt
├── .env.example
└── README.md
```

## Stack

- Streamlit ≥1.54
- Pandas + NumPy
- Plotly
- SQLite (via SQLAlchemy)
- httpx (OpenRouter API)
- pytest + pytest-cov

## Licença

MIT
