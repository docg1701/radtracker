"""
Business-logic calculations for radtracker — v2 dynamic modalities.

Pure functions for earnings, hours, projections, and moving averages.
DB-dependent functions accept a Streamlit connection as first parameter.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.db import load_daily_items, load_month_items

# ---------------------------------------------------------------------------
# Helper: build slug→price and slug→exams_per_hour lookups
# ---------------------------------------------------------------------------

def _build_lookups(
    modalities: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    """Return (slug→price, slug→exams_per_hour) dicts from modality list."""
    prices: dict[str, float] = {}
    eph: dict[str, float] = {}
    for m in modalities:
        prices[m["slug"]] = float(m["price"])
        eph[m["slug"]] = float(m["exams_per_hour"])
    return prices, eph


# ---------------------------------------------------------------------------
# Pure functions (no DB access)
# ---------------------------------------------------------------------------

def compute_earnings(
    counts: dict[str, int], prices: dict[str, float]
) -> float:
    """
    Calculate total earnings from modality counts and prices.

    Example:
        >>> compute_earnings({"ressonancia_magnetica": 8, "tc_geral": 6},
        ...                  {"ressonancia_magnetica": 35.0, "tc_geral": 25.0})
        430.0
    """
    return float(sum(counts.get(slug, 0) * price for slug, price in prices.items()))


def estimate_hours(
    counts: dict[str, int], exams_per_hour: dict[str, float]
) -> float:
    """
    Estimate work hours based on per-modality productivity rates.

    Example:
        >>> estimate_hours({"ressonancia_magnetica": 15, "tc_geral": 15},
        ...                {"ressonancia_magnetica": 7.5, "tc_geral": 7.5})
        4.0
    """
    total = 0.0
    for slug, rate in exams_per_hour.items():
        if rate > 0:
            total += counts.get(slug, 0) / rate
    return round(total, 2)


def compute_delta_pct(today: float, yesterday: float | None) -> float | None:
    """
    Compute percentage change vs yesterday. None if no basis.

    Example:
        >>> compute_delta_pct(600.0, 500.0)
        20.0
        >>> compute_delta_pct(600.0, None) is None
        True
    """
    if yesterday is None or yesterday == 0.0:
        return None
    return round(((today - yesterday) / yesterday) * 100, 1)


def compute_daily_target(monthly_goal: float, total_calendar_days: int) -> float:
    """Daily earnings target to meet monthly goal."""
    if total_calendar_days <= 0:
        return 0.0
    return monthly_goal / total_calendar_days


# ---------------------------------------------------------------------------
# DB-dependent: daily stats
# ---------------------------------------------------------------------------

def compute_daily_stats(
    conn: Any,
    date_str: str,
    active_modalities: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute all statistics for the "Hoje" tab.

    Accepts a list of active modality dicts (slug, label, price, exams_per_hour).

    Returns dict with:
      earnings_today, exam_count_today, estimated_hours,
      modality_counts (slug→count),
      modality_labels (slug→label), yesterday_earnings, delta_pct, has_data.
    """
    prices, eph = _build_lookups(active_modalities)
    counts = load_daily_items(conn, date_str)
    has_data = bool(counts)

    if not has_data:
        return {
            "earnings_today": 0.0,
            "exam_count_today": 0,
            "estimated_hours": 0.0,
            "modality_counts": {},
            "modality_labels": {m["slug"]: m["label"] for m in active_modalities},
            "yesterday_earnings": None,
            "delta_pct": None,
            "has_data": False,
        }

    earnings_today = compute_earnings(counts, prices)
    hours = estimate_hours(counts, eph)
    exam_count_today = sum(counts.values())

    # Yesterday
    yesterday_str = _yesterday_str(date_str)
    yesterday_counts = load_daily_items(conn, yesterday_str)
    yesterday_earnings: float | None = None
    if yesterday_counts:
        yesterday_earnings = compute_earnings(yesterday_counts, prices)

    delta_pct = compute_delta_pct(earnings_today, yesterday_earnings)

    return {
        "earnings_today": earnings_today,
        "exam_count_today": exam_count_today,
        "estimated_hours": hours,
        "modality_counts": counts,
        "modality_labels": {m["slug"]: m["label"] for m in active_modalities},
        "yesterday_earnings": yesterday_earnings,
        "delta_pct": delta_pct,
        "has_data": True,
    }


def _yesterday_str(date_str: str) -> str:
    """Return ISO string for the day before date_str."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Monthly stats
# ---------------------------------------------------------------------------

def _month_time_window(
    year_month: str, today: date, has_today_data: bool,
) -> tuple[int, int]:
    """Return (elapsed_days, remaining_days) for a year-month in dias corridos.

    Every day is work-eligible. For the current month, today counts as elapsed
    (and NOT remaining) when it already has production; otherwise today counts
    as remaining (and not elapsed). Past or other months are fully elapsed with
    zero remaining. ``elapsed_days + remaining_days == total_calendar_days``.

    Example:
        >>> _month_time_window("2026-06", date(2026, 6, 29), has_today_data=True)
        (29, 1)
    """
    year, month = int(year_month[:4]), int(year_month[5:7])
    total = calendar.monthrange(year, month)[1]
    if year_month != today.isoformat()[:7]:
        return total, 0
    if has_today_data:
        return today.day, total - today.day
    elapsed = max(0, today.day - 1)
    return elapsed, total - elapsed


def daily_avg_for_month(
    mtd_earnings: float, year_month: str, today: date, has_today_data: bool,
) -> float:
    """Productivity per dia corrido for a month.

    Current month uses elapsed days (today counts when it has production);
    past months use the full month length. Returns 0.0 when no days elapsed.

    Example:
        >>> daily_avg_for_month(1000.0, "2026-06", date(2026,6,15), True)
        66.666...  # 1000 / 15 elapsed
    """
    elapsed, _ = _month_time_window(year_month, today, has_today_data)
    return mtd_earnings / elapsed if elapsed > 0 else 0.0


def compute_monthly_stats(
    conn: Any,
    year_month: str,
    goal: float,
    active_modalities: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    """Compute aggregate statistics for a year-month in dias corridos.

    ``today`` is injectable for deterministic tests; defaults to date.today().

    Returns: mtd_earnings, pct_goal, days_worked, total_calendar_days,
             elapsed_days, remaining_days, daily_avg, daily_target_needed,
             projection_month_end.

    days_worked (days with >=1 exam) is a displayed statistic only; daily_avg,
    daily_target_needed and projection all use dias corridos so the units stay
    consistent (R$/dia corrido in both numerator and denominator).
    """
    prices, _ = _build_lookups(active_modalities)
    month_df = load_month_items(conn, year_month)

    # Compute MTD earnings
    mtd_earnings = 0.0
    if not month_df.empty:
        for _, row in month_df.iterrows():
            slug = row["modality_slug"]
            if slug in prices:
                mtd_earnings += int(row["count"]) * prices[slug]

    pct_goal = (mtd_earnings / goal * 100.0) if goal > 0 else 0.0

    # Days worked = distinct dates with production (displayed statistic only)
    days_worked = month_df["date"].nunique() if not month_df.empty else 0

    today = today or date.today()
    today_str = today.isoformat()
    has_today_data = (
        not month_df.empty and today_str in set(month_df["date"].tolist())
    )
    elapsed_days, remaining_days = _month_time_window(
        year_month, today, has_today_data
    )
    total_calendar_days = elapsed_days + remaining_days

    # Productivity per dia corrido (gaps count as zero-production days)
    daily_avg = mtd_earnings / elapsed_days if elapsed_days > 0 else 0.0

    remaining_needed = max(0.0, goal - mtd_earnings)
    daily_target_needed = (
        remaining_needed / remaining_days if remaining_days > 0 else 0.0
    )

    projection_month_end = mtd_earnings + (daily_avg * remaining_days)

    return {
        "goal": goal,
        "mtd_earnings": mtd_earnings,
        "pct_goal": pct_goal,
        "days_worked": days_worked,
        "total_calendar_days": total_calendar_days,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "daily_avg": daily_avg,
        "daily_target_needed": daily_target_needed,
        "projection_month_end": projection_month_end,
    }


# ---------------------------------------------------------------------------
# Historical stats (multi-month)
# ---------------------------------------------------------------------------

def compute_historical_stats(
    conn: Any,
    year_month: str,
    goal: float,
    active_modalities: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Load all months, compute MA7/MA30, WoW, MoM, modality mix, etc.

    Uses daily_production_items (v2 normalized schema).
    """
    prices, _ = _build_lookups(active_modalities)

    # Build a daily earnings dataframe from items table
    months_df = conn.query(
        "SELECT DISTINCT substr(date, 1, 7) AS ym "
        "FROM daily_production_items ORDER BY ym",
        ttl=0,
    )
    if months_df.empty:
        return _empty_historical_stats(conn, year_month, goal, active_modalities)

    all_months: list[str] = months_df["ym"].tolist()

    # Load all data and compute daily earnings
    frames: list[pd.DataFrame] = []
    for ym in all_months:
        mdf = load_month_items(conn, ym)
        if mdf.empty:
            continue
        frames.append(mdf)

    if not frames:
        return _empty_historical_stats(conn, year_month, goal, active_modalities)

    items_df = pd.concat(frames, ignore_index=True)

    # Pivot to daily earnings
    daily_earnings = _compute_daily_earnings_from_items(items_df, prices)
    if daily_earnings.empty:
        return _empty_historical_stats(conn, year_month, goal, active_modalities)

    df = daily_earnings.sort_values("date").reset_index(drop=True)
    df["date_dt"] = pd.to_datetime(df["date"])

    # MA7 / MA30
    df["ma7"] = df["earnings"].rolling(window=7, min_periods=1).mean()
    df["ma30"] = df["earnings"].rolling(window=30, min_periods=1).mean()

    # Week grouping
    df["week"] = df["date_dt"].dt.isocalendar().week
    df["iso_year"] = df["date_dt"].dt.isocalendar().year

    weekly_agg = (
        df.groupby(["iso_year", "week"], sort=False)
        .agg(total_earnings=("earnings", "sum"),
             first_date=("date_dt", "min"))
        .reset_index()
        .sort_values("first_date")
    )

    weekly_agg["week_label"] = weekly_agg["first_date"].apply(
        lambda dt: f"Semana {dt.isocalendar().week} — {dt.strftime('%d/%m')}"
        if pd.notna(dt) else "—"
    )
    weekly_totals_last_4: list[dict[str, Any]] = [
        {"week_label": str(r["week_label"]),
         "total_earnings": float(r["total_earnings"])}
        for _, r in weekly_agg.tail(4).iterrows()
    ]

    # WoW
    wow_change_pct: float | None = None
    if len(weekly_agg) >= 2:
        last, prev = weekly_agg.iloc[-1], weekly_agg.iloc[-2]
        if prev["total_earnings"] > 0:
            wow_change_pct = float(
                (last["total_earnings"] - prev["total_earnings"])
                / prev["total_earnings"] * 100
            )

    # Monthly aggregation
    monthly = (
        df.groupby(df["date"].str[:7])
        .agg(total_earnings=("earnings", "sum"))
        .reset_index()
    )
    monthly.columns = ["ym", "total_earnings"]
    monthly = monthly.sort_values("ym")

    # MoM
    mom_change_pct: float | None = None
    monthly_idx = monthly.set_index("ym")
    if year_month in monthly_idx.index:
        pos = monthly_idx.index.get_loc(year_month)
        if isinstance(pos, int) and pos > 0:
            prev_ym = monthly_idx.index[pos - 1]
            prev_total = float(monthly_idx.loc[prev_ym, "total_earnings"])
            curr_total = float(monthly_idx.loc[year_month, "total_earnings"])
            if prev_total > 0:
                mom_change_pct = float((curr_total - prev_total) / prev_total * 100)

    # Modality mix from v2 items
    def _modality_mix(ym: str) -> dict[str, float]:
        ym_items = items_df[items_df["date"].str[:7] == ym]
        if ym_items.empty:
            return {m["slug"]: 0.0 for m in active_modalities}
        rev: dict[str, float] = {}
        for _, row in ym_items.iterrows():
            slug = str(row["modality_slug"])
            if slug in prices:
                rev[slug] = rev.get(slug, 0.0) + int(row["count"]) * prices[slug]
        total = sum(rev.values())
        if total == 0.0:
            return {m["slug"]: 0.0 for m in active_modalities}
        return {slug: round(val / total * 100, 1) for slug, val in rev.items()}

    current_month_df = df[df["date"].str[:7] == year_month]
    modality_mix_current = _modality_mix(year_month)

    modality_mix_historical: dict[str, dict[str, float]] = {}
    for ym in all_months:
        modality_mix_historical[ym] = _modality_mix(ym)

    current_stats = compute_monthly_stats(conn, year_month, goal, active_modalities)
    total_calendar_days = current_stats["total_calendar_days"]
    daily_target = compute_daily_target(goal, total_calendar_days)

    curr_sorted = current_month_df.sort_values("date", ascending=False)
    consecutive_below_target = 0
    for _, row in curr_sorted.iterrows():
        if float(row["earnings"]) < daily_target:
            consecutive_below_target += 1
        else:
            break

    return {
        "df": df,
        "year_month": year_month,
        "wow_change_pct": wow_change_pct,
        "mom_change_pct": mom_change_pct,
        "weekly_totals_last_4": weekly_totals_last_4,
        "modality_mix_current": modality_mix_current,
        "modality_mix_historical": modality_mix_historical,
        "consecutive_below_target": consecutive_below_target,
        "current_month_stats": current_stats,
    }


def _compute_daily_earnings_from_items(
    items_df: pd.DataFrame, prices: dict[str, float]
) -> pd.DataFrame:
    """Aggregate daily_production_items rows into daily earnings + per-modality counts.

    Returns DataFrame with columns: date, earnings, plus one count column per slug.
    """
    if items_df.empty:
        return pd.DataFrame()

    # Compute revenue per row
    items_df = items_df.copy()
    items_df["revenue"] = items_df.apply(
        lambda r: int(r["count"]) * prices.get(str(r["modality_slug"]), 0.0), axis=1
    )

    # Sum revenue by date → earnings
    daily = items_df.groupby("date", as_index=False).agg(earnings=("revenue", "sum"))

    # Add per-modality count columns (pivot + merge)
    pivot = items_df.pivot_table(
        index="date", columns="modality_slug", values="count",
        aggfunc="sum", fill_value=0,
    )
    daily = daily.merge(pivot, on="date", how="left")

    return daily


def _empty_historical_stats(
    conn: Any, year_month: str, goal: float,
    active_modalities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Minimal stats dict when no historical data exists."""
    current_stats = compute_monthly_stats(conn, year_month, goal, active_modalities)
    return {
        "df": pd.DataFrame(columns=[
            "date", "earnings", "date_dt", "ma7", "ma30", "week", "iso_year",
        ]),
        "year_month": year_month,
        "wow_change_pct": None, "mom_change_pct": None,
        "weekly_totals_last_4": [],
        "modality_mix_current": {},
        "modality_mix_historical": {},
        "consecutive_below_target": 0,
        "current_month_stats": current_stats,
    }
