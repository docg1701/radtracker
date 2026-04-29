"""
Business-logic calculations for radtracker.

Pure functions for earnings, hours, projections, and moving averages.
DB-dependent functions accept a Streamlit connection as first parameter.

Business rules (from BRIEF.md):
  - RM pays R$35.00/exam, TC pays R$25.00/exam, RX pays R$4.50/exam
  - Productivity midpoints: RM 7.5/h, TC 7.5/h, RX 75/h
  - Work days: Monday–Saturday
  - Monthly goal default: R$45,000
"""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.db import load_daily

# Productivity midpoints (exams/hour) — used for hour estimation
PRODUCTIVITY: dict[str, float] = {
    "rm": 7.5,
    "tc": 7.5,
    "rx": 75.0,
}

# Default work start time for time-range display
WORK_START_HOUR: int = 8
WORK_START_MINUTE: int = 0


# ---------------------------------------------------------------------------
# Pure functions (no DB access)
# ---------------------------------------------------------------------------

def compute_earnings(
    rm: int, tc: int, rx: int, prices: dict[str, float]
) -> float:
    """
    Calculate total earnings from exam counts and prices.

    Example:
        >>> compute_earnings(8, 6, 35, {"rm": 35.0, "tc": 25.0, "rx": 4.5})
        587.5
    """
    return float(rm * prices["rm"] + tc * prices["tc"] + rx * prices["rx"])


def estimate_hours(rm: int, tc: int, rx: int) -> float:
    """
    Estimate work hours based on productivity midpoints.

    RM midpoint = 7.5 exams/h, TC = 7.5 exams/h, RX = 75 exams/h.

    Example:
        >>> estimate_hours(15, 15, 150)
        6.0
    """
    hours = (
        rm / PRODUCTIVITY["rm"]
        + tc / PRODUCTIVITY["tc"]
        + rx / PRODUCTIVITY["rx"]
    )
    return round(hours, 2)


def format_time_range(hours: float) -> str:
    """
    Return a human-readable time range string assuming work starts at WORK_START_HOUR:WORK_START_MINUTE.

    Example:
        >>> format_time_range(5.2)
        '~08:00 – 13:12'
        >>> format_time_range(0.0)
        '~08:00 – 08:00'
    """
    start_minutes = WORK_START_HOUR * 60 + WORK_START_MINUTE
    end_minutes = start_minutes + round(hours * 60)
    end_h = (end_minutes // 60) % 24
    end_m = end_minutes % 60
    return f"~{WORK_START_HOUR:02d}:{WORK_START_MINUTE:02d} – {end_h:02d}:{end_m:02d}"


def compute_delta_pct(today: float, yesterday: float | None) -> float | None:
    """
    Compute percentage change vs yesterday.

    Returns None if yesterday is None or zero (avoids division by zero).
    Positive = today is higher.

    Example:
        >>> compute_delta_pct(600.0, 500.0)
        20.0
        >>> compute_delta_pct(400.0, 500.0)
        -20.0
        >>> compute_delta_pct(600.0, None) is None
        True
        >>> compute_delta_pct(600.0, 0.0) is None
        True
    """
    if yesterday is None or yesterday == 0.0:
        return None
    return round(((today - yesterday) / yesterday) * 100, 1)


def compute_mtd_earnings(
    month_df: pd.DataFrame, prices: dict[str, float]
) -> float:
    """
    Sum earnings across all rows in a month DataFrame.

    The DataFrame must have columns: rm_count, tc_count, rx_count.
    Returns 0.0 for an empty DataFrame.

    Example:
        >>> df = pd.DataFrame([{"rm_count": 1, "tc_count": 0, "rx_count": 0}])
        >>> compute_mtd_earnings(df, {"rm": 35.0, "tc": 25.0, "rx": 4.5})
        35.0
    """
    if month_df.empty:
        return 0.0
    return float(
        month_df["rm_count"].sum() * prices["rm"]
        + month_df["tc_count"].sum() * prices["tc"]
        + month_df["rx_count"].sum() * prices["rx"]
    )


def add_earnings_column(
    df: pd.DataFrame, prices: dict[str, float]
) -> pd.DataFrame:
    """
    Return a copy of the DataFrame with an 'earnings' column added.

    Each row: earnings = rm_count*rm_price + tc_count*tc_price + rx_count*rx_price.

    Example:
        >>> df = pd.DataFrame([{"rm_count": 2, "tc_count": 0, "rx_count": 0, "date": "2026-04-29"}])
        >>> add_earnings_column(df, {"rm": 35.0, "tc": 25.0, "rx": 4.5})["earnings"].iloc[0]
        70.0
    """
    df = df.copy()
    df["earnings"] = (
        df["rm_count"] * prices["rm"]
        + df["tc_count"] * prices["tc"]
        + df["rx_count"] * prices["rx"]
    )
    return df


# ---------------------------------------------------------------------------
# DB-dependent stats functions
# ---------------------------------------------------------------------------

def compute_daily_stats(
    conn: Any, date_str: str, prices: dict[str, float]
) -> dict[str, Any]:
    """
    Compute all statistics needed for the "Hoje" tab.

    Args:
        conn: Streamlit SQL connection.
        date_str: ISO-format date string (e.g. "2026-04-29").
        prices: Dict with keys "rm", "tc", "rx" and float values.

    Returns:
        dict with keys:
          - earnings_today: float — total R$ for the day
          - exam_count_today: int — total exams (RM+TC+RX)
          - rm_count: int
          - tc_count: int
          - rx_count: int
          - estimated_hours: float — decimal hours
          - estimated_time_range: str — "~08:00 – HH:MM"
          - yesterday_earnings: float | None — yesterday's earnings (None if no data)
          - delta_pct: float | None — % change vs yesterday (None if no basis)

    If no data exists for the given date_str, returns a dict with all
    counts and earnings set to zero, hours set to 0.0, and delta_pct=None.
    """
    today_data = load_daily(conn, date_str)

    if today_data is None:
        return {
            "earnings_today": 0.0,
            "exam_count_today": 0,
            "rm_count": 0,
            "tc_count": 0,
            "rx_count": 0,
            "estimated_hours": 0.0,
            "estimated_time_range": format_time_range(0.0),
            "yesterday_earnings": None,
            "delta_pct": None,
        }

    rm = int(today_data["rm_count"])
    tc = int(today_data["tc_count"])
    rx = int(today_data["rx_count"])

    earnings_today = compute_earnings(rm, tc, rx, prices)
    hours = estimate_hours(rm, tc, rx)
    time_range = format_time_range(hours)

    # Yesterday's earnings
    yesterday_str = _yesterday_str(date_str)
    yesterday_data = load_daily(conn, yesterday_str)
    yesterday_earnings: float | None = None
    if yesterday_data is not None:
        yesterday_earnings = compute_earnings(
            int(yesterday_data["rm_count"]),
            int(yesterday_data["tc_count"]),
            int(yesterday_data["rx_count"]),
            prices,
        )

    delta_pct = compute_delta_pct(earnings_today, yesterday_earnings)

    return {
        "earnings_today": earnings_today,
        "exam_count_today": rm + tc + rx,
        "rm_count": rm,
        "tc_count": tc,
        "rx_count": rx,
        "estimated_hours": hours,
        "estimated_time_range": time_range,
        "yesterday_earnings": yesterday_earnings,
        "delta_pct": delta_pct,
    }


def _yesterday_str(date_str: str) -> str:
    """Return ISO string for the day before date_str."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
