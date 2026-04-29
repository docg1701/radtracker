# Sprint 1 — Foundation & Data Entry

**Sprint**: 1 of 6
**Goal**: Running Streamlit app with sidebar input that persists to SQLite. Empty state visible.
**Estimated duration**: 2–3 hours
**Source documents**: [BRIEF.md](../BRIEF.md), [DESIGN_SPEC.md](../DESIGN_SPEC.md), [RESEARCH.md](../RESEARCH.md), [PLAN.md](../PLAN.md)

---

## 1. Pre-flight Checklist

Before any code is written, verify the environment. Run these in the terminal:

```bash
# 1. Verify Python version (must be 3.12+)
python3 --version
# Expected: Python 3.12.3 or higher

# 2. Verify pip is available
pip --version
# Expected: pip 24.x or higher

# 3. Verify the project directory exists
ls -la /home/galvani/dev/radtracker/
# Should see: docs/  .git/
```

---

## 2. Task-by-Task Breakdown

Execute in order. After each task, run the verification steps before moving on.

---

### Task 1.1 — Create Project Skeleton (15 min)

Create these files: `.streamlit/config.toml`, `.env.example`, `.gitignore`, `requirements.txt`, `README.md`, `data/.gitkeep`

#### 1.1a — `.streamlit/config.toml`

```bash
mkdir -p /home/galvani/dev/radtracker/.streamlit
```

Write to `.streamlit/config.toml` (exact copy from DESIGN_SPEC §7.3):

```toml
# .streamlit/config.toml — radtracker theme configuration
# Light theme is the default. Dark theme activates via Streamlit Settings menu.

[theme]
base = "light"
primaryColor = "#0D9488"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F1F5F9"
textColor = "#0F172A"
font = "sans serif"

[theme.dark]
base = "dark"
primaryColor = "#2DD4BF"
backgroundColor = "#0F172A"
secondaryBackgroundColor = "#1E293B"
textColor = "#F1F5F9"
font = "sans serif"

[browser]
gatherUsageStats = false

[server]
headless = true
```

#### 1.1b — `.env.example`

```
# Ollama Cloud API key — get yours at https://ollama.com/settings/keys
# This is optional. Without it, insights fall back to rule-based generation.
OLLAMA_API_KEY=your_key_here
```

#### 1.1c — `.gitignore`

```
# Environment & secrets
.env
.streamlit/secrets.toml

# Database files
data/*.db
data/app.log

# Python
__pycache__/
*.pyc
*.pyo
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

#### 1.1d — `requirements.txt` (exact copy from RESEARCH §8)

```
streamlit>=1.54.0,<2.0.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
ollama>=0.4.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

#### 1.1e — `README.md` (stub)

```markdown
# radtracker

Dashboard pessoal de produtividade para telerradiologia.

## Pré-requisitos

- Python 3.12+
- pip

## Instalação

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # optional — for LLM insights

## Uso

streamlit run app.py

Acesse http://localhost:8501

## Licença

MIT
```

#### 1.1f — `data/.gitkeep`

```bash
mkdir -p /home/galvani/dev/radtracker/data
touch /home/galvani/dev/radtracker/data/.gitkeep
```

#### Verification (Task 1.1)

```bash
ls .streamlit/config.toml .env.example .gitignore requirements.txt README.md data/.gitkeep
# All 6 files should exist
grep "\.env$" .gitignore && grep "data/\*\.db" .gitignore && grep "venv/" .gitignore
# All patterns should match
```

---

### Task 1.2 — Install Dependencies (5 min)

```bash
cd /home/galvani/dev/radtracker
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Verification (Task 1.2)

```bash
which python  # must show: .../radtracker/venv/bin/python
python -c "import streamlit; print('Streamlit', streamlit.__version__)"
python -c "import pandas; print('Pandas', pandas.__version__)"
python -c "import plotly; print('Plotly', plotly.__version__)"
python -c "import numpy; print('NumPy', numpy.__version__)"
python -c "import ollama; print('Ollama', ollama.__version__)"
python -c "import dotenv; print('python-dotenv OK')"
```

---

### Task 1.3 — Create `src/db.py` (45 min)

This is the most critical file. It must contain exactly these 9 functions:

| Function | Purpose |
|---|---|
| `get_connection()` | Return `st.connection("telerrad", type="sql", url="sqlite:///data/telerrad.db")` |
| `init_db(conn)` | Create 3 tables (idempotent via `IF NOT EXISTS`) |
| `upsert_daily(conn, date_str, rm, tc, rx)` | Insert or update a daily row |
| `load_daily(conn, date_str)` | Return row as dict, or None |
| `load_month(conn, year_month)` | Return DataFrame of all rows for a month |
| `load_prices(conn)` | Return `{"rm": float, "tc": float, "rx": float}`, fallback to defaults |
| `save_prices(conn, rm_price, tc_price, rx_price)` | Append new price row |
| `load_goal(conn, year_month)` | Return float, fallback to 45000.0 |
| `save_goal(conn, year_month, goal)` | UPSERT goal for a year-month |

Create `/home/galvani/dev/radtracker/src/db.py` with the content below:

```python
"""
Database module — SQLite schema, connection, and CRUD operations.

Uses Streamlit's st.connection for managed SQLite access.
"""

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

DEFAULT_PRICES: dict[str, float] = {"rm": 35.0, "tc": 25.0, "rx": 4.5}
DEFAULT_GOAL: float = 45000.0


def get_connection() -> Any:
    """Return a Streamlit SQL connection to the local SQLite database."""
    return st.connection(
        "telerrad",
        type="sql",
        url="sqlite:///data/telerrad.db",
    )


def init_db(conn: Any) -> None:
    """Create all 3 tables if they don't exist. Idempotent."""
    create_daily = """
    CREATE TABLE IF NOT EXISTS daily_production (
        date        TEXT PRIMARY KEY,
        rm_count    INTEGER NOT NULL DEFAULT 0,
        tc_count    INTEGER NOT NULL DEFAULT 0,
        rx_count    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """
    create_prices = """
    CREATE TABLE IF NOT EXISTS exam_prices (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_price        REAL NOT NULL,
        tc_price        REAL NOT NULL,
        rx_price        REAL NOT NULL,
        effective_from  TEXT NOT NULL,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """
    create_goals = """
    CREATE TABLE IF NOT EXISTS monthly_goals (
        year_month  TEXT PRIMARY KEY,
        goal_reais  REAL NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """
    with conn.connect() as db_conn:
        db_conn.execute(create_daily)
        db_conn.execute(create_prices)
        db_conn.execute(create_goals)
        db_conn.commit()


def upsert_daily(conn: Any, date_str: str, rm: int, tc: int, rx: int) -> None:
    """Insert or update a daily production row. On conflict, overwrites counts."""
    upsert_sql = """
    INSERT INTO daily_production (date, rm_count, tc_count, rx_count, updated_at)
    VALUES (:date, :rm, :tc, :rx, datetime('now','localtime'))
    ON CONFLICT(date) DO UPDATE SET
        rm_count = excluded.rm_count,
        tc_count = excluded.tc_count,
        rx_count = excluded.rx_count,
        updated_at = datetime('now','localtime')
    """
    with conn.connect() as db_conn:
        db_conn.execute(upsert_sql, {"date": date_str, "rm": rm, "tc": tc, "rx": rx})
        db_conn.commit()


def load_daily(conn: Any, date_str: str) -> dict | None:
    """Return the daily production row as a dict, or None if no data."""
    df = conn.query(
        "SELECT * FROM daily_production WHERE date = :date",
        params={"date": date_str},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def load_month(conn: Any, year_month: str) -> pd.DataFrame:
    """Return all daily production rows for a year-month (e.g. '2026-04')."""
    return conn.query(
        "SELECT * FROM daily_production WHERE date LIKE :prefix ORDER BY date",
        params={"prefix": f"{year_month}%"},
        ttl=0,
    )


def load_prices(conn: Any) -> dict[str, float]:
    """Return current exam prices. Falls back to DEFAULT_PRICES if table is empty."""
    df = conn.query(
        "SELECT rm_price, tc_price, rx_price FROM exam_prices ORDER BY id DESC LIMIT 1",
        ttl=0,
    )
    if df.empty:
        return dict(DEFAULT_PRICES)
    row = df.iloc[0]
    return {"rm": float(row["rm_price"]), "tc": float(row["tc_price"]), "rx": float(row["rx_price"])}


def save_prices(conn: Any, rm_price: float, tc_price: float, rx_price: float) -> None:
    """Append a new price configuration row. Most recent row is treated as current."""
    today_str = date.today().isoformat()
    with conn.connect() as db_conn:
        db_conn.execute(
            "INSERT INTO exam_prices (rm_price, tc_price, rx_price, effective_from) "
            "VALUES (:rm, :tc, :rx, :eff)",
            {"rm": rm_price, "tc": tc_price, "rx": rx_price, "eff": today_str},
        )
        db_conn.commit()


def load_goal(conn: Any, year_month: str) -> float:
    """Return monthly goal for a year-month. Falls back to DEFAULT_GOAL."""
    df = conn.query(
        "SELECT goal_reais FROM monthly_goals WHERE year_month = :ym",
        params={"ym": year_month},
        ttl=0,
    )
    if df.empty:
        return DEFAULT_GOAL
    return float(df.iloc[0]["goal_reais"])


def save_goal(conn: Any, year_month: str, goal: float) -> None:
    """UPSERT monthly goal. Inserts if year_month is new, updates if exists."""
    with conn.connect() as db_conn:
        db_conn.execute(
            """
            INSERT INTO monthly_goals (year_month, goal_reais, updated_at)
            VALUES (:ym, :goal, datetime('now','localtime'))
            ON CONFLICT(year_month) DO UPDATE SET
                goal_reais = excluded.goal_reais,
                updated_at = datetime('now','localtime')
            """,
            {"ym": year_month, "goal": goal},
        )
        db_conn.commit()
```

**Key notes for the implementing agent:**

1. `conn.connect()` returns a SQLAlchemy `Connection` — it uses `:param` named bindings (not `?` positional).
2. `conn.query()` is for SELECT only — returns DataFrame. Set `ttl=0` for always-fresh reads.
3. The `ON CONFLICT ... DO UPDATE SET` syntax is SQLite 3.24+ UPSERT.
4. **If `conn.connect()` raises `AttributeError`** (varies by Streamlit version), try these fallbacks in order:
   - `conn.session` for SQLAlchemy session: `with conn.session as s: s.execute(sqlalchemy.text(sql), {...}); s.commit()`
   - Raw sqlite3: `import sqlite3; raw = sqlite3.connect("data/telerrad.db"); raw.execute(...); raw.commit()`

#### Verification (Task 1.3)

```bash
grep "^def " src/db.py
# Must show: get_connection, init_db, upsert_daily, load_daily, load_month,
#            load_prices, save_prices, load_goal, save_goal
python -c "import ast; ast.parse(open('src/db.py').read()); print('Syntax OK')"
grep -i "sk_\|api_key\|password" src/db.py
# Must produce NO OUTPUT (no hardcoded secrets)
```

---

### Task 1.4 — Create Package Init Files (5 min)

```bash
mkdir -p /home/galvani/dev/radtracker/src/ui
touch /home/galvani/dev/radtracker/src/__init__.py
touch /home/galvani/dev/radtracker/src/ui/__init__.py
```

#### Verification (Task 1.4)

```bash
python -c "import src; print('src OK')"
python -c "import src.ui; print('src.ui OK')"
```

---

### Task 1.5 — Create `src/chart_colors.py` (10 min)

Exact copy from DESIGN_SPEC §9. Create `src/chart_colors.py`:

```python
"""
Shared color palette for all Plotly charts.

Every chart module imports from here — no inline hex values anywhere else.
Colors are colorblind-safe and semantically named.
"""

CHART_COLORS = {
    # Modality colors — used in bar, pie, stacked charts
    "rm": "#2563EB",      # Blue-600
    "tc": "#D97706",      # Amber-600
    "rx": "#0891B2",      # Cyan-600

    # Semantic — used in progress gauge, delta indicators
    "success": "#16A34A",  # Green-600
    "warning": "#CA8A04",  # Yellow-600
    "danger": "#DC2626",   # Red-600

    # Chart accent
    "primary": "#0D9488",  # Teal-600 — main line/bar color
    "muted": "#94A3B8",    # Slate-400 — secondary lines, grid
    "neutral": "#64748B",  # Slate-500 — annotations

    # Progress milestone segments
    "progress_danger": "#DC2626",   # 0-25%
    "progress_warning": "#CA8A04",  # 25-50%
    "progress_on_track": "#0D9488", # 50-75%
    "progress_achieved": "#16A34A", # 75-100%
}
```

#### Verification (Task 1.5)

```bash
python -c "from src.chart_colors import CHART_COLORS; print(len(CHART_COLORS), 'colors')"
# Expected: 13 colors
python -c "from src.chart_colors import CHART_COLORS; assert CHART_COLORS['rm'] == '#2563EB'; print('OK')"
```

---

### Task 1.6 — Create `src/ui/sidebar.py` (30 min)

Implements `render_sidebar(conn)` per DESIGN_SPEC §4.4. Create `src/ui/sidebar.py`:

```python
"""
Sidebar data-entry form.

Renders the app title, greeting, date picker, 3 modality inputs,
and the save button. Handles UPSERT via db.upsert_daily().
"""

import streamlit as st
from datetime import date

from src.db import upsert_daily, load_daily


def render_sidebar(conn) -> None:
    """
    Render the complete sidebar: header, date picker, modality inputs, save button.

    On save:
      - Calls db.upsert_daily() with current form values.
      - Shows a toast notification (insert or update).
      - Triggers st.rerun() to refresh the dashboard.
    """
    with st.sidebar:
        # Header
        st.title("📊 radtracker")
        st.markdown("Olá, **Galvani** 👋")

        # Date picker
        selected_date = st.date_input(
            "📅 Data",
            value=date.today(),
            format="DD/MM/YYYY",
            max_value=date.today(),
        )
        date_str = selected_date.isoformat()

        # Pre-fill from existing data
        existing = load_daily(conn, date_str)
        default_rm = existing["rm_count"] if existing else 0
        default_tc = existing["tc_count"] if existing else 0
        default_rx = existing["rx_count"] if existing else 0

        # Modality inputs (3 columns)
        cols = st.columns(3)
        with cols[0]:
            rm = st.number_input("RM", min_value=0, step=1, value=default_rm, key="sb_rm")
        with cols[1]:
            tc = st.number_input("TC", min_value=0, step=1, value=default_tc, key="sb_tc")
        with cols[2]:
            rx = st.number_input("RX", min_value=0, step=1, value=default_rx, key="sb_rx")

        # Save button
        if st.button("💾 Salvar produção", type="primary", use_container_width=True):
            upsert_daily(conn, date_str, rm, tc, rx)
            formatted = selected_date.strftime("%d/%m")
            if existing:
                st.toast(f"📝 Produção de {formatted} atualizada!", icon="📝")
            else:
                st.toast(f"✅ Produção de {formatted} salva!", icon="✅")
            st.rerun()

        # Footer
        st.sidebar.divider()
        st.sidebar.caption("radtracker v1.0 · local")
```

**Key behaviors**:
- Date defaults to today, max is today (no future dates).
- On first visit: inputs show 0. On return: pre-fill with existing values.
- Save → UPSERT. "salva" for insert, "atualizada" for update.
- `st.rerun()` forces full refresh after save.

#### Verification (Task 1.6)

```bash
python -c "import ast; ast.parse(open('src/ui/sidebar.py').read()); print('Syntax OK')"
grep "render_sidebar" src/ui/sidebar.py
grep "upsert_daily" src/ui/sidebar.py
grep "st.toast" src/ui/sidebar.py
grep "st.rerun" src/ui/sidebar.py
```

---

### Task 1.7 — Create `app.py` — Entry Point with 4 Tabs (20 min)

Create `app.py` at project root:

```python
"""
radtracker — Personal productivity dashboard for teleradiology.

Entry point. Run with:
    streamlit run app.py

Sprint 1: sidebar + SQLite + 4 placeholder tabs.
"""

import streamlit as st

from src.db import get_connection, init_db
from src.ui.sidebar import render_sidebar

# Page config — MUST be first Streamlit command
st.set_page_config(
    page_title="radtracker",
    page_icon="📊",
    layout="wide",
)

# Database initialization (idempotent)
conn = get_connection()
init_db(conn)

# Sidebar
render_sidebar(conn)

# Tabs (4 placeholders)
tab_hoje, tab_mes, tab_analise, tab_config = st.tabs([
    "📊 Hoje",
    "📅 Mês Atual",
    "📈 Análise",
    "⚙️ Config",
])

with tab_hoje:
    st.header("📊 Hoje")
    st.info("Em breve — dados de hoje (Sprint 2)")

with tab_mes:
    st.header("📅 Mês Atual")
    st.info("Em breve — visão mensal (Sprint 3)")

with tab_analise:
    st.header("📈 Análise")
    st.info("Em breve — análises e insights (Sprint 4)")

with tab_config:
    st.header("⚙️ Configurações")
    st.info("Em breve — preços e meta (Sprint 5)")
```

#### Verification (Task 1.7)

```bash
python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"
grep "from src.db import" app.py
grep "from src.ui.sidebar import" app.py
grep "set_page_config" app.py
grep "st.tabs" app.py
```

---

### Task 1.8 — Integration Smoke Test (15 min)

#### Step 1: Start the app

```bash
cd /home/galvani/dev/radtracker
source venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501. Fix any errors before continuing.

#### Step 2: Verify sidebar

- [ ] "📊 radtracker" title visible
- [ ] "Olá, **Galvani** 👋" greeting visible
- [ ] Date picker shows today in DD/MM/YYYY format
- [ ] RM, TC, RX inputs side-by-side, starting at 0
- [ ] "💾 Salvar produção" button is full-width, teal

#### Step 3: Verify data persistence

1. Enter RM=5, TC=3, RX=20 → click Salvar
2. Toast "✅ Produção de XX/XX salva!" appears
3. Enter RM=8, TC=6, RX=35 → click Salvar again
4. Toast "📝 Produção de XX/XX atualizada!" appears (proves UPSERT)

#### Step 4: Verify database

```bash
sqlite3 data/telerrad.db "SELECT * FROM daily_production;"
# Expected: one row with 8|6|35
sqlite3 data/telerrad.db "SELECT COUNT(*) FROM daily_production;"
# Expected: 1
sqlite3 data/telerrad.db ".tables"
# Expected: daily_production  exam_prices  monthly_goals
```

#### Step 5: Verify 4 tabs

Click each tab — all show placeholder "Em breve" messages.

#### Step 6: Verify theme

☰ → Settings → Theme → Dark → toggle back to Light. Both work.

#### Step 7: Verify reload resilience

Ctrl+C, restart `streamlit run app.py`, select today's date.
Previously saved values (RM=8, TC=6, RX=35) are pre-filled.

---

## 3. Sprint 1 Definition of Done

All items must be ✅:

- [ ] `streamlit run app.py` starts without errors
- [ ] Sidebar renders: title, greeting, date picker, 3 inputs in columns, save button, footer
- [ ] Save inserts a row → `daily_production` table
- [ ] Re-save on same date updates (UPSERT, row count = 1)
- [ ] Toast: "✅ ... salva!" on insert, "📝 ... atualizada!" on update
- [ ] 4 tabs visible with placeholder text
- [ ] `.env.example` and `.gitignore` exist and are correct
- [ ] `requirements.txt` installs cleanly
- [ ] All 3 SQLite tables exist
- [ ] `src/__init__.py` and `src/ui/__init__.py` exist
- [ ] `src/chart_colors.py` has 13 colors
- [ ] Dark theme toggle works
- [ ] Data survives app restart
- [ ] No hardcoded secrets

---

## 4. Common Pitfalls & Debugging

### Pitfall 1: `ModuleNotFoundError: No module named 'src'`

Run `streamlit` from the project root (`/home/galvani/dev/radtracker`). The working directory must contain `src/`.

### Pitfall 2: `st.connection` has no `connect()` method

If `AttributeError: 'SQLConnection' object has no attribute 'connect'`:
- Try `conn.session` instead: `with conn.session as s: s.execute(sqlalchemy.text(sql), params); s.commit()`
- Or use raw sqlite3: `import sqlite3; raw = sqlite3.connect("data/telerrad.db")`

### Pitfall 3: Data directory not created

The `data/` directory is created manually in Task 1.1f. If SQLite can't create the file, ensure the directory exists: `mkdir -p data`

### Pitfall 4: `st.set_page_config` not first

If you see "set_page_config() can only be called once" errors, ensure `st.set_page_config()` is the very first Streamlit call in `app.py` — no `st.*` calls in imported modules before it.

### Pitfall 5: Date format confusion

SQLite stores dates as TEXT in ISO format (`YYYY-MM-DD`). The UI shows DD/MM/YYYY. The `isoformat()` and `strftime("%d/%m")` conversions handle this.

### Pitfall 6: Port already in use

If port 8501 is busy: `streamlit run app.py --server.port 8502`

### Pitfall 7: Virtual environment not activated

Always verify: `which python` must show `.../radtracker/venv/bin/python` before running pip or streamlit.
