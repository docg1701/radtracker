# radtracker

Personal productivity dashboard for teleradiology.
Track revenue, goals and trends with Streamlit + SQLite.
English-native UI with a Brazilian Portuguese option.

## Features

- 📅 **Today**: KPI cards, distribution by modality, 7-day sparkline
- 📆 **This Month**: goal progress, daily revenue, pace alerts
- 📈 **Analysis**: moving averages (MA7/MA30), weekly comparison, mix evolution
- 🤖 **AI Insights**: GPT-OSS 120B via OpenRouter (rule-based fallback when offline)
- 🔒 **Authentication**: login + password (scrypt) with optional TOTP 2FA, configured via SSH
- ⚙️ **Settings**: price per exam, monthly goal, your name, API key, AI prompt

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Installation

```bash
git clone https://github.com/docg1701/radtracker.git
cd radtracker
uv sync                       # installs all dependencies
```

## Usage

```bash
uv run streamlit run app.py   # http://localhost:8501
```

The authentication gate requires `data/auth.json`. For local use, create a scratch one:

```bash
python -c "from src.auth_store import create_bootstrap_auth; print(create_bootstrap_auth('dev', 'dev-password-123', 'data/auth.json', cookie_secure=False))"
```

(In production, `deploy.yml` creates this file automatically from the vault — see
[docs/deployment.md](docs/deployment.md).)

## AI (OpenRouter)

For AI-generated insights:

1. Create a free account at <https://openrouter.ai>
2. Generate an API key
3. In the **Settings** tab, paste your key into the "OpenRouter API key" field
4. Optionally, customize your name and the AI prompt in the same tab
5. In the **AI Chat** tab, click "Start analysis"
6. Without a key, the rule-based fallback is used automatically

The key is stored locally in the SQLite database — no `.env` files.

## Running the tests

```bash
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

## Project structure

```text
radtracker/
├── app.py                  # Streamlit entry point (auth gate after set_page_config)
├── src/
│   ├── auth_crypto.py      # scrypt + TOTP (RFC 6238) + HMAC session tokens
│   ├── auth_store.py       # data/auth.json + gate helpers
│   ├── db.py               # SQLite schema + CRUD (5 tables)
│   ├── calculations.py     # Business logic (earnings, MA, projections)
│   ├── charts.py           # Plotly charts (donut, gauge, line)
│   ├── charts_analysis.py  # Analysis charts (MA, WoW, mix evolution)
│   ├── chart_colors.py     # Shared color palette + hex_to_rgba
│   ├── formatting.py       # fmt_money, MONTHS, md_escape
│   ├── i18n.py             # EN/PT translation catalog + translate()/t()
│   ├── insights_rules.py   # Rule-based insights engine (bilingual)
│   ├── llm_client.py       # OpenRouter GPT-OSS 120B client
│   ├── text_sanitize.py    # Markdown/$ sanitization for LLM output
│   └── ui/
│       ├── login.py        # Auth gate (login, TOTP, logout, language selector)
│       ├── sidebar.py      # Data entry form
│       ├── today.py        # "Today" tab
│       ├── month.py        # "This Month" tab
│       ├── analysis.py     # "Analysis" tab
│       ├── chat.py         # "AI Chat" tab
│       └── settings.py     # "Settings" tab
├── scripts/
│   └── manage_auth.py      # SSH auth management CLI: 2FA, password, repair
├── tests/                  # Test suite (326 tests)
├── data/                   # SQLite DB + auth.json (gitignored)
├── docs/                   # Guides and design reference
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
- pytest + pytest-cov

## Deploy

radtracker can be deployed to any VPS with Docker + Ansible.
Works on a local network (HTTP) or with your own domain (HTTPS + Let's Encrypt).

```bash
git clone https://github.com/docg1701/radtracker.git
cd radtracker
# follow the guide in docs/deployment.md
```

Production stack: Streamlit → Docker → Caddy (TLS) → fail2ban (sshd) → Ansible
In-app authentication: login + TOTP 2FA (see [docs/deployment.md](docs/deployment.md))

See [docs/deployment.md](docs/deployment.md) for the full guide.

## License

MIT
