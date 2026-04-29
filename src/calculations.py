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

import calendar
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.db import load_daily, load_month

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
          - has_data: bool — whether a row exists for date_str

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
            "has_data": False,
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
        "has_data": True,
    }


def _yesterday_str(date_str: str) -> str:
    """Return ISO string for the day before date_str."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Monthly stats and targets
# ---------------------------------------------------------------------------

def compute_daily_target(monthly_goal: float, total_working_days: int) -> float:
    """
    Calculate the daily earnings target needed to meet the monthly goal.

    Example:
        >>> compute_daily_target(45000.0, 26)
        1730.7692307692307
    """
    if total_working_days <= 0:
        return 0.0
    return monthly_goal / total_working_days


def compute_monthly_stats(
    conn: Any, year_month: str, goal: float, prices: dict[str, float]
) -> dict[str, Any]:
    """
    Compute aggregate statistics for a given year-month.

    Uses Mon–Sat as working days (Sunday excluded).
    For past months, remaining_work_days and daily_target_needed are zero.

    Returns dict with keys:
        mtd_earnings, pct_goal, days_worked, total_work_days,
        remaining_work_days, daily_avg,
        daily_target_needed, projection_month_end
    """
    month_df = load_month(conn, year_month)
    mtd_earnings = compute_mtd_earnings(month_df, prices)
    pct_goal = (mtd_earnings / goal * 100.0) if goal > 0 else 0.0
    days_worked = len(month_df)

    # Parse year-month
    year, month = int(year_month[:4]), int(year_month[5:7])
    last_day = calendar.monthrange(year, month)[1]
    month_start = f"{year_month}-01"
    month_end = f"{year_month}-{last_day:02d}"

    # Total Mon–Sat days in the month
    working_dates = pd.bdate_range(
        start=month_start,
        end=month_end,
        freq="C",
        weekmask="Mon Tue Wed Thu Fri Sat",
    )
    total_work_days = len(working_dates)

    # Remaining working days (current month only)
    today = date.today()
    current_ym = today.isoformat()[:7]
    if year_month == current_ym:
        remaining_dates = pd.bdate_range(
            start=today,
            end=month_end,
            freq="C",
            weekmask="Mon Tue Wed Thu Fri Sat",
        )
        remaining_work_days = len(remaining_dates)
    else:
        remaining_work_days = 0

    daily_avg = mtd_earnings / days_worked if days_worked > 0 else 0.0

    remaining_needed = max(0.0, goal - mtd_earnings)
    daily_target_needed = (
        remaining_needed / remaining_work_days
        if remaining_work_days > 0
        else 0.0
    )

    projection_month_end = mtd_earnings + (daily_avg * remaining_work_days)

    return {
        "mtd_earnings": mtd_earnings,
        "pct_goal": pct_goal,
        "days_worked": days_worked,
        "total_work_days": total_work_days,
        "remaining_work_days": remaining_work_days,
        "daily_avg": daily_avg,
        "daily_target_needed": daily_target_needed,
        "projection_month_end": projection_month_end,
    }


# ---------------------------------------------------------------------------
# Historical stats (multi-month) — Sprint 4
# ---------------------------------------------------------------------------

def compute_historical_stats(
    conn: Any, year_month: str, goal: float, prices: dict[str, float]
) -> dict[str, Any]:
    """
    Load all months, compute MA7/MA30, WoW, MoM, modality mix, and
    consecutive-below-target. Returns dict with df, wow_change_pct,
    mom_change_pct, weekly_totals_last_4 (list of dicts),
    modality_mix_current ({"rm": pct, ...}), modality_mix_historical
    (month→mix), consecutive_below_target, current_month_stats.
    """
    months_df = conn.query(
        "SELECT DISTINCT substr(date, 1, 7) AS ym FROM daily_production ORDER BY ym",
        ttl=0,
    )
    if months_df.empty:
        return _empty_historical_stats(conn, year_month, goal, prices)

    all_months: list[str] = months_df["ym"].tolist()
    month_frames: list[pd.DataFrame] = []
    for ym in all_months:
        mdf = load_month(conn, ym)
        if mdf.empty:
            continue
        mdf = add_earnings_column(mdf, prices)
        month_frames.append(mdf)

    if not month_frames:
        return _empty_historical_stats(conn, year_month, goal, prices)

    df = pd.concat(month_frames, ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)
    df["date_dt"] = pd.to_datetime(df["date"])

    df["ma7"] = df["earnings"].rolling(window=7, min_periods=1).mean()
    df["ma30"] = df["earnings"].rolling(window=30, min_periods=1).mean()

    df["week"] = df["date_dt"].dt.isocalendar().week
    df["iso_year"] = df["date_dt"].dt.isocalendar().year

    weekly_agg = (
        df.groupby(["iso_year", "week"], sort=False)
        .agg(
            total_earnings=("earnings", "sum"),
            rm_count=("rm_count", "sum"),
            tc_count=("tc_count", "sum"),
            rx_count=("rx_count", "sum"),
            first_date=("date_dt", "min"),
        )
        .reset_index()
        .sort_values("first_date")
    )

    weekly_agg["week_label"] = weekly_agg["first_date"].apply(
        lambda dt: f"Semana {dt.isocalendar().week} — {dt.strftime('%d/%m')}"
        if pd.notna(dt) else "—"
    )
    weekly_totals_last_4: list[dict[str, Any]] = [
        {"week_label": str(r["week_label"]),
         "total_earnings": float(r["total_earnings"]),
         "rm_count": int(r["rm_count"]),
         "tc_count": int(r["tc_count"]),
         "rx_count": int(r["rx_count"])}
        for _, r in weekly_agg.tail(4).iterrows()
    ]

    wow_change_pct: float | None = None
    if len(weekly_agg) >= 2:
        last, prev = weekly_agg.iloc[-1], weekly_agg.iloc[-2]
        if prev["total_earnings"] > 0:
            wow_change_pct = float((last["total_earnings"] - prev["total_earnings"]) / prev["total_earnings"] * 100)

    monthly = (
        df.groupby(df["date"].str[:7])
        .agg(total_earnings=("earnings", "sum"))
        .reset_index()
    )
    monthly.columns = ["ym", "total_earnings"]
    monthly = monthly.sort_values("ym")

    mom_change_pct: float | None = None
    monthly_idx = monthly.set_index("ym")
    if year_month in monthly_idx.index:
        pos = monthly_idx.index.get_loc(year_month)
        if isinstance(pos, int) and pos > 0:
            prev_ym = monthly_idx.index[pos - 1]  # type: ignore[assignment]
            prev_total = float(monthly_idx.loc[prev_ym, "total_earnings"])
            curr_total = float(monthly_idx.loc[year_month, "total_earnings"])
            if prev_total > 0:
                mom_change_pct = float((curr_total - prev_total) / prev_total * 100)

    def _modality_mix(sdf: pd.DataFrame) -> dict[str, float]:
        """Revenue-share percentages for RM, TC, RX."""
        rev = {m: float(sdf[f"{m}_count"].sum()) * prices[m] for m in ("rm", "tc", "rx")}
        total = sum(rev.values())
        if total == 0.0:
            return {"rm": 0.0, "tc": 0.0, "rx": 0.0}
        return {m: round(rev[m] / total * 100, 1) for m in ("rm", "tc", "rx")}

    current_month_df = df[df["date"].str[:7] == year_month]
    modality_mix_current = _modality_mix(current_month_df)

    modality_mix_historical: dict[str, dict[str, float]] = {}
    for ym in all_months:
        ym_df = df[df["date"].str[:7] == ym]
        modality_mix_historical[ym] = _modality_mix(ym_df)

    current_stats = compute_monthly_stats(conn, year_month, goal, prices)
    total_work_days = current_stats["total_work_days"]
    daily_target = compute_daily_target(goal, total_work_days)

    curr_sorted = current_month_df.sort_values("date", ascending=False)
    consecutive_below_target = 0
    for _, row in curr_sorted.iterrows():
        if float(row["earnings"]) < daily_target:
            consecutive_below_target += 1
        else:
            break

    return {
        "df": df,
        "wow_change_pct": wow_change_pct, "mom_change_pct": mom_change_pct,
        "weekly_totals_last_4": weekly_totals_last_4,
        "modality_mix_current": modality_mix_current,
        "modality_mix_historical": modality_mix_historical,
        "consecutive_below_target": consecutive_below_target,
        "current_month_stats": current_stats,
    }


def _empty_historical_stats(
    conn: Any, year_month: str, goal: float, prices: dict[str, float]
) -> dict[str, Any]:
    """Minimal stats dict when no historical data exists."""
    current_stats = compute_monthly_stats(conn, year_month, goal, prices)
    return {
        "df": pd.DataFrame(columns=[
            "date", "rm_count", "tc_count", "rx_count",
            "earnings", "date_dt", "ma7", "ma30", "week", "iso_year",
        ]),
        "wow_change_pct": None, "mom_change_pct": None,
        "weekly_totals_last_4": [],
        "modality_mix_current": {"rm": 0.0, "tc": 0.0, "rx": 0.0},
        "modality_mix_historical": {},
        "consecutive_below_target": 0,
        "current_month_stats": current_stats,
    }
