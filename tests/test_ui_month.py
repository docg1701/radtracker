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
    # 4 dias decorridos, mesmo atrás → sem alerta (supressão early-month).
    assert _should_show_rhythm_alert(
        _stats(elapsed_days=4, mtd_earnings=1000.0, pct_goal=2.2), 45000.0
    ) is False


def test_alert_when_behind_pace_after_enough_elapsed_days():
    # 15 decorridos de 30 (expected 50%), mtd 20k de meta 45k → atrás → alerta.
    assert _should_show_rhythm_alert(
        _stats(elapsed_days=15, mtd_earnings=20000.0, pct_goal=44.4, remaining_days=15),
        45000.0,
    ) is True


def test_alert_shown_with_low_days_worked_but_high_elapsed():
    # A mudança-chave: poucos dias trabalhados (2) mas muitos decorridos (15)
    # ainda dispara alerta — a supressão early-month é por dias decorridos,
    # não por dias trabalhados (consistente com o modelo por dia corrido).
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