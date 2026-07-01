"""Tests for src.insights_rules — v2 dynamic modality insights."""

from src.insights_rules import generate_rule_insights


def _make_stats(
    mtd_earnings=0.0,
    pct_goal=0.0,
    days_worked=0,
    remaining_days=0,
    total_calendar_days=30,
    daily_avg=0.0,
    daily_target_needed=0.0,
    projection_month_end=0.0,
    wow_change_pct=None,
    mom_change_pct=None,
    module_mix_current=None,
    modality_mix_historical=None,
    consecutive_below_target=0,
):
    """Factory for stats dict matching compute_historical_stats output."""
    return {
        "current_month_stats": {
            "mtd_earnings": mtd_earnings,
            "pct_goal": pct_goal,
            "days_worked": days_worked,
            "remaining_days": remaining_days,
            "total_calendar_days": total_calendar_days,
            "daily_avg": daily_avg,
            "daily_target_needed": daily_target_needed,
            "projection_month_end": projection_month_end,
        },
        "wow_change_pct": wow_change_pct,
        "mom_change_pct": mom_change_pct,
        "modality_mix_current": module_mix_current or {},
        "modality_mix_historical": modality_mix_historical or {},
        "consecutive_below_target": consecutive_below_target,
    }


DEFAULT_ACTIVE_MODS = [
    {"slug": "ressonancia_magnetica", "label": "Ressonância Magnética",
     "price": 35.0, "exams_per_hour": 7.5, "active": 1, "sort_order": 4},
    {"slug": "tc_geral", "label": "TC Geral",
     "price": 25.0, "exams_per_hour": 7.5, "active": 1, "sort_order": 2},
    {"slug": "radiografia", "label": "Radiografia",
     "price": 4.5, "exams_per_hour": 75.0, "active": 1, "sort_order": 8},
]


class TestGenerateRuleInsights:
    def test_no_days_worked(self):
        stats = _make_stats(days_worked=0)
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "barra lateral" in result.lower()

    def test_success_tone(self):
        stats = _make_stats(
            mtd_earnings=50000, pct_goal=111.1, days_worked=20,
            remaining_days=0, total_calendar_days=30,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "bateu a meta" in result.lower()

    def test_on_track(self):
        stats = _make_stats(
            mtd_earnings=30000, pct_goal=66.7, days_worked=20,
            remaining_days=10, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=1500,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "ritmo adequado" in result.lower()

    def test_warning_tone(self):
        stats = _make_stats(
            mtd_earnings=15000, pct_goal=33.3, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1400, daily_target_needed=2000,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "acima do seu ritmo" in result.lower()

    def test_danger_tone(self):
        stats = _make_stats(
            mtd_earnings=5000, pct_goal=11.1, days_worked=10,
            remaining_days=20, total_calendar_days=30,
            daily_avg=500, daily_target_needed=2000,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "abaixo da meta" in result.lower()

    def test_wow_trend(self):
        stats = _make_stats(
            mtd_earnings=20000, pct_goal=44.4, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1333, daily_target_needed=1667,
            wow_change_pct=12.5,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "crescimento" in result.lower()
        assert "12.5%" in result

    def test_consecutive_below_target(self):
        stats = _make_stats(
            mtd_earnings=20000, pct_goal=44.4, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1333, daily_target_needed=1667,
            consecutive_below_target=4,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "dias consecutivos abaixo da meta" in result.lower()

    def test_modality_mix_shift(self):
        stats = _make_stats(
            mtd_earnings=20000, pct_goal=44.4, days_worked=20,
            remaining_days=10, total_calendar_days=30,
            daily_avg=1000, daily_target_needed=2500,
            module_mix_current={
                "ressonancia_magnetica": 60.0,
                "tc_geral": 30.0,
                "radiografia": 10.0,
            },
            modality_mix_historical={
                "2026-03": {
                    "ressonancia_magnetica": 40.0,
                    "tc_geral": 40.0,
                    "radiografia": 20.0,
                },
                "2026-04": {
                    "ressonancia_magnetica": 60.0,
                    "tc_geral": 30.0,
                    "radiografia": 10.0,
                },
            },
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "mudança no mix" in result.lower()

    def test_suggestion_has_highest_price_modality(self):
        stats = _make_stats(
            mtd_earnings=5000, pct_goal=11.1, days_worked=10,
            remaining_days=20, total_calendar_days=30,
            daily_avg=500, daily_target_needed=2000,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Ressonância Magnética" in result or "priorize" in result.lower()

    def test_active_modalities_list_used_for_labels(self):
        """Verify the insight uses modality labels from active_modalities list."""
        stats = _make_stats(
            mtd_earnings=20000, pct_goal=44.4, days_worked=20,
            remaining_days=10, total_calendar_days=30,
            daily_avg=1000, daily_target_needed=2500,
            module_mix_current={
                "ressonancia_magnetica": 50.0,
                "tc_geral": 30.0,
                "radiografia": 20.0,
            },
            modality_mix_historical={
                "2026-03": {
                    "ressonancia_magnetica": 30.0,
                    "tc_geral": 40.0,
                    "radiografia": 30.0,
                },
                "2026-04": {
                    "ressonancia_magnetica": 50.0,
                    "tc_geral": 30.0,
                    "radiografia": 20.0,
                },
            },
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Ressonância Magnética" in result or "TC Geral" in result
