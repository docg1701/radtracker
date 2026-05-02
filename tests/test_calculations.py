"""Tests for src.calculations — v2 dynamic modality functions."""

import pytest

from src.calculations import (
    _build_lookups,
    _empty_historical_stats,
    compute_daily_stats,
    compute_daily_target,
    compute_delta_pct,
    compute_earnings,
    compute_historical_stats,
    compute_monthly_stats,
    estimate_hours,
    format_time_range,
)
from src.db import init_db, upsert_daily_items

# ── Fixtures from conftest ──

def test_build_lookups(active_modalities):
    """_build_lookups returns slug→price and slug→eph dicts."""
    prices, eph = _build_lookups(active_modalities)
    assert prices == {
        "ressonancia_magnetica": 35.0,
        "tc_geral": 25.0,
        "radiografia": 4.5,
    }
    assert eph == {
        "ressonancia_magnetica": 7.5,
        "tc_geral": 7.5,
        "radiografia": 75.0,
    }


# ── Pure functions ──


class TestComputeEarnings:
    def test_typical(self):
        counts = {"ressonancia_magnetica": 8, "tc_geral": 6, "radiografia": 35}
        prices = {"ressonancia_magnetica": 35.0, "tc_geral": 25.0, "radiografia": 4.5}
        result = compute_earnings(counts, prices)
        assert result == 587.5  # 8*35 + 6*25 + 35*4.5

    def test_all_zeros(self):
        result = compute_earnings({}, {"tc_geral": 25.0})
        assert result == 0.0

    def test_unknown_slugs_ignored(self):
        counts = {"desconhecido": 5}
        prices = {"tc_geral": 25.0}
        result = compute_earnings(counts, prices)
        assert result == 0.0


class TestEstimateHours:
    def test_typical(self):
        counts = {"ressonancia_magnetica": 15, "tc_geral": 15, "radiografia": 150}
        eph = {"ressonancia_magnetica": 7.5, "tc_geral": 7.5, "radiografia": 75.0}
        result = estimate_hours(counts, eph)
        assert result == 6.0  # 2 + 2 + 2

    def test_all_zeros(self):
        result = estimate_hours({}, {"tc_geral": 7.5})
        assert result == 0.0

    def test_skips_zero_rate(self):
        counts = {"tc_geral": 10}
        eph = {"tc_geral": 0.0}
        result = estimate_hours(counts, eph)
        assert result == 0.0


class TestFormatTimeRange:
    def test_typical(self):
        assert format_time_range(5.2) == "~08:00 – 13:12"

    def test_zero(self):
        assert format_time_range(0.0) == "~08:00 – 08:00"

    def test_full_day(self):
        assert format_time_range(14.5) == "~08:00 – 22:30"


class TestComputeDeltaPct:
    def test_positive(self):
        assert compute_delta_pct(600.0, 500.0) == 20.0

    def test_negative(self):
        assert compute_delta_pct(400.0, 500.0) == -20.0

    def test_none_yesterday(self):
        assert compute_delta_pct(600.0, None) is None

    def test_zero_yesterday(self):
        assert compute_delta_pct(600.0, 0.0) is None


class TestComputeDailyTarget:
    def test_typical(self):
        assert compute_daily_target(45000.0, 30) == pytest.approx(1500.0)

    def test_zero_days(self):
        assert compute_daily_target(45000.0, 0) == 0.0


# ── DB-dependent: daily stats ──


class TestComputeDailyStats:
    def test_with_data(self, conn, active_modalities):
        init_db(conn)
        upsert_daily_items(conn, "2026-04-15", {
            "ressonancia_magnetica": 8,
            "tc_geral": 6,
            "radiografia": 35,
        })
        upsert_daily_items(conn, "2026-04-14", {
            "ressonancia_magnetica": 4,
            "tc_geral": 3,
            "radiografia": 20,
        })

        stats = compute_daily_stats(conn, "2026-04-15", active_modalities)
        assert stats["has_data"] is True
        assert stats["earnings_today"] == 587.5
        assert stats["exam_count_today"] == 49
        assert stats["modality_counts"]["ressonancia_magnetica"] == 8
        assert stats["modality_counts"]["tc_geral"] == 6
        assert stats["modality_counts"]["radiografia"] == 35
        assert stats["estimated_hours"] == pytest.approx(2.33, abs=0.01)
        assert stats["yesterday_earnings"] == 305.0
        assert stats["delta_pct"] is not None

    def test_no_data(self, conn, active_modalities):
        init_db(conn)
        stats = compute_daily_stats(conn, "2026-04-15", active_modalities)
        assert stats["has_data"] is False
        assert stats["earnings_today"] == 0.0
        assert stats["exam_count_today"] == 0
        assert stats["estimated_hours"] == 0.0
        assert stats["yesterday_earnings"] is None
        assert stats["delta_pct"] is None

    def test_no_yesterday(self, conn, active_modalities):
        init_db(conn)
        upsert_daily_items(conn, "2026-04-15", {"tc_geral": 6})
        stats = compute_daily_stats(conn, "2026-04-15", active_modalities)
        assert stats["has_data"] is True
        assert stats["earnings_today"] == 150.0
        assert stats["yesterday_earnings"] is None
        assert stats["delta_pct"] is None


# ── DB-dependent: monthly stats ──


class TestComputeMonthlyStats:
    def test_empty_month(self, conn, active_modalities):
        init_db(conn)
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, active_modalities)
        assert stats["mtd_earnings"] == 0.0
        assert stats["pct_goal"] == 0.0
        assert stats["days_worked"] == 0
        assert stats["remaining_calendar_days"] == 0

    def test_with_data(self, conn, active_modalities):
        init_db(conn)
        upsert_daily_items(conn, "2026-03-10", {
            "ressonancia_magnetica": 8,
            "tc_geral": 6,
            "radiografia": 35,
        })
        upsert_daily_items(conn, "2026-03-11", {
            "ressonancia_magnetica": 2,
        })
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, active_modalities)
        # 8*35 + 6*25 + 35*4.5 = 280+150+157.5 = 587.5
        # + 2*35 = 70 → total = 657.5
        assert stats["mtd_earnings"] == 657.5
        assert stats["days_worked"] == 2

    def test_pct_goal(self, conn, active_modalities):
        init_db(conn)
        # Insert enough to get ~50%
        upsert_daily_items(conn, "2026-03-10", {"ressonancia_magnetica": 100})
        upsert_daily_items(conn, "2026-03-11", {"ressonancia_magnetica": 542})
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, active_modalities)
        pct = stats["pct_goal"]
        assert 49.0 < pct < 51.0

    def test_total_calendar_days(self, conn, active_modalities):
        init_db(conn)
        stats = compute_monthly_stats(conn, "2026-04", 45000.0, active_modalities)
        assert stats["total_calendar_days"] == 30

    def test_february_days(self, conn, active_modalities):
        init_db(conn)
        stats = compute_monthly_stats(conn, "2026-02", 45000.0, active_modalities)
        assert stats["total_calendar_days"] == 28


# ── Historical stats ──


class TestHistoricalStats:
    def test_empty_db(self, conn, active_modalities):
        init_db(conn)
        result = compute_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        assert "df" in result
        assert result["wow_change_pct"] is None
        assert result["mom_change_pct"] is None
        assert result["weekly_totals_last_4"] == []

    def test_ma7_with_one_day(self, conn, active_modalities):
        init_db(conn)
        upsert_daily_items(conn, "2026-03-10", {"ressonancia_magnetica": 10})
        result = compute_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        df = result["df"]
        assert len(df) == 1
        assert df["earnings"].iloc[0] == 350.0  # 10*35
        assert df["ma7"].iloc[0] == 350.0

    def test_ma7_rolling(self, conn, active_modalities):
        init_db(conn)
        for d in range(10, 20):
            upsert_daily_items(conn, f"2026-03-{d}", {"ressonancia_magnetica": 10})
        result = compute_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        df = result["df"]
        assert len(df) == 10
        assert df["ma7"].iloc[-1] == 350.0

    def test_wow_positive(self, conn, active_modalities):
        init_db(conn)
        # Week 1
        upsert_daily_items(conn, "2026-03-02", {"ressonancia_magnetica": 10})
        upsert_daily_items(conn, "2026-03-03", {"ressonancia_magnetica": 10})
        # Week 2 (higher)
        upsert_daily_items(conn, "2026-03-09", {"ressonancia_magnetica": 20})
        upsert_daily_items(conn, "2026-03-10", {"ressonancia_magnetica": 20})

        result = compute_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        assert result["wow_change_pct"] is not None
        assert result["wow_change_pct"] > 0

    def test_modality_mix_sum_to_100(self, conn, active_modalities):
        init_db(conn)
        upsert_daily_items(conn, "2026-03-10", {
            "ressonancia_magnetica": 8,
            "tc_geral": 6,
            "radiografia": 35,
        })
        result = compute_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        mix = result["modality_mix_current"]
        total = sum(mix.values())
        assert total == pytest.approx(100.0, abs=0.5)

    def test_consecutive_below_target(self, conn, active_modalities):
        init_db(conn)
        year_month = "2026-03"
        for day in ("2026-03-29", "2026-03-30", "2026-03-31"):
            upsert_daily_items(conn, day, {"radiografia": 1})
        result = compute_historical_stats(conn, year_month, 45000.0, active_modalities)
        assert result["consecutive_below_target"] >= 3

    def test_empty_historical_stats_columns(self, conn, active_modalities):
        init_db(conn)
        result = _empty_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        df = result["df"]
        expected = {"date", "earnings", "date_dt", "ma7", "ma30", "week", "iso_year"}
        assert set(df.columns) == expected

    def test_multiple_modalities_in_historical(self, conn, active_modalities):
        init_db(conn)
        # Use both RM and TC
        upsert_daily_items(conn, "2026-03-10", {
            "ressonancia_magnetica": 5,
            "tc_geral": 10,
        })
        upsert_daily_items(conn, "2026-03-11", {
            "ressonancia_magnetica": 3,
            "tc_geral": 8,
        })
        result = compute_historical_stats(conn, "2026-03", 45000.0, active_modalities)
        df = result["df"]
        assert len(df) == 2
        # 5*35 + 10*25 = 175+250 = 425
        assert df["earnings"].iloc[0] == 425.0
