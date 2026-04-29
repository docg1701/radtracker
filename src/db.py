"""
Database module — SQLite schema, connection, and CRUD operations.

Uses Streamlit's st.connection for managed SQLite access.
"""

import os
from datetime import date
from typing import Any

import pandas as pd
import sqlalchemy as sa
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
    os.makedirs("data", exist_ok=True)
    with conn.connect() as db_conn:
        db_conn.execute(sa.text(create_daily))
        db_conn.execute(sa.text(create_prices))
        db_conn.execute(sa.text(create_goals))
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
        db_conn.execute(sa.text(upsert_sql), {"date": date_str, "rm": rm, "tc": tc, "rx": rx})
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
            sa.text("""
                INSERT INTO exam_prices (rm_price, tc_price, rx_price, effective_from)
                VALUES (:rm, :tc, :rx, :eff)
            """),
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
            sa.text("""
            INSERT INTO monthly_goals (year_month, goal_reais, updated_at)
            VALUES (:ym, :goal, datetime('now','localtime'))
            ON CONFLICT(year_month) DO UPDATE SET
                goal_reais = excluded.goal_reais,
                updated_at = datetime('now','localtime')
            """),
            {"ym": year_month, "goal": goal},
        )
        db_conn.commit()
