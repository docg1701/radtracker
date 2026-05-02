"""Tests for src.db — v2 schema, modalities CRUD, daily_production_items CRUD."""

import time

import sqlalchemy as sa

from src.db import (
    DEFAULT_GOAL,
    DEFAULT_LLM_MODEL,
    init_db,
    load_active_modalities,
    load_all_modalities,
    load_daily,
    load_daily_items,
    load_goal,
    load_month,
    load_month_items,
    load_prices,
    load_setting,
    save_goal,
    save_modality,
    save_prices,
    save_setting,
    upsert_daily,
    upsert_daily_items,
)


class TestInitDb:
    def test_init_db_creates_tables(self, conn):
        init_db(conn)
        df = conn.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = set(df["name"].tolist())
        expected = {
            "daily_production",
            "exam_prices",
            "modalities",
            "daily_production_items",
            "monthly_goals",
            "user_settings",
        }
        assert expected.issubset(names)

    def test_init_db_idempotent(self, conn):
        init_db(conn)
        init_db(conn)  # must not raise

    def test_init_db_seeds_modalities(self, conn):
        init_db(conn)
        mods = load_all_modalities(conn)
        assert len(mods) == 11
        slugs = {m["slug"] for m in mods}
        assert "ressonancia_magnetica" in slugs
        assert "tc_geral" in slugs
        assert "radiografia" in slugs
        # All should be inactive with price=0 by default
        assert all(m["active"] == 0 for m in mods)
        assert all(m["price"] == 0.0 for m in mods)
        assert all(m["exams_per_hour"] == 0.0 for m in mods)


# ── v2: Modalities CRUD ──


class TestLoadAllModalities:
    def test_returns_11_ordered(self, conn):
        init_db(conn)
        mods = load_all_modalities(conn)
        assert len(mods) == 11
        # Verify alphabetical order by label (case-insensitive)
        labels = [m["label"].lower() for m in mods]
        assert labels == sorted(labels)


class TestLoadActiveModalities:
    def test_empty_when_none_active(self, conn):
        init_db(conn)
        active = load_active_modalities(conn)
        assert active == []

    def test_returns_activated_modalities(self, conn):
        init_db(conn)
        save_modality(conn, "ressonancia_magnetica", 35.0, 7.5, 1)
        active = load_active_modalities(conn)
        assert len(active) == 1
        assert active[0]["slug"] == "ressonancia_magnetica"
        assert active[0]["price"] == 35.0
        assert active[0]["exams_per_hour"] == 7.5

    def test_excludes_zero_price_or_eph(self, conn):
        init_db(conn)
        # Active but price=0 → not returned
        save_modality(conn, "radiografia", 0.0, 75.0, 1)
        active = load_active_modalities(conn)
        assert len(active) == 0

        # Active but exams_per_hour=0 → not returned
        save_modality(conn, "tc_geral", 25.0, 0.0, 1)
        active = load_active_modalities(conn)
        assert len(active) == 0


class TestSaveModality:
    def test_updates_price_and_eph_and_active(self, conn):
        init_db(conn)
        save_modality(conn, "tc_abdome_total", 30.0, 3.0, 1)
        mods = load_all_modalities(conn)
        m = next(m for m in mods if m["slug"] == "tc_abdome_total")
        assert m["price"] == 30.0
        assert m["exams_per_hour"] == 3.0
        assert m["active"] == 1

    def test_deactivate(self, conn):
        init_db(conn)
        save_modality(conn, "densitometria", 10.0, 10.0, 1)
        active = load_active_modalities(conn)
        assert len(active) == 1

        save_modality(conn, "densitometria", 10.0, 10.0, 0)
        active = load_active_modalities(conn)
        assert len(active) == 0


# ── v2: Daily production items CRUD ──


class TestUpsertDailyItems:
    def test_insert_single_item(self, conn):
        init_db(conn)
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 6})
        items = load_daily_items(conn, "2026-05-02")
        assert items == {"tc_geral": 6}

    def test_insert_multiple_items(self, conn):
        init_db(conn)
        upsert_daily_items(
            conn, "2026-05-02",
            {"ressonancia_magnetica": 8, "tc_geral": 6, "radiografia": 35},
        )
        items = load_daily_items(conn, "2026-05-02")
        assert items["ressonancia_magnetica"] == 8
        assert items["tc_geral"] == 6
        assert items["radiografia"] == 35

    def test_update_existing(self, conn):
        init_db(conn)
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 6})
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 10})
        items = load_daily_items(conn, "2026-05-02")
        assert items["tc_geral"] == 10

    def test_empty_items_noop(self, conn):
        init_db(conn)
        upsert_daily_items(conn, "2026-05-02", {})
        items = load_daily_items(conn, "2026-05-02")
        assert items == {}

    def test_zero_count_deletes_row(self, conn):
        """Setting count to 0 removes the row from the database."""
        init_db(conn)
        # Insert first
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 6})
        items = load_daily_items(conn, "2026-05-02")
        assert items == {"tc_geral": 6}

        # Set to zero — row should be deleted
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 0})
        items = load_daily_items(conn, "2026-05-02")
        assert items == {}

    def test_zero_count_on_nonexistent_noop(self, conn):
        """DELETE on non-existent row is a no-op."""
        init_db(conn)
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 0})
        items = load_daily_items(conn, "2026-05-02")
        assert items == {}


class TestLoadDailyItems:
    def test_returns_dict(self, conn):
        init_db(conn)
        upsert_daily_items(conn, "2026-05-02", {"tc_geral": 5})
        items = load_daily_items(conn, "2026-05-02")
        assert isinstance(items, dict)
        assert items["tc_geral"] == 5

    def test_nonexistent_date_empty_dict(self, conn):
        init_db(conn)
        items = load_daily_items(conn, "2099-01-01")
        assert items == {}


class TestLoadMonthItems:
    def test_returns_correct_rows(self, conn):
        init_db(conn)
        upsert_daily_items(conn, "2026-04-10", {"tc_geral": 2, "radiografia": 10})
        upsert_daily_items(conn, "2026-04-20", {"tc_geral": 3})
        upsert_daily_items(conn, "2026-05-01", {"tc_geral": 1})

        df = load_month_items(conn, "2026-04")
        assert len(df) == 3  # 2 items on 04-10 + 1 item on 04-20
        dates = set(df["date"].tolist())
        assert "2026-04-10" in dates
        assert "2026-04-20" in dates
        assert "2026-05-01" not in dates

    def test_empty_month(self, conn):
        init_db(conn)
        df = load_month_items(conn, "2026-06")
        assert df.empty


# ── v2: load_prices from active modalities ──


class TestLoadPricesV2:
    def test_returns_active_modality_prices(self, seeded_conn):
        prices = load_prices(seeded_conn)
        assert prices == {
            "ressonancia_magnetica": 35.0,
            "tc_geral": 25.0,
            "radiografia": 4.5,
        }

    def test_fallback_to_defaults_when_no_active(self, conn):
        init_db(conn)
        prices = load_prices(conn)
        assert prices["ressonancia_magnetica"] == 35.0
        assert prices["tc_geral"] == 25.0
        assert prices["radiografia"] == 4.5


# ── v1 (legacy) tests — kept for migration verification ──


class TestUpsertDaily:
    def test_upsert_insert(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-04-15", 8, 6, 35)
        df = conn.query("SELECT COUNT(*) AS cnt FROM daily_production")
        assert df["cnt"].iloc[0] == 1

    def test_upsert_update(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-04-15", 8, 6, 35)
        upsert_daily(conn, "2026-04-15", 10, 10, 50)
        row = load_daily(conn, "2026-04-15")
        assert row is not None
        assert row["rm_count"] == 10
        assert row["tc_count"] == 10
        assert row["rx_count"] == 50

    def test_upsert_preserves_created_at(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-04-15", 8, 6, 35)
        first = load_daily(conn, "2026-04-15")
        assert first is not None

        time.sleep(1.1)
        upsert_daily(conn, "2026-04-15", 10, 10, 50)
        second = load_daily(conn, "2026-04-15")
        assert second is not None

        assert first["created_at"] == second["created_at"]
        assert first["updated_at"] != second["updated_at"]


class TestLoadDaily:
    def test_load_daily_exists(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-04-15", 8, 6, 35)
        row = load_daily(conn, "2026-04-15")
        assert row is not None
        assert row["rm_count"] == 8

    def test_load_daily_nonexistent(self, conn):
        init_db(conn)
        row = load_daily(conn, "2026-04-15")
        assert row is None


class TestLoadMonth:
    def test_load_month_returns_correct_rows(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-04-10", 1, 0, 0)
        upsert_daily(conn, "2026-04-20", 2, 0, 0)
        upsert_daily(conn, "2026-05-01", 3, 0, 0)

        df = load_month(conn, "2026-04")
        assert len(df) == 2
        dates = df["date"].tolist()
        assert "2026-04-10" in dates
        assert "2026-04-20" in dates
        assert "2026-05-01" not in dates


class TestPrices:
    def test_save_and_load_prices(self, conn):
        init_db(conn)
        save_prices(conn, 40.0, 30.0, 5.0)
        # v1 load_prices now delegates to active modalities
        # The old exam_prices table just stores history; load_prices reads from modalities
        # So this test verifies save_prices doesn't crash
        df = conn.query("SELECT * FROM exam_prices", ttl=0)
        assert len(df) == 1


class TestGoal:
    def test_load_goal_default(self, conn):
        init_db(conn)
        goal = load_goal(conn, "2026-04")
        assert goal == DEFAULT_GOAL

    def test_save_and_load_goal(self, conn):
        init_db(conn)
        save_goal(conn, "2026-04", 50000.0)
        goal = load_goal(conn, "2026-04")
        assert goal == 50000.0


class TestSettings:
    def test_save_and_load_setting(self, conn):
        init_db(conn)
        save_setting(conn, "llm_model", "anthropic/claude-sonnet-4")
        val = load_setting(conn, "llm_model", DEFAULT_LLM_MODEL)
        assert val == "anthropic/claude-sonnet-4"

    def test_load_setting_default(self, conn):
        init_db(conn)
        val = load_setting(conn, "nonexistent", "fallback")
        assert val == "fallback"


# ── Migration test ──


class TestMigration:
    def test_v1_to_v2_migrates_data(self, conn):
        """Insert v1 data, then init_db should migrate to v2 items."""
        # Manually create v1 tables
        with conn.connect() as c:
            c.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS daily_production (
                    date TEXT PRIMARY KEY, rm_count INTEGER, tc_count INTEGER,
                    rx_count INTEGER, created_at TEXT, updated_at TEXT
                )
            """))
            c.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS exam_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rm_price REAL, tc_price REAL, rx_price REAL,
                    effective_from TEXT, created_at TEXT
                )
            """))
            c.commit()

        upsert_daily(conn, "2026-03-10", 8, 6, 35)
        save_prices(conn, 40.0, 30.0, 5.0)

        # Now run init_db which should create v2 tables + migrate
        init_db(conn)

        # Verify v2 data exists
        items = load_daily_items(conn, "2026-03-10")
        assert items.get("ressonancia_magnetica") == 8
        assert items.get("tc_geral") == 6
        assert items.get("radiografia") == 35

        # Verify modalities got prices from migration
        active = load_active_modalities(conn)
        assert len(active) == 3

        rm = next(m for m in active if m["slug"] == "ressonancia_magnetica")
        assert rm["price"] == 40.0
        assert rm["exams_per_hour"] == 7.5

        tx = next(m for m in active if m["slug"] == "radiografia")
        assert tx["price"] == 5.0
        assert tx["exams_per_hour"] == 75.0

    def test_v1_to_v2_migrates_data_without_prices(self, conn):
        """If exam_prices is empty, migration falls back to DEFAULT_PRICES."""
        with conn.connect() as c:
            c.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS daily_production (
                    date TEXT PRIMARY KEY, rm_count INTEGER, tc_count INTEGER,
                    rx_count INTEGER, created_at TEXT, updated_at TEXT
                )
            """))
            c.commit()

        upsert_daily(conn, "2026-03-10", 8, 6, 35)
        # No exam_prices row inserted

        init_db(conn)

        items = load_daily_items(conn, "2026-03-10")
        assert items.get("ressonancia_magnetica") == 8
        assert items.get("tc_geral") == 6
        assert items.get("radiografia") == 35

        active = load_active_modalities(conn)
        assert len(active) == 3
        from src.db import DEFAULT_PRICES
        rm = next(m for m in active if m["slug"] == "ressonancia_magnetica")
        assert rm["price"] == DEFAULT_PRICES["ressonancia_magnetica"]
        assert rm["exams_per_hour"] == 7.5
