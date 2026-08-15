# radtracker

Dashboard pessoal de produtividade para telerradiologia.
Acompanhe faturamento, metas e tendências com Streamlit + SQLite.

## Funcionalidades

- 📅 **Hoje**: KPI cards, distribuição por modalidade, sparkline de 7 dias
- 📆 **Mês Atual**: progresso da meta, faturamento diário, alertas de ritmo
- 📈 **Análise**: médias móveis (MA7/MA30), comparação semanal, evolução do mix
- 🤖 **Insights IA**: GPT-OSS 120B via OpenRouter (fallback para regras se offline)
- 🔒 **Autenticação**: login + senha (scrypt) com TOTP 2FA opcional, configurado via SSH
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

O portão de autenticação exige `data/auth.json`. Para uso local, crie um de rascunho:

```bash
python -c "from src.auth_store import create_bootstrap_auth; print(create_bootstrap_auth('dev', 'dev-password-123', 'data/auth.json', cookie_secure=False))"
```

(Em produção o `deploy.yml` cria esse arquivo automaticamente a partir do vault — ver [docs/deployment.md](docs/deployment.md).)

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
├── app.py                  # Entry point Streamlit (auth gate após set_page_config)
├── src/
│   ├── auth_crypto.py      # scrypt + TOTP (RFC 6238) + token de sessão HMAC
│   ├── auth_store.py       # data/auth.json + helpers do gate
│   ├── db.py               # SQLite schema + CRUD (5 tables)
│   ├── calculations.py     # Business logic (earnings, MA, projections)
│   ├── charts.py           # Plotly charts (donut, gauge, line)
│   ├── charts_analysis.py  # Analysis charts (MA, WoW, mix evolution)
│   ├── chart_colors.py     # Shared color palette + hex_to_rgba
│   ├── formatting.py       # fmt_brl, MONTHS_PT
│   ├── insights_rules.py   # Rule-based insights engine
│   ├── llm_client.py       # OpenRouter GPT-OSS 120B client
│   └── ui/
│       ├── login.py        # Gate de autenticação (login, TOTP, logout)
│       ├── sidebar.py      # Data entry form
│       ├── today.py        # "Hoje" tab
│       ├── month.py        # "Mês Atual" tab
│       ├── analysis.py     # "Análise" tab
│       ├── chat.py         # "Chat IA" tab
│       └── settings.py     # "Config" tab
├── scripts/
│   ├── import_csv.py       # Importador CSV legado
│   └── manage_auth.py      # CLI de gestão de auth (SSH): 2FA, senha, repair
├── tests/                  # Test suite (294 testes)
├── data/                   # SQLite DB + auth.json (gitignored)
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

## Deploy

radtracker pode ser deployado em qualquer VPS com Docker + Ansible.
Funciona em rede local (HTTP) ou com domínio próprio (HTTPS + Let's Encrypt).

```bash
git clone https://github.com/docg1701/radtracker.git
cd radtracker
# seguir o guia em docs/deployment.md
```

Stack de produção: Streamlit → Docker → Caddy (TLS) → fail2ban (sshd) → Ansible
Autenticação no app: login + TOTP 2FA (ver [docs/auth-implementation-plan.md](docs/auth-implementation-plan.md))

Veja [docs/deployment.md](docs/deployment.md) para o guia completo.

## Licença

MIT
