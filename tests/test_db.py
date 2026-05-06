"""Tests for src.db — v2 schema, modalities CRUD, daily_production_items CRUD."""

import time

import sqlalchemy as sa

from src.db import (
    DEFAULT_GOAL,
    DEFAULT_LLM_MODEL,
    add_modality,
    delete_modality,
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
    slugify,
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
        assert len(mods) == 5
        slugs = {m["slug"] for m in mods}
        assert "ressonancia_magnetica" in slugs
        assert "tc_geral" in slugs
        assert "radiografia" in slugs
        assert "angiotomografia" in slugs
        assert "tc_abdome_total" in slugs
        # All 5 should be active with production values
        assert all(m["active"] == 1 for m in mods)
        assert all(m["price"] > 0 for m in mods)
        assert all(m["exams_per_hour"] > 0 for m in mods)


# ── v2: Modalities CRUD ──


class TestLoadAllModalities:
    def test_returns_5_ordered(self, conn):
        init_db(conn)
        mods = load_all_modalities(conn)
        assert len(mods) == 5
        # Verify alphabetical order by label (case-insensitive)
        labels = [m["label"].lower() for m in mods]
        assert labels == sorted(labels)


class TestLoadActiveModalities:
    def test_empty_when_none_active(self, conn):
        init_db(conn)
        # Seed now has 5 active modalities — deactivate all first
        for slug in ["angiotomografia", "radiografia", "ressonancia_magnetica",
                      "tc_geral", "tc_abdome_total"]:
            save_modality(conn, slug, 30.0, 10.0, 0)
        active = load_active_modalities(conn)
        assert active == []

    def test_returns_activated_modalities(self, conn):
        init_db(conn)
        # All 5 modalities are seeded active with production values
        active = load_active_modalities(conn)
        assert len(active) == 5
        slugs = {m["slug"] for m in active}
        assert slugs == {"angiotomografia", "radiografia", "ressonancia_magnetica",
                         "tc_geral", "tc_abdome_total"}

    def test_excludes_zero_price_or_eph(self, conn):
        init_db(conn)
        # Deactivate all first, then test exclusion logic
        for slug in ["angiotomografia", "radiografia", "ressonancia_magnetica",
                      "tc_geral", "tc_abdome_total"]:
            save_modality(conn, slug, 30.0, 10.0, 0)

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
        # Deactivate others so only radiografia is active
        for slug in ["angiotomografia", "ressonancia_magnetica",
                      "tc_geral", "tc_abdome_total"]:
            save_modality(conn, slug, 30.0, 10.0, 0)

        active = load_active_modalities(conn)
        assert len(active) == 1
        assert active[0]["slug"] == "radiografia"

        save_modality(conn, "radiografia", 4.0, 80.0, 0)
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
        # All 5 seeded modalities are active with production values
        assert prices == {
            "angiotomografia": 30.0,
            "radiografia": 4.0,
            "ressonancia_magnetica": 35.0,
            "tc_abdome_total": 60.0,
            "tc_geral": 30.0,
        }

    def test_fallback_to_defaults_when_no_active(self, conn):
        init_db(conn)
        # Deactivate all seeded modalities so fallback is triggered
        for slug in ["angiotomografia", "radiografia", "ressonancia_magnetica",
                      "tc_geral", "tc_abdome_total"]:
            save_modality(conn, slug, 30.0, 10.0, 0)
        prices = load_prices(conn)
        assert prices["ressonancia_magnetica"] == 35.0
        assert prices["tc_geral"] == 30.0
        assert prices["radiografia"] == 4.0


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
        # Seed has 5 active; migration overrides 3 of them
        active = load_active_modalities(conn)
        assert len(active) == 5

        rm = next(m for m in active if m["slug"] == "ressonancia_magnetica")
        assert rm["price"] == 40.0
        assert rm["exams_per_hour"] == 7.5

        # radiografia: exam_prices says 5.0, migration overrides seed 4.0
        rx = next(m for m in active if m["slug"] == "radiografia")
        assert rx["price"] == 5.0
        assert rx["exams_per_hour"] == 75.0

        # tc_geral: exam_prices says 30.0 (matches seed default)
        tc = next(m for m in active if m["slug"] == "tc_geral")
        assert tc["price"] == 30.0

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
        assert len(active) == 5
        from src.db import DEFAULT_PRICES
        rm = next(m for m in active if m["slug"] == "ressonancia_magnetica")
        assert rm["price"] == DEFAULT_PRICES["ressonancia_magnetica"]
        assert rm["exams_per_hour"] == 7.5


class TestModalityColor:
    def test_save_modality_with_color(self, seeded_conn):
        """Save custom color, load back, verify it persisted."""
        save_modality(seeded_conn, "radiografia", 4.5, 75.0, 1, color="#FF0000")
        mods = load_all_modalities(seeded_conn)
        rx = next(m for m in mods if m["slug"] == "radiografia")
        assert rx["color"] == "#FF0000"
        # Other modalities should still have their default colors
        rm = next(m for m in mods if m["slug"] == "ressonancia_magnetica")
        assert rm["color"] == "#7C3AED"

    def test_seed_modalities_has_color(self, conn):
        """After seeding, every modality has a non-default color from the palette."""
        from src.db import _add_color_column, _seed_modalities
        _seed_modalities(conn)
        _add_color_column(conn)
        all_mods = load_all_modalities(conn)
        assert len(all_mods) == 5
        for m in all_mods:
            assert "color" in m
            # Each modality should have a real palette color (not the generic fallback)
            assert m["color"] != "#64748B", f"{m['slug']} should not have fallback color"
            assert m["color"].startswith("#")
            assert len(m["color"]) == 7

    def test_chart_colors_retains_11_colors(self):
        """MODALITY_COLORS still has 11 entries for backward compatibility."""
        from src.chart_colors import MODALITY_COLORS
        assert len(MODALITY_COLORS) == 11
        # Key production slugs should have colors
        assert "ressonancia_magnetica" in MODALITY_COLORS
        assert "tc_geral" in MODALITY_COLORS
        assert "radiografia" in MODALITY_COLORS

    def test_save_modality_without_color_does_not_overwrite(self, seeded_conn):
        """Calling save_modality without color leaves existing color unchanged."""
        # First set a custom color
        save_modality(seeded_conn, "tc_geral", 25.0, 7.5, 1, color="#111111")
        # Then update without color
        save_modality(seeded_conn, "tc_geral", 30.0, 8.0, 1)
        mods = load_all_modalities(seeded_conn)
        tc = next(m for m in mods if m["slug"] == "tc_geral")
        assert tc["price"] == 30.0
        assert tc["exams_per_hour"] == 8.0
        # Color should survive unchanged
        assert tc["color"] == "#111111"


# ── v1.4: slugify ──


class TestSlugify:
    def test_slugify_basic(self):
        assert slugify("Ressonância Magnética") == "ressonancia_magnetica"
        assert slugify("TC Geral") == "tc_geral"
        assert slugify("Hello World") == "hello_world"
        assert slugify("  spaces  ") == "spaces"
        assert slugify("Pontuação!!!") == "pontuacao"
        assert slugify("São Paulo") == "sao_paulo"
        assert slugify("Coração") == "coracao"

    def test_slugify_edge_cases(self):
        assert slugify("") == "modalidade"
        assert slugify("!!!###") == "modalidade"
        assert slugify("___") == "modalidade"


# ── v1.4: add_modality ──


class TestAddModality:
    def test_add_modality_success(self, conn):
        init_db(conn)
        result = add_modality(conn, "tomografia_cranio", "Tomografia de Crânio",
                              25.0, 5.0, 1)
        assert result is True
        mods = load_all_modalities(conn)
        assert len(mods) == 6  # 5 seed + 1 new
        new = next(m for m in mods if m["slug"] == "tomografia_cranio")
        assert new["label"] == "Tomografia de Crânio"
        assert new["price"] == 25.0
        assert new["exams_per_hour"] == 5.0
        assert new["active"] == 1
        assert new["color"] == "#64748B"  # default color

    def test_add_modality_duplicate_slug(self, conn):
        init_db(conn)
        add_modality(conn, "novo_exame", "Novo Exame", 10.0, 5.0, 1)
        result = add_modality(conn, "novo_exame", "Outro Nome", 20.0, 10.0, 0)
        assert result is False
        # Only one modality with this slug
        mods = load_all_modalities(conn)
        matches = [m for m in mods if m["slug"] == "novo_exame"]
        assert len(matches) == 1
        assert matches[0]["label"] == "Novo Exame"

    def test_add_modality_sort_order(self, conn):
        init_db(conn)
        # Seed has sort_order 1-5. New one should get 6.
        add_modality(conn, "extra1", "Extra 1", 10.0, 5.0, 1)
        mods = load_all_modalities(conn)
        extra = next(m for m in mods if m["slug"] == "extra1")
        assert extra["sort_order"] == 6

        # Next one gets 7
        add_modality(conn, "extra2", "Extra 2", 10.0, 5.0, 1)
        mods = load_all_modalities(conn)
        extra2 = next(m for m in mods if m["slug"] == "extra2")
        assert extra2["sort_order"] == 7


# ── v1.4: delete_modality ──


class TestDeleteModality:
    def test_delete_modality_success(self, conn):
        init_db(conn)
        result = delete_modality(conn, "tc_abdome_total")
        assert result is True
        mods = load_all_modalities(conn)
        assert len(mods) == 4
        slugs = {m["slug"] for m in mods}
        assert "tc_abdome_total" not in slugs

    def test_delete_nonexistent_modality(self, conn):
        init_db(conn)
        result = delete_modality(conn, "slug_inexistente")
        assert result is False
        mods = load_all_modalities(conn)
        assert len(mods) == 5  # unchanged

    def test_delete_modality_cascades_to_daily_items(self, conn):
        init_db(conn)
        # Create some daily production items first
        upsert_daily_items(conn, "2026-05-01", {"tc_abdome_total": 10})
        upsert_daily_items(conn, "2026-05-02", {"tc_abdome_total": 5,
                                                  "tc_geral": 8})

        # Verify items exist
        assert load_daily_items(conn, "2026-05-01") == {"tc_abdome_total": 10}
        assert load_daily_items(conn, "2026-05-02") == {"tc_abdome_total": 5,
                                                         "tc_geral": 8}

        # Delete the modality
        result = delete_modality(conn, "tc_abdome_total")
        assert result is True

        # tc_abdome_total items should be gone
        items_after_1 = load_daily_items(conn, "2026-05-01")
        assert items_after_1 == {}

        # tc_geral items should survive
        items_after_2 = load_daily_items(conn, "2026-05-02")
        assert items_after_2 == {"tc_geral": 8}


# ── v1.4: save_modality with label ──


class TestSaveModalityWithLabel:
    def test_save_modality_with_label(self, seeded_conn):
        save_modality(seeded_conn, "tc_geral", 30.0, 10.0, 1,
                       label="Tomografia Geral")
        mods = load_all_modalities(seeded_conn)
        tc = next(m for m in mods if m["slug"] == "tc_geral")
        assert tc["label"] == "Tomografia Geral"
        assert tc["slug"] == "tc_geral"  # slug never changes

    def test_rename_modality_label_slug_unchanged(self, seeded_conn):
        # Rename label, verify slug stays
        save_modality(seeded_conn, "ressonancia_magnetica", 35.0, 8.0, 1,
                       label="MRI")
        mods = load_all_modalities(seeded_conn)
        rm = next(m for m in mods if m["slug"] == "ressonancia_magnetica")
        assert rm["label"] == "MRI"
        assert rm["slug"] == "ressonancia_magnetica"

    def test_save_modality_without_label_does_not_overwrite(self, seeded_conn):
        # Set a custom label first
        save_modality(seeded_conn, "radiografia", 4.0, 80.0, 1,
                       label="RX Digital")
        # Then update price only (no label)
        save_modality(seeded_conn, "radiografia", 5.0, 80.0, 1)
        mods = load_all_modalities(seeded_conn)
        rx = next(m for m in mods if m["slug"] == "radiografia")
        assert rx["price"] == 5.0
        # Label should survive
        assert rx["label"] == "RX Digital"


# ── v1.4: seed verification ──


class TestSeed:
    def test_seed_has_five_modalities(self, seeded_conn):
        mods = load_all_modalities(seeded_conn)
        assert len(mods) == 5
        expected_slugs = {"angiotomografia", "radiografia", "ressonancia_magnetica",
                          "tc_geral", "tc_abdome_total"}
        slugs = {m["slug"] for m in mods}
        assert slugs == expected_slugs

    def test_seed_values_match_production(self, seeded_conn):
        mods = load_all_modalities(seeded_conn)
        values = {m["slug"]: (m["price"], m["exams_per_hour"], m["active"])
                  for m in mods}
        assert values["angiotomografia"] == (30.0, 4.0, 1)
        assert values["radiografia"] == (4.0, 80.0, 1)
        assert values["ressonancia_magnetica"] == (35.0, 8.0, 1)
        assert values["tc_geral"] == (30.0, 10.0, 1)
        assert values["tc_abdome_total"] == (60.0, 5.0, 1)


# ── v1.4: migration v1.3 → v1.4 ──


class TestMigrationV134:
    def test_migration_applies_defaults_to_untouched_mods(self, conn):
        """Modalities with price=0, active=0 get production defaults."""
        # Manually insert 5 mods with price=0, active=0 (simulating old DB)
        from src.db import _MODALITY_SEED, _migrate_v1_3_to_v1_4_defaults
        with conn.connect() as c:
            c.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS modalities (
                    slug TEXT PRIMARY KEY, label TEXT NOT NULL,
                    price REAL DEFAULT 0.0, exams_per_hour REAL DEFAULT 0.0,
                    active INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
                    color TEXT DEFAULT '#64748B'
                )
            """))
            c.commit()
        for m in _MODALITY_SEED:
            with conn.connect() as c:
                c.execute(sa.text("""
                    INSERT INTO modalities (slug, label, price, exams_per_hour,
                                            active, sort_order, color)
                    VALUES (:slug, :label, 0.0, 0.0, 0, :sort_order, :color)
                """), m)
                c.commit()

        # Verify they start at 0/0/0
        mods = load_all_modalities(conn)
        for m in mods:
            assert m["price"] == 0.0
            assert m["exams_per_hour"] == 0.0
            assert m["active"] == 0

        # Run migration
        _migrate_v1_3_to_v1_4_defaults(conn)

        # Verify they got production values
        mods = load_all_modalities(conn)
        values = {m["slug"]: (m["price"], m["exams_per_hour"], m["active"])
                  for m in mods}
        assert values["angiotomografia"] == (30.0, 4.0, 1)
        assert values["radiografia"] == (4.0, 80.0, 1)
        assert values["ressonancia_magnetica"] == (35.0, 8.0, 1)
        assert values["tc_geral"] == (30.0, 10.0, 1)
        assert values["tc_abdome_total"] == (60.0, 5.0, 1)

    def test_migration_preserves_user_config(self, conn):
        """Modalities already configured by user are not overwritten."""
        from src.db import _MODALITY_SEED, _migrate_v1_3_to_v1_4_defaults
        with conn.connect() as c:
            c.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS modalities (
                    slug TEXT PRIMARY KEY, label TEXT NOT NULL,
                    price REAL DEFAULT 0.0, exams_per_hour REAL DEFAULT 0.0,
                    active INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
                    color TEXT DEFAULT '#64748B'
                )
            """))
            c.commit()
        for m in _MODALITY_SEED:
            with conn.connect() as c:
                c.execute(sa.text("""
                    INSERT INTO modalities (slug, label, price, exams_per_hour,
                                            active, sort_order, color)
                    VALUES (:slug, :label, 0.0, 0.0, 0, :sort_order, :color)
                """), m)
                c.commit()

        # User configured tc_geral manually
        with conn.connect() as c:
            c.execute(sa.text("""
                UPDATE modalities
                SET price = 50.0, exams_per_hour = 3.0, active = 1
                WHERE slug = 'tc_geral'
            """))
            c.commit()

        # Run migration
        _migrate_v1_3_to_v1_4_defaults(conn)

        # tc_geral should keep user's values
        mods = load_all_modalities(conn)
        tc = next(m for m in mods if m["slug"] == "tc_geral")
        assert tc["price"] == 50.0
        assert tc["exams_per_hour"] == 3.0
        assert tc["active"] == 1

        # Untouched modalities should get defaults
        rm = next(m for m in mods if m["slug"] == "ressonancia_magnetica")
        assert rm["price"] == 35.0
        assert rm["active"] == 1

    def test_init_db_idempotent_on_existing_db(self, conn):
        """Calling init_db on a DB with existing modalities should not add
        duplicates or crash."""
        init_db(conn)
        mods_first = load_all_modalities(conn)
        assert len(mods_first) == 5

        init_db(conn)  # second call
        mods_second = load_all_modalities(conn)
        assert len(mods_second) == 5
        # Same slugs, same labels
        first_slugs = {(m["slug"], m["label"]) for m in mods_first}
        second_slugs = {(m["slug"], m["label"]) for m in mods_second}
        assert first_slugs == second_slugs
