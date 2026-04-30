"""Tests for src.calculations — earnings, stats, MA, WoW, MoM, historical."""

from datetime import date

import pandas as pd
import pytest

from src.calculations import (
    _empty_historical_stats,
    add_earnings_column,
    compute_daily_stats,
    compute_daily_target,
    compute_delta_pct,
    compute_earnings,
    compute_historical_stats,
    compute_monthly_stats,
    compute_mtd_earnings,
    estimate_hours,
    format_time_range,
)
from src.db import init_db, upsert_daily

DEFAULT_PRICES = {"rm": 35.0, "tc": 25.0, "rx": 4.5}


# ── Pure functions (no DB) ──


class TestComputeEarnings:
    def test_compute_earnings_typical(self):
        result = compute_earnings(8, 6, 35, DEFAULT_PRICES)
        assert result == 587.5  # 8*35 + 6*25 + 35*4.5

    def test_compute_earnings_all_zeros(self):
        result = compute_earnings(0, 0, 0, DEFAULT_PRICES)
        assert result == 0.0

    def test_compute_earnings_only_rm(self):
        result = compute_earnings(10, 0, 0, DEFAULT_PRICES)
        assert result == 350.0


class TestEstimateHours:
    def test_estimate_hours_typical(self):
        result = estimate_hours(15, 15, 150)
        assert result == 6.0

    def test_estimate_hours_all_zeros(self):
        result = estimate_hours(0, 0, 0)
        assert result == 0.0


class TestFormatTimeRange:
    def test_format_time_range_typical(self):
        result = format_time_range(5.2)
        assert result == "~08:00 – 13:12"

    def test_format_time_range_zero(self):
        result = format_time_range(0.0)
        assert result == "~08:00 – 08:00"

    def test_format_time_range_full_day(self):
        result = format_time_range(14.5)  # 870 minutes
        assert result == "~08:00 – 22:30"


class TestComputeDeltaPct:
    def test_compute_delta_pct_positive(self):
        result = compute_delta_pct(600.0, 500.0)
        assert result == 20.0

    def test_compute_delta_pct_negative(self):
        result = compute_delta_pct(400.0, 500.0)
        assert result == -20.0

    def test_compute_delta_pct_none_yesterday(self):
        result = compute_delta_pct(600.0, None)
        assert result is None

    def test_compute_delta_pct_zero_yesterday(self):
        result = compute_delta_pct(600.0, 0.0)
        assert result is None


# ── DB-dependent: monthly stats ──


class TestComputeMonthlyStats:
    def test_compute_monthly_stats_empty_month(self, conn):
        init_db(conn)
        # Use a past month to avoid non-deterministic remaining_work_days
        # when date.today() falls within the test month
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        assert stats["mtd_earnings"] == 0.0
        assert stats["pct_goal"] == 0.0
        assert stats["days_worked"] == 0
        assert stats["remaining_calendar_days"] == 0  # past month

    def test_compute_monthly_stats_with_data(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-03-10", 8, 6, 35)
        upsert_daily(conn, "2026-03-11", 2, 0, 0)
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        # 8*35 + 6*25 + 35*4.5 = 280+150+157.5 = 587.5
        # + 2*35 = 70 → total = 657.5
        assert stats["mtd_earnings"] == 657.5
        assert stats["days_worked"] == 2

    def test_compute_monthly_stats_pct_goal(self, conn):
        init_db(conn)
        # Insert data that gives exactly 50% of 45000 = 22500
        # One day with enough exams: 22500 / 35 = ~643 RM exams
        # Actually let's just test the formula indirectly by inserting
        # a known amount
        upsert_daily(conn, "2026-03-10", 100, 0, 0)  # 3500
        upsert_daily(conn, "2026-03-11", 542, 0, 0)  # ~18970
        # total ≈ 22470, close to 22500
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        pct = stats["pct_goal"]
        # 3500+18970=22470, /45000*100 ≈ 49.93
        assert 49.0 < pct < 51.0

    def test_compute_monthly_stats_total_calendar_days(self, conn):
        init_db(conn)
        stats = compute_monthly_stats(conn, "2026-04", 45000.0, DEFAULT_PRICES)
        # April has 30 calendar days
        assert stats["total_calendar_days"] == 30

    def test_compute_monthly_stats_calendar_days_vary(self, conn):
        init_db(conn)
        stats_feb = compute_monthly_stats(conn, "2026-02", 45000.0, DEFAULT_PRICES)
        # February 2026 has 28 days
        assert stats_feb["total_calendar_days"] == 28

    def test_compute_monthly_stats_past_month(self, conn):
        init_db(conn)
        stats = compute_monthly_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        # Past month has 0 remaining calendar days
        assert stats["remaining_calendar_days"] == 0


class TestComputeDailyTarget:
    def test_compute_daily_target_normal(self):
        result = compute_daily_target(45000.0, 26)
        assert result == pytest.approx(1730.7692307692307)

    def test_compute_daily_target_zero_days(self):
        result = compute_daily_target(45000.0, 0)
        assert result == 0.0


# ── DB-dependent: earnings column + compute_mtd ──


class TestAddEarningsColumn:
    def test_add_earnings_column(self):
        df = pd.DataFrame([
            {"rm_count": 2, "tc_count": 0, "rx_count": 0, "date": "2026-04-29"},
        ])
        result = add_earnings_column(df, DEFAULT_PRICES)
        assert "earnings" in result.columns
        assert result["earnings"].iloc[0] == 70.0

    def test_add_earnings_column_does_not_mutate(self):
        df = pd.DataFrame([
            {"rm_count": 2, "tc_count": 0, "rx_count": 0, "date": "2026-04-29"},
        ])
        _ = add_earnings_column(df, DEFAULT_PRICES)
        assert "earnings" not in df.columns  # original unchanged


class TestComputeMtdEarnings:
    def test_compute_mtd_earnings(self):
        df = pd.DataFrame([
            {"rm_count": 1, "tc_count": 0, "rx_count": 0},
            {"rm_count": 2, "tc_count": 0, "rx_count": 0},
        ])
        result = compute_mtd_earnings(df, DEFAULT_PRICES)
        assert result == 105.0  # 3*35 = 105

    def test_compute_mtd_earnings_empty(self):
        df = pd.DataFrame(columns=["rm_count", "tc_count", "rx_count"])
        result = compute_mtd_earnings(df, DEFAULT_PRICES)
        assert result == 0.0


class TestComputeDailyStats:
    def test_compute_daily_stats_with_data(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-04-15", 8, 6, 35)
        # Insert yesterday data too
        upsert_daily(conn, "2026-04-14", 4, 3, 20)

        stats = compute_daily_stats(conn, "2026-04-15", DEFAULT_PRICES)
        assert stats["has_data"] is True
        assert stats["earnings_today"] == 587.5
        assert stats["exam_count_today"] == 49
        assert stats["rm_count"] == 8
        assert stats["tc_count"] == 6
        assert stats["rx_count"] == 35
        assert stats["estimated_hours"] == pytest.approx(2.33, abs=0.01)

        # Yesterday earnings: 4*35 + 3*25 + 20*4.5 = 140+75+90 = 305
        assert stats["yesterday_earnings"] == 305.0
        assert stats["delta_pct"] is not None

    def test_compute_daily_stats_no_data(self, conn):
        init_db(conn)
        stats = compute_daily_stats(conn, "2026-04-15", DEFAULT_PRICES)
        assert stats["has_data"] is False
        assert stats["earnings_today"] == 0.0
        assert stats["exam_count_today"] == 0
        assert stats["estimated_hours"] == 0.0
        assert stats["yesterday_earnings"] is None
        assert stats["delta_pct"] is None
        assert stats["estimated_time_range"] == "~08:00 – 08:00"


# ── Historical stats ──


class TestHistoricalStats:
    def test_historical_empty_db(self, conn):
        init_db(conn)
        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        assert "df" in result
        assert result["wow_change_pct"] is None
        assert result["mom_change_pct"] is None
        assert result["weekly_totals_last_4"] == []
        assert result["modality_mix_current"] == {"rm": 0.0, "tc": 0.0, "rx": 0.0}
        assert result["modality_mix_historical"] == {}
        assert result["consecutive_below_target"] == 0
        assert "current_month_stats" in result

    def test_historical_ma7_with_one_day(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-03-10", 10, 0, 0)  # 350.0 earnings
        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        df = result["df"]
        assert len(df) == 1
        assert df["ma7"].iloc[0] == 350.0
        assert df["ma30"].iloc[0] == 350.0

    def test_historical_ma7_rolling(self, conn):
        init_db(conn)
        # Insert 10 days, each with 10 RM exams = 350 per day
        for d in range(10, 20):
            upsert_daily(conn, f"2026-03-{d}", 10, 0, 0)
        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        df = result["df"]
        assert len(df) == 10
        # Last MA7 should be mean of days 4-10 = 7*350/7 = 350
        assert df["ma7"].iloc[-1] == 350.0

    def test_historical_ma30_insufficient_data(self, conn):
        init_db(conn)
        for d in range(10, 15):  # 5 days
            upsert_daily(conn, f"2026-03-{d}", 10, 0, 0)
        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        df = result["df"]
        assert len(df) == 5
        # MA30 with 5 points should be mean of all 5 = 350
        assert df["ma30"].iloc[-1] == 350.0

    def test_historical_wow_positive(self, conn):
        init_db(conn)
        # Week 1: 2026-03-02 (Mon) and 2026-03-03
        upsert_daily(conn, "2026-03-02", 10, 0, 0)  # 350
        upsert_daily(conn, "2026-03-03", 10, 0, 0)  # 350

        # Week 2: 2026-03-09 (Mon) and 2026-03-10 — higher totals
        upsert_daily(conn, "2026-03-09", 20, 0, 0)  # 700
        upsert_daily(conn, "2026-03-10", 20, 0, 0)  # 700

        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        assert result["wow_change_pct"] is not None
        assert result["wow_change_pct"] > 0

    def test_historical_wow_insufficient_weeks(self, conn):
        init_db(conn)
        # Only one week of data
        upsert_daily(conn, "2026-03-02", 10, 0, 0)
        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        assert result["wow_change_pct"] is None

    def test_historical_modality_mix_sum_to_100(self, conn):
        init_db(conn)
        upsert_daily(conn, "2026-03-10", 8, 6, 35)  # 587.5
        result = compute_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        mix = result["modality_mix_current"]
        total = mix["rm"] + mix["tc"] + mix["rx"]
        assert total == pytest.approx(100.0, abs=0.5)

    def test_historical_consecutive_below_target(self, conn):
        init_db(conn)
        # Insert 3 days with very low earnings (below daily_target ~1730.77)
        today = date.today()
        ym = today.isoformat()[:7]
        from datetime import timedelta
        # Insert 3 days with 1 RM exam each = 35.0 << 1730.77
        for i in range(3):
            day = (today - timedelta(days=3 - i)).isoformat()
            upsert_daily(conn, day, 1, 0, 0)

        result = compute_historical_stats(conn, ym, 45000.0, DEFAULT_PRICES)
        assert result["consecutive_below_target"] >= 3

    def test_historical_empty_df_columns(self, conn):
        init_db(conn)
        result = _empty_historical_stats(conn, "2026-03", 45000.0, DEFAULT_PRICES)
        df = result["df"]
        expected = {"date", "rm_count", "tc_count", "rx_count",
                    "earnings", "date_dt", "ma7", "ma30", "week", "iso_year"}
        assert set(df.columns) == expected
