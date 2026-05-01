"""
Shared fixtures for radtracker test suite.

Provides FakeConnection (emulates st.connection with SQLite :memory:)
and a conn fixture with full schema ready for testing.
"""

import pandas as pd
import pytest
import sqlalchemy as sa

DB_CREATE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS daily_production (
        date        TEXT PRIMARY KEY,
        rm_count    INTEGER NOT NULL DEFAULT 0,
        tc_count    INTEGER NOT NULL DEFAULT 0,
        rx_count    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_prices (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_price        REAL NOT NULL,
        tc_price        REAL NOT NULL,
        rx_price        REAL NOT NULL,
        effective_from  TEXT NOT NULL,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS monthly_goals (
        year_month  TEXT PRIMARY KEY,
        goal_reais  REAL NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        key         TEXT PRIMARY KEY,
        value       TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
]


class FakeConnection:
    """Emulates st.connection('telerrad', type='sql') with SQLite :memory:."""

    def __init__(self) -> None:
        self._engine = sa.create_engine(
            "sqlite:///:memory:",
            poolclass=sa.pool.StaticPool,
            connect_args={"check_same_thread": False},
        )

    def connect(self) -> sa.engine.Connection:
        """Returns a SQLAlchemy connection (context-manager compatible)."""
        return self._engine.connect()  # type: ignore[return-value]

    def query(self, sql: str, *, params: dict | None = None, ttl: int = 0) -> pd.DataFrame:
        """Executes a SELECT query, returns a pandas DataFrame."""
        with self._engine.connect() as c:
            result = c.execute(sa.text(sql), params or {})
            rows = result.fetchall()
            cols = result.keys()
        return pd.DataFrame(rows, columns=cols)


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
    """Return a copy of DEFAULT_PRICES dict from src.db."""
    from src.db import DEFAULT_PRICES
    return dict(DEFAULT_PRICES)
