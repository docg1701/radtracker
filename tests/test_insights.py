"""Tests for src.insights_rules — rule-based insight generation."""

from src.insights_rules import generate_rule_insights


def _make_stats(pct_goal: float, mtd: float = 22500.0, days_worked: int = 13,
                total_days: int = 30, remaining_calendar_days: int = 17,
                daily_target_needed: float = 1730.77,
                projection_month_end: float = 45000.0,
                daily_avg: float | None = None,
                wow: float | None = None,
                mom: float | None = None, consecutive: int = 0,
                mix_current: dict | None = None,
                mix_history: dict | None = None) -> dict:
    """Build a stats dict matching compute_historical_stats output."""
    default_mix = {"rm": 60.0, "tc": 25.0, "rx": 15.0}
    avg = daily_avg if daily_avg is not None else (
        mtd / days_worked if days_worked > 0 else 0.0)
    return {
        "current_month_stats": {
            "pct_goal": pct_goal,
            "mtd_earnings": mtd,
            "days_worked": days_worked,
            "total_calendar_days": total_days,
            "remaining_calendar_days": remaining_calendar_days,
            "daily_target_needed": daily_target_needed,
            "daily_avg": avg,
            "projection_month_end": projection_month_end,
        },
        "wow_change_pct": wow,
        "mom_change_pct": mom,
        "modality_mix_current": mix_current or default_mix,
        "modality_mix_historical": mix_history or {},
        "consecutive_below_target": consecutive,
    }


class TestTones:
    def test_success_when_goal_hit(self):
        text = generate_rule_insights(_make_stats(pct_goal=120.0, mtd=54000.0,
                                         daily_target_needed=0.0))
        assert ":material/check_circle:" in text
        assert "já bateu a meta" in text.lower()

    def test_on_track_when_pace_sufficient(self):
        # daily_needed (1000) < daily_avg (1100) * 1.1 → on_track
        text = generate_rule_insights(_make_stats(
            pct_goal=50.0, mtd=22500.0, daily_avg=1500.0,
            daily_target_needed=1000.0, projection_month_end=48000.0))
        assert "Ritmo adequado" in text

    def test_warning_when_pace_needs_stretch(self):
        # daily_needed (2000)  / daily_avg (1500) = 1.33 → warning
        text = generate_rule_insights(_make_stats(
            pct_goal=40.0, mtd=18000.0, daily_avg=1500.0,
            daily_target_needed=2000.0, projection_month_end=35000.0))
        assert "projeção" in text.lower()

    def test_danger_when_gap_unrealistic(self):
        # daily_needed (5000) / daily_avg (1500) = 3.33 → danger
        text = generate_rule_insights(_make_stats(
            pct_goal=20.0, mtd=9000.0, daily_avg=1500.0,
            daily_target_needed=5000.0, projection_month_end=20000.0))
        assert "abaixo da meta" in text.lower()


class TestContent:
    def test_contains_formatted_currency(self):
        text = generate_rule_insights(_make_stats(pct_goal=50.0, mtd=22500.0,
                                         daily_avg=1730.0))
        assert "R$ 22.500,00" in text

    def test_contains_days_worked(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=60.0, days_worked=15, daily_avg=2000.0))
        assert "15" in text

    def test_days_plural_correct(self):
        text = generate_rule_insights(_make_stats(
            pct_goal=95.0, mtd=42750.0, remaining_calendar_days=1,
            daily_avg=2000.0, daily_target_needed=0))
        assert "dias trabalhados" in text
        # Singular: "restante" for 1 remaining day
        assert "restante" in text
        assert "restantes" not in text


class TestSuggestions:
    def test_success_suggestion(self):
        text = generate_rule_insights(_make_stats(
            pct_goal=120.0, mtd=54000.0, daily_target_needed=0.0))
        assert "Sugestão" in text
        assert "consolidar" in text.lower()

    def test_danger_suggestion_actionable(self):
        text = generate_rule_insights(_make_stats(
            pct_goal=10.0, mtd=4500.0, daily_avg=1500.0,
            daily_target_needed=5000.0))
        assert "Sugestão" in text
        assert "RM" in text


class TestWowTrend:
    def test_wow_trend_up(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=60.0, daily_avg=2000.0, wow=10.5))
        assert ":material/trending_up:" in text
        assert "crescimento" in text

    def test_wow_trend_down(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=60.0, daily_avg=2000.0, wow=-5.0))
        assert ":material/trending_down:" in text
        assert "queda" in text

    def test_wow_trend_none(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=60.0, daily_avg=2000.0, wow=None))
        assert "Semana a semana" not in text


class TestMomTrend:
    def test_mom_trend_up(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=60.0, daily_avg=2000.0, mom=15.0))
        assert ":material/trending_up:" in text
        assert "crescimento" in text
        assert "Mês a mês" in text

    def test_mom_trend_none(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=60.0, daily_avg=2000.0, mom=None))
        assert "Mês a mês" not in text


class TestConsecutive:
    def test_consecutive_below_trigger(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=50.0, daily_avg=2000.0, consecutive=4))
        assert ":material/warning:" in text
        assert "consecutivos" in text

    def test_consecutive_below_no_trigger(self):
        text = generate_rule_insights(
            _make_stats(pct_goal=50.0, daily_avg=2000.0, consecutive=1))
        assert "consecutivos" not in text


class TestModalityMix:
    def test_modality_mix_shift_detected(self):
        stats = _make_stats(
            pct_goal=60.0, daily_avg=2000.0,
            days_worked=13,
            mix_current={"rm": 80.0, "tc": 15.0, "rx": 5.0},
            mix_history={
                "2026-01": {"rm": 60.0, "tc": 25.0, "rx": 15.0},
                "2026-02": {"rm": 60.0, "tc": 25.0, "rx": 15.0},
            },
        )
        text = generate_rule_insights(stats)
        assert "Mudança no mix" in text

    def test_modality_mix_no_shift(self):
        stats = _make_stats(
            pct_goal=60.0, daily_avg=2000.0,
            days_worked=13,
            mix_current={"rm": 62.0, "tc": 24.0, "rx": 14.0},
            mix_history={
                "2026-01": {"rm": 60.0, "tc": 25.0, "rx": 15.0},
                "2026-02": {"rm": 60.0, "tc": 25.0, "rx": 15.0},
            },
        )
        text = generate_rule_insights(stats)
        assert "Mudança no mix" not in text


class TestEmptyStats:
    def test_empty_stats_returns_message(self):
        stats = {"current_month_stats": None}
        text = generate_rule_insights(stats)
        assert "barra lateral" in text
