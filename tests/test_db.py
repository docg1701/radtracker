"""Tests for src.db — schema, CRUD, and default values."""

import time

from src.db import (
    DEFAULT_GOAL,
    init_db,
    load_daily,
    load_goal,
    load_month,
    load_prices,
    save_goal,
    save_prices,
    upsert_daily,
)


class TestInitDb:
    def test_init_db_creates_tables(self, conn):
        init_db(conn)
        df = conn.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = set(df["name"].tolist())
        expected = {"daily_production", "exam_prices", "monthly_goals"}
        assert expected.issubset(names)

    def test_init_db_idempotent(self, conn):
        init_db(conn)
        init_db(conn)  # must not raise


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

        time.sleep(1.1)  # ensure at least 1s difference for TEXT timestamps
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
        assert row["tc_count"] == 6
        assert row["rx_count"] == 35
        assert row["date"] == "2026-04-15"

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
        # Verify ordering by date (SQL ORDER BY date)
        assert df["date"].tolist() == sorted(df["date"].tolist())

    def test_load_month_empty(self, conn):
        init_db(conn)
        df = load_month(conn, "2026-06")
        assert df.empty


class TestPrices:
    def test_load_prices_defaults(self, conn):
        init_db(conn)
        prices = load_prices(conn)
        assert prices == {"rm": 35.0, "tc": 25.0, "rx": 4.5}

    def test_save_and_load_prices(self, conn):
        init_db(conn)
        save_prices(conn, 40.0, 30.0, 5.0)
        prices = load_prices(conn)
        assert prices == {"rm": 40.0, "tc": 30.0, "rx": 5.0}

    def test_load_prices_most_recent(self, conn):
        init_db(conn)
        save_prices(conn, 35.0, 25.0, 4.5)
        save_prices(conn, 40.0, 30.0, 5.0)
        prices = load_prices(conn)
        assert prices == {"rm": 40.0, "tc": 30.0, "rx": 5.0}


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

    def test_save_goal_update(self, conn):
        init_db(conn)
        save_goal(conn, "2026-04", 50000.0)
        save_goal(conn, "2026-04", 60000.0)  # update same month
        goal = load_goal(conn, "2026-04")
        assert goal == 60000.0

    def test_load_goal_different_month_default(self, conn):
        init_db(conn)
        save_goal(conn, "2026-04", 50000.0)
        goal = load_goal(conn, "2026-05")
        assert goal == DEFAULT_GOAL
