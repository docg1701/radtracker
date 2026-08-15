"""
Shared fixtures for radtracker test suite — v2.

Provides FakeConnection (emulates st.connection with SQLite :memory:)
and a conn fixture with full schema ready for testing.
"""

import pytest
import sqlalchemy as sa

from src.db import SCHEMA_DDL, SqliteConn, _add_color_column


class FakeConnection(SqliteConn):
    """Emulates st.connection('telerrad', type='sql') with SQLite :memory:."""

    def __init__(self) -> None:
        # StaticPool keeps a single in-memory DB alive across .connect() calls.
        self._engine = sa.create_engine(
            "sqlite:///:memory:",
            poolclass=sa.pool.StaticPool,
            connect_args={"check_same_thread": False},
        )


@pytest.fixture
def conn():
    """Return a FakeConnection with full schema, ready for testing."""
    fc = FakeConnection()
    with fc.connect() as c:
        for ddl in SCHEMA_DDL:
            c.execute(sa.text(ddl))
        c.commit()
    _add_color_column(fc)  # init_db parity: color column + backfill
    return fc


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
