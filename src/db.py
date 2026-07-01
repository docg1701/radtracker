"""
Database module — SQLite schema, connection, and CRUD operations.

Uses Streamlit's st.connection for managed SQLite access.
v2: dynamic modalities replacing hardcoded RM/TC/RX.
"""

import os
import re
import unicodedata
from datetime import date
from typing import Any

import pandas as pd
import sqlalchemy as sa
import streamlit as st

from src.chart_colors import MODALITY_COLORS

DEFAULT_GOAL: float = 45000.0
DEFAULT_LLM_MODEL: str = "openai/gpt-oss-120b:free"

# ── Predefined modality catalog (5 production modalities) ──
_MODALITY_SEED: list[dict[str, Any]] = [
    {"slug": "angiotomografia",  "label": "Angiotomografia",
     "sort_order": 1, "color": "#0D9488"},
    {"slug": "radiografia",  "label": "Radiografia",
     "sort_order": 2, "color": "#2563EB"},
    {"slug": "ressonancia_magnetica",  "label": "Ressonância Magnética",
     "sort_order": 3, "color": "#7C3AED"},
    {"slug": "tc_geral",  "label": "TC Geral",
     "sort_order": 4, "color": "#6366F1"},
    {"slug": "tc_abdome_total",  "label": "TC de Abdome Total",
     "sort_order": 5, "color": "#0891B2"},
]

# Production default values for the 5 standard modalities.
_PRODUCTION_DEFAULTS: dict[str, tuple[str, float, float]] = {
    "angiotomografia":       ("Angiotomografia",       30.00, 4.0),
    "radiografia":           ("Radiografia",            4.00, 80.0),
    "ressonancia_magnetica": ("Ressonância Magnética", 35.00, 8.0),
    "tc_geral":              ("TC Geral",              30.00, 10.0),
    "tc_abdome_total":       ("TC de Abdome Total",    60.00, 5.0),
}


def get_connection() -> Any:
    """Return a Streamlit SQL connection to the local SQLite database."""
    return st.connection(
        "telerrad",
        type="sql",
        url="sqlite:///data/telerrad.db",
    )


def init_db(conn: Any) -> None:
    """Create all tables if they don't exist. Idempotent.

    Tables: modalities, daily_production_items, modality_prices,
    monthly_goals, user_settings.
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
    create_modality_prices = """
    CREATE TABLE IF NOT EXISTS modality_prices (
        slug            TEXT NOT NULL,
        price           REAL NOT NULL,
        effective_from  TEXT NOT NULL,
        created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (slug, effective_from)
    );
    """

    os.makedirs("data", exist_ok=True)
    with conn.connect() as db_conn:
        db_conn.execute(sa.text(create_modalities))
        db_conn.execute(sa.text(create_daily_items))
        db_conn.execute(sa.text(create_goals))
        db_conn.execute(sa.text(create_settings))
        db_conn.execute(sa.text(create_modality_prices))
        db_conn.commit()

    # Add color column if missing (must run before seed so seed can set colors)
    _add_color_column(conn)
    # Seed modalities if table is empty
    _seed_modalities(conn)
    # Apply v1.4 production defaults to untouched modalities
    _migrate_v1_3_to_v1_4_defaults(conn)
    # Backfill price vigencies (one-shot) so the past is immutable
    _backfill_price_vigencies(conn)
    # Drop v1 legacy tables once v2 is populated (one-shot, guarded)
    _migrate_v1_cleanup(conn)
    # Seed reasoning settings for thinking/temperature configuration
    _seed_reasoning_settings(conn)


# ---------------------------------------------------------------------------
# v2: Modalities CRUD
# ---------------------------------------------------------------------------

def slugify(label: str) -> str:
    """Convert a human-readable label into a URL-safe slug.

    'Ressonância Magnética' → 'ressonancia_magnetica'
    'TC de Abdome Total'    → 'tc_de_abdome_total'

    Returns 'modalidade' if the result would be empty.

    Example:
        >>> slugify("Ressonância Magnética")
        'ressonancia_magnetica'
    """
    value = unicodedata.normalize("NFKD", label.strip().lower())
    value = value.encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "modalidade"


def load_all_modalities(conn: Any) -> list[dict[str, Any]]:
    """Return all modalities ordered by label (case-insensitive).

    Each dict: slug, label, price, exams_per_hour, active, sort_order, color.
    """
    df = conn.query(
        "SELECT slug, label, price, exams_per_hour, active, sort_order, color "
        "FROM modalities ORDER BY label COLLATE NOCASE",
        ttl=0,
    )
    return df.to_dict("records")


def load_active_modalities(conn: Any) -> list[dict[str, Any]]:
    """Return modalities that are active AND have price>0 AND exams_per_hour>0.

    These appear in sidebar and dashboards.
    """
    df = conn.query(
        "SELECT slug, label, price, exams_per_hour, active, sort_order, color "
        "FROM modalities "
        "WHERE active = 1 AND price > 0 AND exams_per_hour > 0 "
        "ORDER BY label COLLATE NOCASE",
        ttl=0,
    )
    return df.to_dict("records")


def save_modality(
    conn: Any, slug: str, price: float, exams_per_hour: float, active: int,
    label: str | None = None,
    color: str | None = None,
) -> None:
    """Update price, exams_per_hour, active flag, and optionally label and color.

    When label is None (default), the label column is left unchanged.
    When color is None (default), the color column is left unchanged.
    """
    # Read the current price first so we only record a new vigency on a real
    # price change (label/color/active edits must NOT rewrite price history).
    before = conn.query(
        "SELECT price FROM modalities WHERE slug = :slug",
        params={"slug": slug}, ttl=0,
    )
    old_price = float(before.iloc[0]["price"]) if not before.empty else None

    set_clauses = [
        "price = :price",
        "exams_per_hour = :eph",
        "active = :active",
        "updated_at = datetime('now','localtime')",
    ]
    params: dict[str, Any] = {
        "slug": slug, "price": price, "eph": exams_per_hour, "active": active,
    }
    if label is not None:
        set_clauses.append("label = :label")
        params["label"] = label
    if color is not None:
        set_clauses.append("color = :color")
        params["color"] = color

    with conn.connect() as db_conn:
        db_conn.execute(
            sa.text(f"UPDATE modalities SET {', '.join(set_clauses)} WHERE slug = :slug"),
            params,
        )
        db_conn.commit()

    # A real price change opens a new vigency from today; the past keeps its
    # own vigency and is never recomputed.
    new_price = float(price)
    if (
        old_price is not None
        and new_price > 0
        and abs(new_price - old_price) > 0.001
    ):
        save_price_vigency(conn, slug, new_price, date.today().isoformat())


def add_modality(
    conn: Any, slug: str, label: str, price: float, exams_per_hour: float,
    active: int, color: str = "#64748B",
) -> bool:
    """Insert a new modality, or reactivate an inactive one with the same slug.

    A brand-new slug gets sort_order = MAX(sort_order) + 1. If the slug already
    exists, an ACTIVE row is left untouched (returns False); an INACTIVE row is
    reactivated with the new label/price/eph/color (returns True), preserving all
    production history under that slug.

    Example:
        >>> add_modality(conn, "tomografia_cranio", "Tomografia de Crânio", 25.0, 5.0, 1)
        True
    """
    with conn.connect() as db_conn:
        existing = db_conn.execute(
            sa.text("SELECT active FROM modalities WHERE slug = :slug"),
            {"slug": slug},
        )
        row = existing.fetchone()
        if row is not None:
            if bool(row[0]):
                # Already active — do not overwrite an in-use modality.
                return False
            # Inactive — reactivate with the new values, keeping production history.
            db_conn.execute(
                sa.text("""
                    UPDATE modalities
                    SET label = :label, price = :price, exams_per_hour = :eph,
                        active = :active, color = :color,
                        updated_at = datetime('now','localtime')
                    WHERE slug = :slug
                """),
                {"slug": slug, "label": label, "price": price,
                 "eph": exams_per_hour, "active": active, "color": color},
            )
            db_conn.commit()
            return True

        # New slug — insert with the next sort_order.
        result = db_conn.execute(
            sa.text("SELECT COALESCE(MAX(sort_order), 0) AS mx FROM modalities"),
        )
        mx_row = result.fetchone()
        next_order = (mx_row[0] if mx_row else 0) + 1

        db_conn.execute(
            sa.text("""
                INSERT INTO modalities
                    (slug, label, price, exams_per_hour, active, sort_order, color)
                VALUES (:slug, :label, :price, :eph, :active, :sort_order, :color)
            """),
            {
                "slug": slug, "label": label, "price": price,
                "eph": exams_per_hour, "active": active,
                "sort_order": next_order, "color": color,
            },
        )
        db_conn.commit()
    return True


def deactivate_modality(conn: Any, slug: str) -> bool:
    """Soft-delete a modality: mark it inactive, preserving all production history.

    The row stays in `modalities` (so the slug stays reserved and the modality
    can be reactivated later by adding it again) and `daily_production_items` is
    never touched. Returns True if the modality existed, False otherwise.

    Example:
        >>> deactivate_modality(conn, "tc_abdome_total")
        True
    """
    with conn.connect() as db_conn:
        result = db_conn.execute(
            sa.text("SELECT COUNT(*) AS cnt FROM modalities WHERE slug = :slug"),
            {"slug": slug},
        )
        row = result.fetchone()
        if not row or row[0] == 0:
            return False
        db_conn.execute(
            sa.text(
                "UPDATE modalities SET active = 0, "
                "updated_at = datetime('now','localtime') WHERE slug = :slug"
            ),
            {"slug": slug},
        )
        db_conn.commit()
    return True


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
            if count == 0:
                db_conn.execute(
                    sa.text(
                        "DELETE FROM daily_production_items "
                        "WHERE date = :date AND modality_slug = :slug"
                    ),
                    {"date": date_str, "slug": slug},
                )
            else:
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
# Goals + Settings (unchanged keys)
# ---------------------------------------------------------------------------

def load_goal(conn: Any, year_month: str) -> float:
    """Return monthly goal for a year-month with carry-forward semantics.

    If no row exists for ``year_month``, returns the goal from the most recent
    prior month that has one, so the previous month's goal persists across a
    month turnover. Falls back to DEFAULT_GOAL only when no goal has ever been
    recorded.

    Example:
        >>> save_goal(conn, "2026-05", 50000.0)
        >>> load_goal(conn, "2026-06")  # June has no row → carries May's 50000
        50000.0
    """
    df = conn.query(
        "SELECT goal_reais FROM monthly_goals WHERE year_month = :ym",
        params={"ym": year_month},
        ttl=0,
    )
    if not df.empty:
        return float(df.iloc[0]["goal_reais"])

    # Carry-forward: most recent prior month with a goal (never a future one).
    prior = conn.query(
        "SELECT goal_reais FROM monthly_goals "
        "WHERE year_month < :ym ORDER BY year_month DESC LIMIT 1",
        params={"ym": year_month},
        ttl=0,
    )
    if not prior.empty:
        return float(prior.iloc[0]["goal_reais"])

    return DEFAULT_GOAL


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
# v2.1: Price vigency (modality_prices)
# ---------------------------------------------------------------------------

def save_price_vigency(conn: Any, slug: str, price: float, effective_from: str) -> None:
    """UPSERT a price-vigency row: `price` valid for `slug` from `effective_from`.

    A price change creates a new vigency from today; the past keeps the previous
    vigency. On conflict (slug, effective_from) the price is updated.

    Example:
        >>> save_price_vigency(conn, "tc_geral", 30.0, "2026-07-01")
    """
    with conn.connect() as db_conn:
        db_conn.execute(
            sa.text("""
                INSERT INTO modality_prices (slug, price, effective_from, created_at)
                VALUES (:slug, :price, :eff, datetime('now','localtime'))
                ON CONFLICT(slug, effective_from) DO UPDATE SET
                    price = excluded.price
            """),
            {"slug": slug, "price": price, "eff": effective_from},
        )
        db_conn.commit()


def load_prices_at(conn: Any, date_str: str) -> dict[str, float]:
    """Return slug->price valid at `date_str` (most recent vigency <= date).

    Slugs without any vigency are omitted (caller treats missing as 0). If a
    slug has vigencies but none <= date_str, the oldest one is used as fallback.

    Example:
        >>> load_prices_at(conn, "2026-03-15")
        {'tc_geral': 25.0, 'ressonancia_magnetica': 35.0}
    """
    df = conn.query(
        "SELECT slug, effective_from, price FROM modality_prices",
        ttl=0,
    )
    if df.empty:
        return {}
    result: dict[str, float] = {}
    for slug, grp in df.groupby("slug"):
        prior = grp[grp["effective_from"] <= date_str]
        if not prior.empty:
            best = prior.loc[prior["effective_from"].idxmax()]
        else:
            best = grp.loc[grp["effective_from"].idxmin()]
        result[str(slug)] = float(best["price"])
    return result


def load_price_vigencies(conn: Any) -> list[dict[str, Any]]:
    """Return all price-vigency rows ordered by slug, effective_from."""
    df = conn.query(
        "SELECT slug, effective_from, price FROM modality_prices "
        "ORDER BY slug, effective_from",
        ttl=0,
    )
    return df.to_dict("records")


# ---------------------------------------------------------------------------
# Private: seed + migration
# ---------------------------------------------------------------------------

def _backfill_price_vigencies(conn: Any) -> None:
    """One-shot: seed modality_prices with each modality's current price, valid
    since its first production record (or its created_at when it has no items).

    Idempotent: skips when any vigency already exists. The user confirmed the
    current prices are the real prices practiced since the start of the year, so
    freezing them as the historical vigency preserves the past from being
    recalculated when a price is later changed.

    Example:
        >>> _backfill_price_vigencies(conn)  # first run seeds all modalities
    """
    existing = conn.query("SELECT DISTINCT slug FROM modality_prices", ttl=0)
    if not existing.empty:
        return
    mods = conn.query("SELECT slug, price, created_at FROM modalities", ttl=0)
    if mods.empty:
        return
    items = conn.query(
        "SELECT modality_slug AS slug, MIN(date) AS first_date "
        "FROM daily_production_items GROUP BY modality_slug",
        ttl=0,
    )
    first_by_slug: dict[str, str] = {}
    if not items.empty:
        first_by_slug = dict(zip(items["slug"].astype(str), items["first_date"].astype(str)))
    with conn.connect() as db_conn:
        for _, m in mods.iterrows():
            slug = str(m["slug"])
            price = float(m["price"])
            if price <= 0:
                continue
            eff = first_by_slug.get(slug) or str(m["created_at"])[:10]
            db_conn.execute(
                sa.text("""
                    INSERT OR IGNORE INTO modality_prices
                        (slug, price, effective_from, created_at)
                    VALUES (:slug, :price, :eff, datetime('now','localtime'))
                """),
                {"slug": slug, "price": price, "eff": eff},
            )
        db_conn.commit()


def _seed_reasoning_settings(conn: Any) -> None:
    """Seed reasoning-related user_settings if absent. Idempotent.

    Called from init_db() after tables are created.
    """
    defaults = [
        ("thinking_enabled", "1"),
        ("thinking_effort", "high"),
        ("thinking_budget", ""),        # empty = budget not set
        ("temperature", "0.3"),
    ]
    for key, default in defaults:
        if not load_setting(conn, key):
            save_setting(conn, key, default)


def _seed_modalities(conn: Any) -> None:
    """Insert the 5 predefined modalities with production values if the table is empty."""
    existing = conn.query("SELECT COUNT(*) AS cnt FROM modalities", ttl=0)
    if existing["cnt"].iloc[0] > 0:
        return
    with conn.connect() as db_conn:
        for m in _MODALITY_SEED:
            prod = _PRODUCTION_DEFAULTS.get(m["slug"])
            if prod:
                _, price, eph = prod
                active = 1
            else:
                price, eph, active = 0.0, 0.0, 0
            db_conn.execute(
                sa.text("""
                    INSERT OR IGNORE INTO modalities
                        (slug, label, price, exams_per_hour, active, sort_order, color)
                    VALUES (:slug, :label, :price, :eph, :active, :sort_order, :color)
                """),
                {
                    "slug": m["slug"], "label": m["label"],
                    "price": price, "eph": eph, "active": active,
                    "sort_order": m["sort_order"], "color": m["color"],
                },
            )
        db_conn.commit()


def _add_color_column(conn: Any) -> None:
    """Add color column to modalities if it doesn't exist, then backfill defaults.

    Uses PRAGMA table_info to check column existence before ALTER TABLE.
    Backfills per-modality default colors from MODALITY_COLORS.
    """
    columns_df = conn.query("PRAGMA table_info(modalities)", ttl=0)
    existing_cols = set(columns_df["name"].tolist())
    if "color" in existing_cols:
        return  # Already migrated, nothing to do

    with conn.connect() as db_conn:
        db_conn.execute(
            sa.text("ALTER TABLE modalities ADD COLUMN color TEXT NOT NULL DEFAULT '#64748B'"),
        )
        # Backfill default colors for known modalities
        for slug, color in MODALITY_COLORS.items():
            db_conn.execute(
                sa.text("UPDATE modalities SET color = :color WHERE slug = :slug"),
                {"slug": slug, "color": color},
            )
        db_conn.commit()


def _migrate_v1_3_to_v1_4_defaults(conn: Any) -> None:
    """One-shot migration: apply production defaults to the 5 standard modalities.

    Only updates modalities that still have price=0 AND active=0 (untouched by
    the user). Guarded by a user_settings flag so it runs exactly once — a user
    who later deactivates and zeroes a seed modality is not silently re-activated
    on the next boot.
    """
    if load_setting(conn, "migration_v1_4_defaults_done") == "1":
        return
    with conn.connect() as db_conn:
        for slug, (label, price, eph) in _PRODUCTION_DEFAULTS.items():
            db_conn.execute(
                sa.text("""
                    UPDATE modalities
                    SET label = :label,
                        price = :price,
                        exams_per_hour = :eph,
                        active = 1,
                        updated_at = datetime('now','localtime')
                    WHERE slug = :slug
                      AND price = 0.0
                      AND active = 0
                """),
                {"slug": slug, "label": label, "price": price, "eph": eph},
            )
        db_conn.commit()
    save_setting(conn, "migration_v1_4_defaults_done", "1")


def _migrate_v1_cleanup(conn: Any) -> None:
    """One-shot: drop the v1 legacy tables (daily_production, exam_prices) once
    the v2 daily_production_items is populated.

    Guarded by a user_settings flag so it runs exactly once and never drops v1
    before its data was migrated. Idempotent and safe: only drops when v2
    already holds the production history.
    """
    if load_setting(conn, "migration_v1_cleanup_done") == "1":
        return
    v2_count = conn.query("SELECT COUNT(*) AS cnt FROM daily_production_items", ttl=0)
    if v2_count["cnt"].iloc[0] == 0:
        return  # v2 empty — keep v1 until its data is migrated
    with conn.connect() as db_conn:
        db_conn.execute(sa.text("DROP TABLE IF EXISTS daily_production"))
        db_conn.execute(sa.text("DROP TABLE IF EXISTS exam_prices"))
        db_conn.commit()
    save_setting(conn, "migration_v1_cleanup_done", "1")
