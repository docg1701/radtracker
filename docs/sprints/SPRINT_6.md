# Sprint 6 — Implementation Plan: Testing, Polish & Release

**Project**: radtracker
**Date**: 2026-04-29
**Status**: Planning complete. Implementation pending.
**Previous sprints**: S1–S5 ✅ complete

---

## 1. Objective

Deliver a **tested, documented, and tagged v1.0.0 release**. All core logic modules reach ≥80% test coverage. The `README.md` is rewritten as a complete user/developer guide. A final `.gitignore` audit ensures no secrets or generated files are tracked.

---

## 2. Testing Architecture

### 2.1 Philosophy

- **Behavior only**: Test what the function does, not how it does it.
- **No Streamlit in unit tests**: `db.py`, `calculations.py`, `formatting.py`, `chart_colors.py`, `insights_rules.py`, and `llm_client.py` are tested with pure Python. Streamlit UI modules (`src/ui/*.py`) and chart modules (`src/charts*.py`) are tested **manually** (dashboard visual verification) since they're thin wrappers around tested logic.
- **In-memory SQLite**: All database tests use `sqlite3.connect(":memory:")` — fast, isolated, no file cleanup needed.
- **Named fake classes**: The Streamlit connection is mocked with `FakeConnection`, the LLM HTTP client is mocked with `respx` (httpx mock).

### 2.2 FakeConnection Design

`db.py` functions expect a `conn` parameter with `.connect()` and `.query()` methods matching Streamlit's `st.connection` API. `FakeConnection` wraps an in-memory SQLite database:

```python
class FakeConnection:
    """Emulates st.connection('telerrad', type='sql') with SQLite :memory:."""

    def __init__(self) -> None:
        self._engine = sqlalchemy.create_engine("sqlite:///:memory:")

    def connect(self) -> sqlalchemy.engine.Connection:
        """Returns a SQLAlchemy connection (context-manager compatible)."""
        return self._engine.connect()  # type: ignore[return-value]

    def query(self, sql: str, *, params: dict | None = None, ttl: int = 0) -> pd.DataFrame:
        """Executes a SELECT query, returns a pandas DataFrame."""
        with self._engine.connect() as c:
            result = c.execute(sqlalchemy.text(sql), params or {})
            rows = result.fetchall()
            cols = result.keys()
        return pd.DataFrame(rows, columns=cols)
```

### 2.3 What Is Tested vs. What Is Manual

| Module | Automated test? | Rationale |
|---|---|---|
| `src/db.py` | ✅ Yes | CRUD + schema logic, no Streamlit rendering |
| `src/calculations.py` | ✅ Yes | Pure business logic, earnings, projections, MA, WoW |
| `src/formatting.py` | ✅ Yes | Pure formatting, currency, month constants |
| `src/chart_colors.py` | ✅ Yes | Pure hex/rgba conversion |
| `src/insights_rules.py` | ✅ Yes | Pure function: dict in → string out |
| `src/llm_client.py` | ✅ Yes | Mocked httpx, no real API calls |
| `src/charts.py` | ❌ Manual | Plotly figure objects — visual verification |
| `src/charts_analysis.py` | ❌ Manual | Plotly figure objects — visual verification |
| `src/ui/*.py` | ❌ Manual | Streamlit rendering — thin wrappers |
| `app.py` | ❌ Manual | Orchestration — smoke test |

---

## 3. Task Breakdown

### 6.1 — Create `tests/__init__.py`

**File**: `tests/__init__.py`

**Content**: Empty file (makes `tests` a package).

**Acceptance**: `python -c "import tests"` succeeds.

**Dependencies**: None.

---

### 6.2 — Create `tests/conftest.py` (Fixtures)

**File**: `tests/conftest.py`

**Contents**:

```python
import sqlalchemy as sa
import pandas as pd
import pytest

DB_CREATE_SQL = [
    """CREATE TABLE IF NOT EXISTS daily_production (...);""",  # exact DDL from src/db.py init_db
    """CREATE TABLE IF NOT EXISTS exam_prices (...);""",
    """CREATE TABLE IF NOT EXISTS monthly_goals (...);""",
]

class FakeConnection:
    # (... as documented in §2.2 above ...)

@pytest.fixture
def conn():
    """Return a FakeConnection with full schema, ready for testing."""
    fc = FakeConnection()
    with fc.connect() as c:
        for ddl in DB_CREATE_SQL:
            c.execute(sa.text(ddl))
        c.commit()
    return fc

@pytest.fixture
def default_prices():
    """Return the DEFAULT_PRICES dict from src/db.py."""
    from src.db import DEFAULT_PRICES
    return dict(DEFAULT_PRICES)  # copy to avoid mutation
```

**Expectations**:
- `conn` fixture creates all 3 tables (idempotent via `CREATE TABLE IF NOT EXISTS`).
- `default_prices` returns `{"rm": 35.0, "tc": 25.0, "rx": 4.5}`.

**Dependencies**: None.

---

### 6.3 — Create `tests/test_db.py`

**File**: `tests/test_db.py`

**Target module**: `src.db`

**Test functions** (15 total):

| # | Function | What It Verifies | Technique / Inputs | Expected Output |
|---|---|---|---|---|
| 1 | `test_init_db_creates_tables` | `init_db(conn)` creates all 3 tables in an empty DB | Call `init_db(conn)`, then `SELECT name FROM sqlite_master WHERE type='table'` | Set `{"daily_production","exam_prices","monthly_goals"}` |
| 2 | `test_init_db_idempotent` | Calling `init_db` twice does not error | `init_db(conn)`, then `init_db(conn)` again | No exception |
| 3 | `test_upsert_insert` | First save creates a row | `upsert_daily(conn, "2026-04-15", 8, 6, 35)` then `SELECT COUNT(*)` | 1 row |
| 4 | `test_upsert_update` | Second save on same date overwrites counts | Insert `(8,6,35)`, then `upsert(..., 10,10,50)`, load | `rm_count=10`, `tc_count=10`, `rx_count=50` |
| 5 | `test_upsert_preserves_created_at` | `created_at` unchanged on update, `updated_at` changes | Insert, capture `created_at` via `load_daily`. `time.sleep(1.1)` (ensures at least 1s difference for SQLite TEXT timestamps). Upsert again. Load again. Compare: `assert first["created_at"] == second["created_at"]` and `assert first["updated_at"] != second["updated_at"]` | `created_at` equal, `updated_at` different |
| 6 | `test_load_daily_exists` | `load_daily` returns correct dict for existing date | Insert known data, load same date | Dict with expected `rm_count`, `tc_count`, `rx_count` |
| 7 | `test_load_daily_nonexistent` | Returns `None` for date with no row | Load a date that was never inserted | `None` |
| 8 | `test_load_month_returns_correct_rows` | Only rows matching `YYYY-MM%` prefix | Insert 2 rows in "2026-04", 1 row in "2026-05", load "2026-04" | DataFrame with 2 rows |
| 9 | `test_load_month_empty` | Returns empty DataFrame for month with no rows | Load "2026-06" with no data | `assert df.empty` (no `== True` needed) |
| 10 | `test_load_prices_defaults` | Returns DEFAULT_PRICES when `exam_prices` is empty | `load_prices(conn)` on fresh DB | `{"rm":35.0,"tc":25.0,"rx":4.5}` |
| 11 | `test_save_and_load_prices` | Round-trip: save prices, load them back | `save_prices(conn, 40.0, 30.0, 5.0)`, then `load_prices(conn)` | `{"rm":40.0,"tc":30.0,"rx":5.0}` |
| 12 | `test_load_prices_most_recent` | Only the latest price row is returned | Save `(35,25,4.5)`, then save `(40,30,5.0)` | `(40,30,5.0)` |
| 13 | `test_load_goal_default` | Returns DEFAULT_GOAL when no goal row exists | `load_goal(conn, "2026-04")` on fresh DB | `45000.0` |
| 14 | `test_save_and_load_goal` | Round-trip: save goal, load it back | `save_goal(conn, "2026-04", 50000.0)`, then `load_goal(conn, "2026-04")` | `50000.0` |
| 15 | `test_load_goal_different_month_default` | Missing month returns DEFAULT_GOAL | Save goal for "2026-04", load "2026-05" | `45000.0` |

**Dependencies**: 6.2 (needs `conn` fixture + `FakeConnection`).

---

### 6.4 — Create `tests/test_calculations.py`

**File**: `tests/test_calculations.py`

**Target module**: `src.calculations`

**Constant**:
```python
DEFAULT_PRICES = {"rm": 35.0, "tc": 25.0, "rx": 4.5}
```

**Test functions** (33 total):

#### Pure functions (no DB) — 10 tests

| # | Function | What It Verifies | Inputs | Expected |
|---|---|---|---|---|
| 1 | `test_compute_earnings_typical` | `compute_earnings(rm,tc,rx,prices)` formula | `rm=8, tc=6, rx=35` | `587.5` (8×35+6×25+35×4.5) |
| 2 | `test_compute_earnings_all_zeros` | Edge case: all zero counts | `rm=0, tc=0, rx=0` | `0.0` |
| 3 | `test_compute_earnings_only_rm` | Only RM exams | `rm=10, tc=0, rx=0` | `350.0` |
| 4 | `test_estimate_hours_typical` | Hours formula | `rm=15, tc=15, rx=150` | `6.0` |
| 5 | `test_estimate_hours_all_zeros` | No exams → 0 hours | `rm=0, tc=0, rx=0` | `0.0` |
| 6 | `test_format_time_range_typical` | Time range from hours | `hours=5.2` | `"~08:00 – 13:12"` |
| 7 | `test_format_time_range_zero` | Zero hours | `hours=0.0` | `"~08:00 – 08:00"` |
| 8 | `test_format_time_range_full_day` | 12+ hour day wraps correctly | `hours=14.5` (870 min) | Start `08:00`, end `22:30` |
| 9 | `test_compute_delta_pct_positive` | Positive delta | `today=600.0, yesterday=500.0` | `20.0` |
| 10 | `test_compute_delta_pct_negative` | Negative delta | `today=400.0, yesterday=500.0` | `-20.0` |
| 11 | `test_compute_delta_pct_none_yesterday` | `yesterday=None` → `None` | `today=600.0, yesterday=None` | `None` |
| 12 | `test_compute_delta_pct_zero_yesterday` | Division-by-zero guarded | `today=600.0, yesterday=0.0` | `None` |

#### DB-dependent (monthly stats) — 8 tests

| # | Function | What It Verifies | Technique |
|---|---|---|---|
| 13 | `test_compute_monthly_stats_empty_month` | All-zero stats when no data | `compute_monthly_stats(conn, "2026-04", 45000, prices)` | `mtd_earnings=0, pct_goal=0, days_worked=0`. ⚠️ Use a **past month** (e.g. "2026-03") to avoid non-deterministic `remaining_work_days`/`daily_target_needed` when `date.today()` falls within the test month. |
| 14 | `test_compute_monthly_stats_with_data` | Correct MTD with known rows | Insert 2 rows → compute | `mtd_earnings` matches sum |
| 15 | `test_compute_monthly_stats_pct_goal` | Percentage calculation | `mtd=22500, goal=45000` | `pct_goal=50.0` |
| 16 | `test_compute_monthly_stats_total_work_days` | April 2026 has 26 Mon–Sat | Compute for 2026-04 | `total_work_days=26` |
| 17 | `test_compute_monthly_stats_work_days_exclude_sunday` | No Sunday in work days | Build date_range for month, check weekday | No date has `weekday()==6` |
| 18 | `test_compute_monthly_stats_past_month` | Remaining days = 0 for past month | Compute for 2026-03 (past) | `remaining_work_days=0` |
| 19 | `test_compute_daily_target_normal` | Monthly goal ÷ working days | `goal=45000, days=26` | `45000/26` ≈ `1730.77` |
| 20 | `test_compute_daily_target_zero_days` | Guard: zero working days | `goal=45000, days=0` | `0.0` |

#### DB-dependent (earnings column + compute_mtd) — 4 tests

| # | Function | Technique |
|---|---|---|
| 21 | `test_add_earnings_column` | DataFrame with `rm_count,tc_count,rx_count` → gets `earnings` column |
| 22 | `test_add_earnings_column_does_not_mutate` | Original df unchanged after `add_earnings_column` |
| 23 | `test_compute_mtd_earnings` | DataFrame with 2 rows → sum of earnings |
| 24 | `test_compute_mtd_earnings_empty` | Empty DataFrame → `0.0` |

#### Historical stats — 9 tests

| # | Function | What It Verifies |
|---|---|---|
| 25 | `test_historical_empty_db` | `compute_historical_stats` on empty DB returns `_empty_historical_stats` shape |
| 26 | `test_historical_ma7_with_one_day` | 1 row → `ma7 == earnings` (min_periods=1) |
| 27 | `test_historical_ma7_rolling` | 10 rows → last `ma7` = mean of rows 4–10 |
| 28 | `test_historical_ma30_insufficient_data` | 5 rows → `ma30` = mean of all 5 (min_periods=1) |
| 29 | `test_historical_wow_positive` | 2 weeks with different totals → positive WoW % | ⚠️ Must insert rows spanning at least 2 ISO weeks (e.g., 2026-04-06 Mon and 2026-04-13 Mon). Single-week data produces `wow_change_pct = None`. |
| 30 | `test_historical_wow_insufficient_weeks` | 1 week → `wow_change_pct = None` |
| 31 | `test_historical_modality_mix_sum_to_100` | `rm_pct + tc_pct + rx_pct ≈ 100.0` (or 0.0 if no data) |
| 32 | `test_historical_consecutive_below_target` | 3 days below daily target → count = 3 |
| 33 | `test_historical_empty_df_columns` | `_empty_historical_stats` returns DataFrame with expected columns |

**Dependencies**: 6.2 (needs `conn` fixture + `default_prices` fixture).

---

### 6.5 — Create `tests/test_insights.py`

**File**: `tests/test_insights.py`

**Target module**: `src.insights_rules`

**Helper**:
```python
def _make_stats(pct_goal: float, mtd: float = 22500.0, days_worked: int = 13,
                total_days: int = 26, remaining_work_days: int = 13,
                daily_target_needed: float = 1730.77,
                projection_month_end: float = 45000.0,
                wow: float | None = None,
                mom: float | None = None, consecutive: int = 0,
                mix_current: dict | None = None,
                mix_history: dict | None = None) -> dict:
    """Build a stats dict matching compute_historical_stats output.

    All keys required by generate_rule_insights are present, including
    daily_target_needed, remaining_work_days, and projection_month_end.
    """
    default_mix = {"rm": 60.0, "tc": 25.0, "rx": 15.0}
    return {
        "current_month_stats": {
            "pct_goal": pct_goal,
            "mtd_earnings": mtd,
            "days_worked": days_worked,
            "total_work_days": total_days,
            "remaining_work_days": remaining_work_days,
            "daily_target_needed": daily_target_needed,
            "daily_avg": mtd / days_worked if days_worked > 0 else 0.0,
            "projection_month_end": projection_month_end,
        },
        "wow_change_pct": wow,
        "mom_change_pct": mom,
        "modality_mix_current": mix_current or default_mix,
        "modality_mix_historical": mix_history or {},
        "consecutive_below_target": consecutive,
    }
```

**Test functions** (19 total):

| # | Function | What It Verifies |
|---|---|---|
| 1 | `test_success_tone_pct_80` | `pct_goal ≥ 75` → output contains `"🟢"` and `"Excelente"` |
| 2 | `test_on_track_tone_pct_60` | `50 ≤ pct < 75` → `"🟡"` and `"No caminho certo"` |
| 3 | `test_warning_tone_pct_40` | `25 ≤ pct < 50` → `"🟠"` and `"Atenção"` |
| 4 | `test_danger_tone_pct_10` | `pct < 25` → `"🔴"` and `"Alerta"` |
| 5 | `test_contains_galvani_name` | Output string contains `"Galvani"` |
| 6 | `test_contains_formatted_currency` | Output contains Brazilian Real format (e.g. `"R$ 22.500,00"`) |
| 7 | `test_contains_days_worked` | Output includes the number of days worked |
| 8 | `test_success_suggestion` | Success tone → suggestion about consolidating rhythm |
| 9 | `test_danger_suggestion_actionable` | Danger tone → suggestion about RM volume or adjusting goal |
| 10 | `test_wow_trend_up` | `wow_change_pct=10.5` → `"📈"` and `"crescimento"` |
| 11 | `test_wow_trend_down` | `wow_change_pct=-5.0` → `"📉"` and `"queda"` |
| 12 | `test_wow_trend_none` | `wow_change_pct=None` → no WoW line in output |
| 13 | `test_mom_trend_up` | `mom_change_pct=15.0` → `"📈"` and `"crescimento"` and `"Mês a mês"` |
| 14 | `test_mom_trend_none` | `mom_change_pct=None` → no MoM line |
| 15 | `test_consecutive_below_trigger` | `consecutive≥3` → `"⚠️"` and `"dias consecutivos"` |
| 16 | `test_consecutive_below_no_trigger` | `consecutive=1` → no consecutive warning |
| 17 | `test_modality_mix_shift_detected` | RM mix shifted >10pp vs historical average → `"🔍"` and `"Mudança no mix"` |
| 18 | `test_modality_mix_no_shift` | Mix within 10pp → no shift alert |
| 19 | `test_empty_stats_returns_message` | `current_month_stats=None` → friendly message about registering data |

**Dependencies**: None (pure function, only needs the `generate_rule_insights` function + fabricated stats dict).

---

### 6.6 — Create `tests/test_formatting.py`

**File**: `tests/test_formatting.py`

**Target module**: `src.formatting`

**Test functions** (8 total):

| # | Function | Input | Expected |
|---|---|---|---|
| 1 | `test_fmt_brl_integer` | `1000.0` | `"R$ 1.000,00"` |
| 2 | `test_fmt_brl_with_cents` | `1250.50` | `"R$ 1.250,50"` |
| 3 | `test_fmt_brl_zero` | `0.0` | `"R$ 0,00"` |
| 4 | `test_fmt_brl_negative` | `-500.00` | `"−R$ 500,00"` (unicode minus `\u2212`) |
| 5 | `test_fmt_brl_large_number` | `1234567.89` | `"R$ 1.234.567,89"` |
| 6 | `test_fmt_brl_half_centavo_round_up` | `0.005` → `cents = int(0.5 + 0.5) = 1` | `"R$ 0,01"` |
| 7 | `test_months_pt_all_12` | `len(MONTHS_PT)` | `12` |
| 8 | `test_months_pt_january` | `MONTHS_PT[1]` | `"Janeiro"` |

**Dependencies**: None.

---

### 6.7 — Create `tests/test_chart_colors.py`

**File**: `tests/test_chart_colors.py`

**Target module**: `src.chart_colors`

**Test functions** (5 total):

| # | Function | Input | Expected |
|---|---|---|---|
| 1 | `test_hex_to_rgba_full` | `("#ff0000", 0.5)` | `"rgba(255, 0, 0, 0.5)"` |
| 2 | `test_hex_to_rgba_short` | `("#0D9", 1.0)` | `"rgba(0, 221, 153, 1.0)"` |
| 3 | `test_hex_to_rgba_black` | `("#000000", 0.0)` | `"rgba(0, 0, 0, 0.0)"` |
| 4 | `test_chart_colors_has_required_keys` | `CHART_COLORS.keys()` | Contains `"rm"`, `"tc"`, `"rx"`, `"primary"`, `"muted"`, `"progress_danger"` |
| 5 | `test_chart_colors_all_start_with_hash` | All values in `CHART_COLORS` | Every value is `str` starting with `"#"` |

**Dependencies**: None.

---

### 6.8 — Create `tests/test_llm_client.py`

**File**: `tests/test_llm_client.py`

**Target module**: `src.llm_client`

**MOCKING STRATEGY**: Use `respx` (httpx mock) to intercept all HTTP requests. Zero real API calls.

```python
import respx
from httpx import Response

# In each test:
@respx.mock
def test_whatever():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "Insight IA"}}]
        })
    )
```

**Test functions** (8 total):

| # | Function | What It Verifies | Mock Response |
|---|---|---|---|
| 1 | `test_llm_client_success` | Returns insight text on 200 OK | 200, `{"choices":[{"message":{"content":"Insight gerado"}}]}` |
| 2 | `test_llm_client_missing_key` | `LLMClient(api_key=None)` raises `LLMUnavailableError` | No HTTP call |
| 3 | `test_llm_client_empty_key` | `LLMClient(api_key="")` raises `LLMUnavailableError` | No HTTP call |
| 4 | `test_llm_client_timeout` | Timeout (15s) raises `LLMUnavailableError` | Simulate timeout via `respx` |
| 5 | `test_llm_client_http_500` | Server error raises `LLMUnavailableError` | 500 |
| 6 | `test_llm_client_http_429` | Rate limit raises `LLMUnavailableError` | 429 |
| 7 | `test_build_prompt_sanitizes_none_wow` | `_build_prompt` converts `wow=None` to `"sem dados suficientes"` | No HTTP call (unit test on `_build_prompt`) |
| 8 | `test_build_prompt_includes_brl_formatting` | Monetary values use `R$ X.XXX,XX` format in prompt | Verify `fmt_brl` output appears in prompt string |

**Dependencies**: `respx` is a test-only dependency. Since the project uses a single `requirements.txt` for simplicity, add `respx>=0.21.0` alongside `pytest` in `requirements.txt`. Both are installed with `pip install -r requirements.txt`.

---

### 6.9 — Run Full Test Suite

**Command**:
```bash
cd /home/galvani/dev/radtracker
source venv/bin/activate
python -m pytest tests/ -v

# With coverage:
pip install pytest-cov
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

**Coverage targets**:
| Module | Minimum |
|---|---|
| `src/db.py` | ≥80% |
| `src/calculations.py` | ≥80% |
| `src/formatting.py` | ≥90% |
| `src/chart_colors.py` | ≥90% |
| `src/insights_rules.py` | ≥90% |
| `src/llm_client.py` | ≥80% |

**Dependencies**: 6.1–6.8 all complete.

---

### 6.10 — Write `README.md`

**File**: `README.md` (overwrite existing skeleton)

**Structure**:

```markdown
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

git clone <repo-url> radtracker
cd radtracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # opcional — para insights com IA

## Uso

streamlit run app.py          # http://localhost:8501

## IA (OpenRouter)

Para insights gerados por IA:
1. Crie uma conta gratuita em https://openrouter.ai
2. Gere uma API key
3. Adicione ao `.env`: `OPENROUTER_API_KEY=sk-or-v1-...`
4. Na aba "Análise", o insight será gerado por GPT-OSS 120B
5. Sem chave, o fallback baseado em regras é usado automaticamente

## Executando os testes

pip install pytest pytest-cov respx
python -m pytest tests/ -v
python -m pytest tests/ -v --cov=src --cov-report=term-missing

## Estrutura do projeto

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
├── tests/                  # Test suite
├── data/                   # SQLite DB (gitignored)
├── docs/                   # Sprint plans
├── requirements.txt
├── .env.example
└── README.md

## Stack

- Streamlit ≥1.54
- Pandas + NumPy
- Plotly
- SQLite (via SQLAlchemy)
- httpx (OpenRouter API)
- pytest + pytest-cov

## Licença

MIT
```

**Dependencies**: 6.9 (test suite must pass before README claims it does).

---

### 6.11 — Final `.gitignore` Audit

**File**: `.gitignore` (verify, not create from scratch)

**Checklist**:
- `.env` ✅ (already in .gitignore)
- `.streamlit/secrets.toml` ✅
- `data/*.db` ✅
- `data/app.log` ✅
- `__pycache__/` ✅
- `*.pyc` ✅
- `venv/` ✅
- `.DS_Store` ✅
- `.vscode/`, `.idea/` ✅
- `*.swp`, `*.swo` ✅

**Verification command**:
```bash
git ls-files --others --exclude-standard
# Should show: .env (gitignored), data/telerrad.db (gitignored)
# Should NOT show: any .pyc, __pycache__, venv/, secrets
```

**Dependencies**: None.

---

### 6.12 — Tag `v1.0.0` and Push

**Commands**:
```bash
git add tests/ README.md
git commit -m "test(sprint6): 88 test functions, >=80% coverage, README v1.0"
git tag v1.0.0 -m "Initial release: dashboard de produtividade para telerradiologia"
git push origin master --tags
```

**Dependencies**: 6.1–6.11 all complete.

---

## 4. Implementation Order

```
6.1 (tests/__init__.py)   ← independent
6.2 (conftest.py)         ← independent
6.6 (test_formatting)     ← independent (parallel with 6.3 after 6.2)
6.7 (test_chart_colors)   ← independent (parallel with 6.3 after 6.2)
6.3 (test_db.py)          ← depends on 6.2
6.4 (test_calculations)   ← depends on 6.2
6.5 (test_insights)       ← independent (pure function, no fixtures needed)
6.8 (test_llm_client)     ← independent (mock httpx, no DB fixtures)
6.9 (coverage run)        ← depends on 6.3, 6.4, 6.5, 6.6, 6.7, 6.8
6.10 (README.md)          ← depends on 6.9
6.11 (gitignore audit)    ← independent
6.12 (tag + push)         ← depends on all
```

**Parallel opportunities**: 6.6, 6.7, 6.5, 6.8 can all be written simultaneously after 6.2 is done.

---

## 5. Test Execution

```bash
# All tests
python -m pytest tests/ -v

# With coverage
pip install pytest-cov respx
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Specific module
python -m pytest tests/test_db.py -v

# Fail fast on first error
python -m pytest tests/ -v -x
```

---

## 6. Files Created

| File | Lines (est.) | Description |
|---|---|---|
| `tests/__init__.py` | 1 | Package marker |
| `tests/conftest.py` | ~60 | FakeConnection + conn fixture + default_prices fixture |
| `tests/test_db.py` | ~200 | 15 tests for CRUD, schema, defaults |
| `tests/test_calculations.py` | ~350 | 33 tests for earnings, stats, MA, WoW, MoM |
| `tests/test_insights.py` | ~250 | 19 tests for 4 tones, trends, mix shifts |
| `tests/test_formatting.py` | ~80 | 8 tests for fmt_brl edge cases |
| `tests/test_chart_colors.py` | ~50 | 5 tests for hex_to_rgba, palette keys |
| `tests/test_llm_client.py` | ~150 | 8 tests with mocked httpx |

**Total**: ~1141 lines of test code across 8 files.

---

## 7. Definition of Done

- [ ] `python -m pytest tests/ -v` exits with **0 failures**
- [ ] Test coverage ≥80% on `src/db.py`, `src/calculations.py`, `src/insights_rules.py`, `src/llm_client.py`
- [ ] Test coverage ≥90% on `src/formatting.py`, `src/chart_colors.py`
- [ ] `README.md` rewritten with: features, install, IA setup, test commands, project structure, stack
- [ ] `.gitignore` audit passes: `git ls-files --others --exclude-standard` shows only gitignored files
- [ ] `git tag v1.0.0` created with descriptive message
- [ ] All `py_compile` checks clean: `python -m py_compile app.py src/*.py src/ui/*.py`
- [ ] No hardcoded secrets in any committed file
- [ ] `tests/conftest.py` schema DDL matches `src/db.py init_db` DDL exactly

---

## 8. Risk Log

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `respx` version incompatibility with `httpx` | Low (15%) | Low — only affects llm_client tests | Pin `respx>=0.21.0` compatible with httpx in test instructions |
| R2 | Schema DDL drift between `init_db` and test fixtures | Medium (30%) | Medium — tests pass but don't validate real schema | Export DDL from `init_db` into `conftest.py` as string constants; document that both must match |
| R3 | `pytest-cov` reports misleading coverage (import-time lines) | Low (10%) | Low — cosmetic | Focus on `term-missing` output, not aggregate %. The 80% threshold is a goal, not a hard gate |
| R4 | `FakeConnection.query()` behavior differs from `st.connection` for edge cases | Medium (25%) | Medium — tests pass but behavior differs in Streamlit | Test with `load_daily`, `load_month`, `load_prices`, `load_goal` which cover the 4 query patterns used |
| R5 | Brazilian Real formatting locale-dependent (Python `,` vs `.`) | Very low (<5%) | Low | `fmt_brl` explicitly uses `.` for thousands and `,` for decimal — no locale dependency |
