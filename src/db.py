"""
Database module — SQLite schema, connection, and CRUD operations.

Uses Streamlit's st.connection for managed SQLite access.
v2: dynamic modalities replacing hardcoded RM/TC/RX.
"""

import os
from datetime import date
from typing import Any

import pandas as pd
import sqlalchemy as sa
import streamlit as st

DEFAULT_PRICES: dict[str, float] = {
    "ressonancia_magnetica": 35.0,
    "tc_geral": 25.0,
    "radiografia": 4.5,
}
DEFAULT_GOAL: float = 45000.0
DEFAULT_LLM_MODEL: str = "openai/gpt-oss-120b:free"

# ── Predefined modality catalog (11 items) ──
_MODALITY_SEED: list[dict[str, Any]] = [
    {"slug": "tc_abdome_total", "label": "TC de Abdome Total", "sort_order": 1},
    {"slug": "tc_geral", "label": "TC Geral", "sort_order": 2},
    {"slug": "angiotomografia", "label": "Angiotomografia", "sort_order": 3},
    {"slug": "ressonancia_magnetica", "label": "Ressonância Magnética", "sort_order": 4},
    {"slug": "ultrassonografia", "label": "Ultrassonografia", "sort_order": 5},
    {"slug": "dopplervelocimetria", "label": "Dopplervelocimetria", "sort_order": 6},
    {"slug": "mamografia", "label": "Mamografia", "sort_order": 7},
    {"slug": "radiografia", "label": "Radiografia", "sort_order": 8},
    {"slug": "radiografia_contrastada", "label": "Radiografia Contrastada", "sort_order": 9},
    {"slug": "ultrassom_morfologico", "label": "Ultrassom Morfológico", "sort_order": 10},
    {"slug": "densitometria", "label": "Densitometria", "sort_order": 11},
]


def get_connection() -> Any:
    """Return a Streamlit SQL connection to the local SQLite database."""
    return st.connection(
        "telerrad",
        type="sql",
        url="sqlite:///data/telerrad.db",
    )


def init_db(conn: Any) -> None:
    """Create all tables if they don't exist. Idempotent.

    v2 tables: modalities, daily_production_items.
    v1 tables: daily_production, exam_prices (kept for migration).
    """
    # ── v1 tables (kept for migration) ──
    create_daily_v1 = """
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

    # ── v2 tables ──
    create_modalities = """
    CREATE TABLE IF NOT EXISTS modalities (
        slug            TEXT PRIMARY KEY,
        label           TEXT NOT NULL,
        price           REAL NOT NULL DEFAULT 0.0,
        exams_per_hour  REAL NOT NULL DEFAULT 0.0,
        active          INTEGER NOT NULL DEFAULT 0,
        sort_order      INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """
    create_daily_items = """
    CREATE TABLE IF NOT EXISTS daily_production_items (
        date            TEXT NOT NULL,
        modality_slug   TEXT NOT NULL,
        count           INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (date, modality_slug),
        FOREIGN KEY (modality_slug) REFERENCES modalities(slug)
    );
    """
    create_goals = """
    CREATE TABLE IF NOT EXISTS monthly_goals (
        year_month  TEXT PRIMARY KEY,
        goal_reais  REAL NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """
    create_settings = """
    CREATE TABLE IF NOT EXISTS user_settings (
        key         TEXT PRIMARY KEY,
        value       TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """

    os.makedirs("data", exist_ok=True)
    with conn.connect() as db_conn:
        db_conn.execute(sa.text(create_daily_v1))
        db_conn.execute(sa.text(create_prices))
        db_conn.execute(sa.text(create_modalities))
        db_conn.execute(sa.text(create_daily_items))
        db_conn.execute(sa.text(create_goals))
        db_conn.execute(sa.text(create_settings))
        db_conn.commit()

    # Seed modalities if table is empty
    _seed_modalities(conn)
    # Run v1→v2 migration if needed
    _migrate_v1_to_v2(conn)


# ---------------------------------------------------------------------------
# v2: Modalities CRUD
# ---------------------------------------------------------------------------

def load_all_modalities(conn: Any) -> list[dict[str, Any]]:
    """Return all 11 modalities ordered by sort_order. Always 11 rows.

    Each dict: slug, label, price, exams_per_hour, active, sort_order.
    """
    df = conn.query(
        "SELECT slug, label, price, exams_per_hour, active, sort_order "
        "FROM modalities ORDER BY sort_order",
        ttl=0,
    )
    return df.to_dict("records")


def load_active_modalities(conn: Any) -> list[dict[str, Any]]:
    """Return modalities that are active AND have price>0 AND exams_per_hour>0.

    These appear in sidebar and dashboards.
    """
    df = conn.query(
        "SELECT slug, label, price, exams_per_hour, active, sort_order "
        "FROM modalities "
        "WHERE active = 1 AND price > 0 AND exams_per_hour > 0 "
        "ORDER BY sort_order",
        ttl=0,
    )
    return df.to_dict("records")


def save_modality(
    conn: Any, slug: str, price: float, exams_per_hour: float, active: int
) -> None:
    """Update price, exams_per_hour, and active flag for a single modality."""
    with conn.connect() as db_conn:
        db_conn.execute(
            sa.text("""
                UPDATE modalities
                SET price = :price,
                    exams_per_hour = :eph,
                    active = :active,
                    updated_at = datetime('now','localtime')
                WHERE slug = :slug
            """),
            {"slug": slug, "price": price, "eph": exams_per_hour, "active": active},
        )
        db_conn.commit()


# ---------------------------------------------------------------------------
# v2: Daily production items CRUD
# ---------------------------------------------------------------------------

def upsert_daily_items(conn: Any, date_str: str, items: dict[str, int]) -> None:
    """Insert or update daily production counts for multiple modalities.

    Args:
        date_str: ISO date string (e.g. "2026-05-02").
        items: Dict mapping modality_slug → count. Only non-zero counts
               should be present (zeroes are skipped — they represent
               nothing to save).
    """
    if not items:
        return
    with conn.connect() as db_conn:
        for slug, count in items.items():
            db_conn.execute(
                sa.text("""
                    INSERT INTO daily_production_items
                        (date, modality_slug, count, updated_at)
                    VALUES (:date, :slug, :count, datetime('now','localtime'))
                    ON CONFLICT(date, modality_slug) DO UPDATE SET
                        count = excluded.count,
                        updated_at = datetime('now','localtime')
                """),
                {"date": date_str, "slug": slug, "count": count},
            )
        db_conn.commit()


def load_daily_items(conn: Any, date_str: str) -> dict[str, int]:
    """Return a dict of slug→count for a given date. Empty dict if no data.

    Example:
        >>> items = load_daily_items(conn, "2026-05-02")
        >>> items.get("ressonancia_magnetica", 0)
        8
    """
    df = conn.query(
        "SELECT modality_slug, count FROM daily_production_items WHERE date = :date",
        params={"date": date_str},
        ttl=0,
    )
    if df.empty:
        return {}
    return dict(zip(df["modality_slug"], df["count"].astype(int)))


def load_month_items(conn: Any, year_month: str) -> pd.DataFrame:
    """Return all daily_production_items rows for a year-month (e.g. '2026-04').

    Columns: date, modality_slug, count.
    """
    return conn.query(
        "SELECT date, modality_slug, count "
        "FROM daily_production_items "
        "WHERE date LIKE :prefix ORDER BY date, modality_slug",
        params={"prefix": f"{year_month}%"},
        ttl=0,
    )


# ---------------------------------------------------------------------------
# v1 (legacy) — kept for migration
# ---------------------------------------------------------------------------

def upsert_daily(conn: Any, date_str: str, rm: int, tc: int, rx: int) -> None:
    """v1: Insert or update a daily production row. On conflict, overwrites counts."""
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
    """v1: Return the daily production row as a dict, or None if no data."""
    df = conn.query(
        "SELECT * FROM daily_production WHERE date = :date",
        params={"date": date_str},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def load_month(conn: Any, year_month: str) -> pd.DataFrame:
    """v1: Return all daily production rows for a year-month."""
    return conn.query(
        "SELECT * FROM daily_production WHERE date LIKE :prefix ORDER BY date",
        params={"prefix": f"{year_month}%"},
        ttl=0,
    )


def load_prices(conn: Any) -> dict[str, float]:
    """Return current exam prices as slug→price from active modalities.

    Falls back to DEFAULT_PRICES if no active modalities exist.
    """
    active = load_active_modalities(conn)
    if not active:
        return dict(DEFAULT_PRICES)
    return {m["slug"]: float(m["price"]) for m in active}


def save_prices(conn: Any, rm_price: float, tc_price: float, rx_price: float) -> None:
    """v1: Append a new price configuration row. Kept for backward compat."""
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


# ---------------------------------------------------------------------------
# Goals + Settings (unchanged keys)
# ---------------------------------------------------------------------------

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
    """UPSERT monthly goal."""
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


def load_setting(conn: Any, key: str, default: str = "") -> str:
    """Return a user setting value by key, falling back to default."""
    df = conn.query(
        "SELECT value FROM user_settings WHERE key = :key",
        params={"key": key},
        ttl=0,
    )
    if df.empty:
        return default
    return str(df.iloc[0]["value"])


def save_setting(conn: Any, key: str, value: str) -> None:
    """UPSERT a user setting key/value pair."""
    with conn.connect() as db_conn:
        db_conn.execute(
            sa.text("""
            INSERT INTO user_settings (key, value, updated_at)
            VALUES (:key, :value, datetime('now','localtime'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now','localtime')
            """),
            {"key": key, "value": value},
        )
        db_conn.commit()


# ---------------------------------------------------------------------------
# Private: seed + migration
# ---------------------------------------------------------------------------

def _seed_modalities(conn: Any) -> None:
    """Insert the 11 predefined modalities if the table is empty."""
    existing = conn.query("SELECT COUNT(*) AS cnt FROM modalities", ttl=0)
    if existing["cnt"].iloc[0] > 0:
        return
    with conn.connect() as db_conn:
        for m in _MODALITY_SEED:
            db_conn.execute(
                sa.text("""
                    INSERT OR IGNORE INTO modalities
                        (slug, label, price, exams_per_hour, active, sort_order)
                    VALUES (:slug, :label, 0.0, 0.0, 0, :sort_order)
                """),
                {"slug": m["slug"], "label": m["label"], "sort_order": m["sort_order"]},
            )
        db_conn.commit()


def _migrate_v1_to_v2(conn: Any) -> None:
    """One-shot migration: v1 daily_production → v2 daily_production_items.

    Only runs if v1 has data and v2 is empty. Migrates RM→ressonancia_magnetica,
    TC→tc_geral, RX→radiografia. Copies latest prices from exam_prices.
    """
    v1_count = conn.query("SELECT COUNT(*) AS cnt FROM daily_production", ttl=0)
    if v1_count["cnt"].iloc[0] == 0:
        return

    v2_count = conn.query(
        "SELECT COUNT(*) AS cnt FROM daily_production_items", ttl=0
    )
    if v2_count["cnt"].iloc[0] > 0:
        return  # Already migrated

    # Copy exam counts
    df_v1 = conn.query(
        "SELECT date, rm_count, tc_count, rx_count FROM daily_production ORDER BY date",
        ttl=0,
    )
    with conn.connect() as db_conn:
        for _, row in df_v1.iterrows():
            for slug, col in [
                ("ressonancia_magnetica", "rm_count"),
                ("tc_geral", "tc_count"),
                ("radiografia", "rx_count"),
            ]:
                count = int(row[col])
                if count > 0:
                    db_conn.execute(
                        sa.text("""
                            INSERT INTO daily_production_items
                                (date, modality_slug, count)
                            VALUES (:date, :slug, :count)
                            ON CONFLICT(date, modality_slug) DO UPDATE SET
                                count = excluded.count
                        """),
                        {"date": row["date"], "slug": slug, "count": count},
                    )
        db_conn.commit()

    # Copy latest prices and activate migrated modalities
    prices_df = conn.query(
        "SELECT rm_price, tc_price, rx_price FROM exam_prices ORDER BY id DESC LIMIT 1",
        ttl=0,
    )
    if not prices_df.empty:
        row = prices_df.iloc[0]
        price_map = {
            "ressonancia_magnetica": (float(row["rm_price"]), 7.5),
            "tc_geral": (float(row["tc_price"]), 7.5),
            "radiografia": (float(row["rx_price"]), 75.0),
        }
        with conn.connect() as db_conn:
            for slug, (price, eph) in price_map.items():
                db_conn.execute(
                    sa.text("""
                        UPDATE modalities
                        SET price = :price,
                            exams_per_hour = :eph,
                            active = 1,
                            updated_at = datetime('now','localtime')
                        WHERE slug = :slug
                    """),
                    {"slug": slug, "price": price, "eph": eph},
                )
            db_conn.commit()
