"""Tests for src.insights_rules — factual, scenario-based insights (v2.1)."""

from datetime import date

from src.calculations import compute_monthly_stats
from src.db import init_db, upsert_daily_items
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
    goal=0.0,
    wow_change_pct=None,
    mom_change_pct=None,
    module_mix_current=None,
    modality_mix_historical=None,
    consecutive_below_target=0,
    elapsed_days=None,
    current_month_daily_std=None,
    prev_month_earnings=None,
):
    """Factory for stats dict matching compute_historical_stats output."""
    return {
        "current_month_stats": {
            "mtd_earnings": mtd_earnings,
            "pct_goal": pct_goal,
            "days_worked": days_worked,
            "remaining_days": remaining_days,
            "total_calendar_days": total_calendar_days,
            "elapsed_days": (
                elapsed_days if elapsed_days is not None
                else total_calendar_days - remaining_days
            ),
            "daily_avg": daily_avg,
            "daily_target_needed": daily_target_needed,
            "projection_month_end": projection_month_end,
            "goal": goal,
        },
        "wow_change_pct": wow_change_pct,
        "mom_change_pct": mom_change_pct,
        "modality_mix_current": module_mix_current or {},
        "modality_mix_historical": modality_mix_historical or {},
        "consecutive_below_target": consecutive_below_target,
        "current_month_daily_std": current_month_daily_std,
        "prev_month_earnings": prev_month_earnings,
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

    def test_goal_met_no_remaining(self):
        stats = _make_stats(
            mtd_earnings=50000, pct_goal=111.1, days_worked=20,
            remaining_days=0, total_calendar_days=30,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "R$ 50.000,00" in result
        assert "acima" in result

    def test_projection_three_scenarios(self):
        # mtd=15000, daily_avg=1500, remaining=15, std=500, goal=45000
        # conserv = 15000 + (1500-500)*15 = 30000; base = 15000+1500*15 = 37500;
        # optim = 15000 + (1500+500)*15 = 45000
        stats = _make_stats(
            mtd_earnings=15000, pct_goal=33.3, days_worked=10,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=2000,
            projection_month_end=37500.0, goal=45000.0,
            current_month_daily_std=500.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Conservador: R$ 30.000,00" in result
        assert "Base (média atual): R$ 37.500,00" in result
        assert "Otimista: R$ 45.000,00" in result
        assert "Mais provável: **base**." in result

    def test_required_per_day_when_behind(self):
        stats = _make_stats(
            mtd_earnings=15000, pct_goal=33.3, days_worked=10,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=2000,
            projection_month_end=37500.0, goal=45000.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Faltam R$ 30.000,00" in result
        assert "R$ 2.000,00/dia" in result

    def test_mom_shown(self):
        stats = _make_stats(
            mtd_earnings=22500, pct_goal=50.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=1500,
            projection_month_end=45000.0, mom_change_pct=12.5,
            prev_month_earnings=20000.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "MoM: +12,5%" in result
        assert "R$ 22.500,00 vs R$ 20.000,00" in result

    def test_mix_top3_shown(self):
        stats = _make_stats(
            mtd_earnings=22500, pct_goal=50.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=1500,
            projection_month_end=45000.0,
            module_mix_current={
                "ressonancia_magnetica": 60.0,
                "tc_geral": 30.0,
                "radiografia": 10.0,
            },
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Ressonância Magnética 60%" in result
        assert "TC Geral 30%" in result
        assert "Radiografia 10%" in result

    def test_consecutive_below_target_shown(self):
        stats = _make_stats(
            mtd_earnings=22500, pct_goal=50.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=1500,
            projection_month_end=45000.0, consecutive_below_target=4,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "4 dias consecutivos abaixo da meta diária." in result

    def test_singular_day_counting(self):
        # days_worked=1 and elapsed=1 → singular forms, no plural leak.
        stats = _make_stats(
            mtd_earnings=1500, pct_goal=3.0, days_worked=1,
            remaining_days=29, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=1666.67,
            projection_month_end=45000.0, goal=50000.0,
            elapsed_days=1,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "1 dia trabalhado" in result
        assert "1 decorrido" in result
        assert "29 restantes" in result
        assert "1 dias trabalhados" not in result
        assert "1 decorridos" not in result

    def test_singular_remaining(self):
        stats = _make_stats(
            mtd_earnings=49000, pct_goal=98.0, days_worked=29,
            remaining_days=1, total_calendar_days=30,
            daily_avg=1690, daily_target_needed=1000,
            projection_month_end=50000.0, goal=50000.0,
            elapsed_days=29,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "1 restante" in result
        assert "1 restantes" not in result

    def test_single_projection_when_no_variance(self):
        # std=None (few data points): only the base projection is informative,
        # so Conservador/Otimista (which would be identical) must be omitted.
        stats = _make_stats(
            mtd_earnings=15000, pct_goal=33.3, days_worked=10,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=2000,
            projection_month_end=37500.0, goal=45000.0,
            # current_month_daily_std omitted → None
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Base (média atual): R$ 37.500,00" in result
        assert "Conservador" not in result
        assert "Otimista" not in result

    def test_projection_scenarios_on_separate_lines(self):
        # Each scenario must be its own markdown list item on its own line,
        # and the list must be separated from the header by a blank line
        # (otherwise Streamlit renders them jammed into one line).
        stats = _make_stats(
            mtd_earnings=15000, pct_goal=33.3, days_worked=10,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=2000,
            projection_month_end=37500.0, goal=45000.0,
            current_month_daily_std=500.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "**Projeção de fechamento:**\n\n- Conservador:" in result
        assert "\n- Base (média atual):" in result
        assert "\n- Otimista:" in result
        assert "\n\nMais provável: **base**." in result

    def test_no_tone_adjectives_or_suggestions(self):
        """Factual output: no 'você', 'bateu', 'priorize', 'sugestão', 'ritmo adequado'."""
        stats = _make_stats(
            mtd_earnings=22500, pct_goal=50.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_avg=1500, daily_target_needed=1500,
            projection_month_end=45000.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS).lower()
        for banned in ("você", "bateu", "priorize", "sugestão", "ritmo adequado",
                       "atenção ao ritmo", "parabéns", "consolidar"):
            assert banned not in result, f"frase proibida presente: {banned}"

    def test_integration_real_compute_monthly_stats(self, conn):
        """Pipe real compute_monthly_stats output into generate_rule_insights."""
        init_db(conn)
        for d in (5, 8, 12, 15, 18, 22):
            upsert_daily_items(conn, f"2026-06-{d:02d}", {"ressonancia_magnetica": 8})
        current = compute_monthly_stats(
            conn, "2026-06", 45000.0, DEFAULT_ACTIVE_MODS, today=date(2026, 6, 22)
        )
        stats = {
            "current_month_stats": current,
            "wow_change_pct": None, "mom_change_pct": None,
            "modality_mix_current": {}, "modality_mix_historical": {},
            "consecutive_below_target": 0,
            "current_month_daily_std": None, "prev_month_earnings": None,
        }
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        # Must mention the real MTD (8*35*6 = 1680) and days worked (6)
        assert "1.680,00" in result
        assert "6 dias trabalhados" in result