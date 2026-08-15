"""Tests for the month-tab UI decision logic.

Only pure decision helpers are tested; the Streamlit-rendering side of
``_render_rhythm_alert`` is intentionally excluded (no Streamlit runtime).
"""

from src.ui.month import _should_show_rhythm_alert


def _stats(**over):
    base = {
        "total_calendar_days": 30,
        "days_worked": 10,
        "elapsed_days": 15,
        "mtd_earnings": 20000.0,
        "remaining_days": 15,
        "pct_goal": 44.4,
        "daily_target_needed": 1666.7,
    }
    base.update(over)
    return base


def test_no_alert_when_month_just_started_few_elapsed_days():
    # 4 elapsed days, even behind → no alert (early-month suppression).
    assert _should_show_rhythm_alert(
        _stats(elapsed_days=4, mtd_earnings=1000.0, pct_goal=2.2), 45000.0
    ) is False


def test_alert_when_behind_pace_after_enough_elapsed_days():
    # 15 elapsed of 30 (expected 50%), mtd 20k of 45k goal → behind → alert.
    assert _should_show_rhythm_alert(
        _stats(elapsed_days=15, mtd_earnings=20000.0, pct_goal=44.4, remaining_days=15),
        45000.0,
    ) is True


def test_alert_shown_with_low_days_worked_but_high_elapsed():
    # The key change: few worked days (2) but many elapsed (15) still fires the
    # alert — early-month suppression is by elapsed days, not worked days
    # (consistent with the per-calendar-day model).
    assert _should_show_rhythm_alert(
        _stats(days_worked=2, elapsed_days=15, mtd_earnings=5000.0, pct_goal=11.1),
        45000.0,
    ) is True


def test_no_alert_when_goal_already_reached():
    assert _should_show_rhythm_alert(
        _stats(mtd_earnings=50000.0, pct_goal=111.0), 45000.0
    ) is False


def test_no_alert_when_no_remaining_days():
    assert _should_show_rhythm_alert(
        _stats(elapsed_days=30, remaining_days=0, mtd_earnings=20000.0, pct_goal=44.0),
        45000.0,
    ) is False


def test_no_alert_when_on_pace():
    # elapsed 15/30 → expected 50%; pct_goal 55 >= 50 → no ritmo → sem alerta.
    assert _should_show_rhythm_alert(
        _stats(elapsed_days=15, mtd_earnings=25000.0, pct_goal=55.0, remaining_days=15),
        45000.0,
    ) is False


def test_no_alert_when_total_calendar_days_zero():
    assert _should_show_rhythm_alert(
        _stats(total_calendar_days=0, elapsed_days=0, remaining_days=0), 45000.0
    ) is False