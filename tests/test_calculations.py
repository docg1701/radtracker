"""Tests for src.calculations — v2 dynamic modality functions."""

from datetime import date

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
)
from src.db import init_db, upsert_daily_items

# ── Fixtures from conftest ──

def test_build_lookups(active_modalities):
    """_build_lookups returns slug→price and slug→eph dicts for all 5 active."""
    prices, eph = _build_lookups(active_modalities)
    assert prices == {
        "angiotomografia": 30.0,
        "radiografia": 4.0,
        "ressonancia_magnetica": 35.0,
        "tc_abdome_total": 60.0,
        "tc_geral": 30.0,
    }
    assert eph == {
        "angiotomografia": 4.0,
        "radiografia": 80.0,
        "ressonancia_magnetica": 8.0,
        "tc_abdome_total": 5.0,
        "tc_geral": 10.0,
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
        # rm=8*35 + tc=6*30 + rx=35*4 = 280+180+140 = 600
        assert stats["earnings_today"] == 600.0
        assert stats["exam_count_today"] == 49
        assert stats["modality_counts"]["ressonancia_magnetica"] == 8
        assert stats["modality_counts"]["tc_geral"] == 6
        assert stats["modality_counts"]["radiografia"] == 35
        # 8/8 + 6/10 + 35/80 = 1.0+0.6+0.4375 = 2.0375
        assert stats["estimated_hours"] == pytest.approx(2.04, abs=0.01)
        # yesterday: rm=4*35 + tc=3*30 + rx=20*4 = 140+90+80 = 310
        assert stats["yesterday_earnings"] == 310.0
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
        # tc_geral=6 * 30.0 = 180.0
        assert stats["earnings_today"] == 180.0
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
        assert stats["remaining_days"] == 0

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
        # Day1: 8*35 + 6*30 + 35*4 = 280+180+140 = 600
        # Day2: 2*35 = 70 → total = 670.0
        assert stats["mtd_earnings"] == 670.0
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


class TestMonthlyStatsDayCounting:
    """Day counting in dias corridos: every day is work-eligible.

    - today counts as ELAPSED (not remaining) when it already has production,
      reproducing the 29/06 23:00 report where the app said "2 dias restantes"
      instead of 1.
    - daily_avg is mtd / elapsed_days (all days, gaps as zero-production),
      NOT mtd / days_worked. days_worked stays a displayed statistic only.
    """

    def test_remaining_excludes_today_when_today_has_data(self, conn, active_modalities):
        init_db(conn)
        # June 2026 (30 days); today=29/06 with production on the 29th.
        upsert_daily_items(conn, "2026-06-29", {"ressonancia_magnetica": 8})
        stats = compute_monthly_stats(
            conn, "2026-06", 45000.0, active_modalities, today=date(2026, 6, 29)
        )
        assert stats["remaining_days"] == 1          # only the 30th
        assert stats["elapsed_days"] == 29
        assert stats["total_calendar_days"] == 30

    def test_remaining_includes_today_when_today_has_no_data(self, conn, active_modalities):
        init_db(conn)
        # today=29/06, production only on the 28th (today not yet recorded)
        upsert_daily_items(conn, "2026-06-28", {"ressonancia_magnetica": 8})
        stats = compute_monthly_stats(
            conn, "2026-06", 45000.0, active_modalities, today=date(2026, 6, 29)
        )
        assert stats["remaining_days"] == 2          # 29th + 30th still workable
        assert stats["elapsed_days"] == 28

    def test_daily_avg_over_elapsed_days_not_worked(self, conn, active_modalities):
        init_db(conn)
        # 15 elapsed days, worked only 4 (gaps as zero-production days)
        for d in (5, 8, 12, 15):
            upsert_daily_items(conn, f"2026-06-{d:02d}", {"ressonancia_magnetica": 8})
        stats = compute_monthly_stats(
            conn, "2026-06", 45000.0, active_modalities, today=date(2026, 6, 15)
        )
        # mtd = 8*35*4 = 1120; daily_avg = mtd / elapsed(15), not mtd / days_worked(4)
        assert stats["daily_avg"] == pytest.approx(1120 / 15, rel=1e-4)
        assert stats["days_worked"] == 4   # statistic only, not used in avg

    def test_projection_uses_elapsed_daily_avg_times_remaining(self, conn, active_modalities):
        init_db(conn)
        for d in (5, 8, 12, 15):
            upsert_daily_items(conn, f"2026-06-{d:02d}", {"ressonancia_magnetica": 8})
        stats = compute_monthly_stats(
            conn, "2026-06", 45000.0, active_modalities, today=date(2026, 6, 15)
        )
        # projection = mtd + daily_avg * remaining = 1120 + (1120/15)*15 = 2240
        assert stats["projection_month_end"] == pytest.approx(2240.0, rel=1e-4)

    def test_past_month_elapsed_full_remaining_zero(self, conn, active_modalities):
        init_db(conn)
        upsert_daily_items(conn, "2026-03-10", {"ressonancia_magnetica": 8})
        stats = compute_monthly_stats(
            conn, "2026-03", 45000.0, active_modalities, today=date(2026, 6, 15)
        )
        assert stats["elapsed_days"] == 31  # March full month
        assert stats["remaining_days"] == 0
        assert stats["daily_avg"] == pytest.approx(280 / 31, rel=1e-4)

    def test_first_of_month_no_data_full_remaining(self, conn, active_modalities):
        init_db(conn)
        stats = compute_monthly_stats(
            conn, "2026-06", 45000.0, active_modalities, today=date(2026, 6, 1)
        )
        assert stats["elapsed_days"] == 0
        assert stats["remaining_days"] == 30
        assert stats["daily_avg"] == 0.0


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
        # 5*35 + 10*30 = 175+300 = 475
        assert df["earnings"].iloc[0] == 475.0
