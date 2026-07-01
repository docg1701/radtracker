"""
Shared fixtures for radtracker test suite — v2.

Provides FakeConnection (emulates st.connection with SQLite :memory:)
and a conn fixture with full schema ready for testing.
"""

import pandas as pd
import pytest
import sqlalchemy as sa

DB_CREATE_SQL = [
    # v1 tables (kept for migration tests)
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
    # v2 tables
    """
    CREATE TABLE IF NOT EXISTS modalities (
        slug            TEXT PRIMARY KEY,
        label           TEXT NOT NULL,
        price           REAL NOT NULL DEFAULT 0.0,
        exams_per_hour  REAL NOT NULL DEFAULT 0.0,
        active          INTEGER NOT NULL DEFAULT 0,
        color           TEXT NOT NULL DEFAULT '#64748B',
        sort_order      INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_production_items (
        date            TEXT NOT NULL,
        modality_slug   TEXT NOT NULL,
        count           INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (date, modality_slug),
        FOREIGN KEY (modality_slug) REFERENCES modalities(slug)
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
    """
    CREATE TABLE IF NOT EXISTS modality_prices (
        slug            TEXT NOT NULL,
        price           REAL NOT NULL,
        effective_from  TEXT NOT NULL,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (slug, effective_from)
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
        """Returns a SQLAlchemy connection."""
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


@pytest.fixture
def seeded_conn(conn):
    """Return a connection with 5 modalities seeded with production values."""
    from src.db import _seed_modalities
    _seed_modalities(conn)
    return conn


@pytest.fixture
def active_modalities():
    """Return a list of 5 active modality dicts (like from load_active_modalities)."""
    return [
        {"slug": "angiotomografia", "label": "Angiotomografia",
         "price": 30.0, "exams_per_hour": 4.0, "active": 1, "sort_order": 1,
         "color": "#0D9488"},
        {"slug": "radiografia", "label": "Radiografia",
         "price": 4.0, "exams_per_hour": 80.0, "active": 1, "sort_order": 2,
         "color": "#2563EB"},
        {"slug": "ressonancia_magnetica", "label": "Ressonância Magnética",
         "price": 35.0, "exams_per_hour": 8.0, "active": 1, "sort_order": 3,
         "color": "#7C3AED"},
        {"slug": "tc_abdome_total", "label": "TC de Abdome Total",
         "price": 60.0, "exams_per_hour": 5.0, "active": 1, "sort_order": 5,
         "color": "#0891B2"},
        {"slug": "tc_geral", "label": "TC Geral",
         "price": 30.0, "exams_per_hour": 10.0, "active": 1, "sort_order": 4,
         "color": "#6366F1"},
    ]
