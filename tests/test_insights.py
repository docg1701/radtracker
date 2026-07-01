"""Tests for src.insights_rules — natural-language month analysis (v2.2)."""

from datetime import date

from src.calculations import compute_monthly_stats
from src.db import init_db, upsert_daily_items
from src.insights_rules import _prev_month_label, generate_rule_insights


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
    elapsed_days=None,
    mom_change_pct=None,
    prev_month_earnings=None,
    year_month="2026-07",
):
    """Factory for stats dict matching compute_historical_stats output."""
    return {
        "year_month": year_month,
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
        "mom_change_pct": mom_change_pct,
        "prev_month_earnings": prev_month_earnings,
        "modality_mix_current": {},
        "modality_mix_historical": {},
        "consecutive_below_target": 0,
        "current_month_daily_std": None,
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
        assert "Nenhum registro ainda" in result
        assert "barra lateral" in result

    def test_current_total_and_gap(self):
        stats = _make_stats(
            mtd_earnings=1500, pct_goal=3.0, days_worked=1,
            remaining_days=30, total_calendar_days=31,
            daily_target_needed=1618.63, projection_month_end=44671.0,
            goal=50000.0, elapsed_days=1, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Hoje o faturamento está em" in result
        assert "R$ 1.500,00" in result
        assert "3% da meta de R$ 50.000,00" in result
        assert "Faltam R$ 48.500,00" in result

    def test_mom_same_point_comparison(self):
        stats = _make_stats(
            mtd_earnings=32000, pct_goal=64.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_target_needed=1200, projection_month_end=45000.0,
            goal=50000.0, elapsed_days=15, year_month="2026-07",
            mom_change_pct=8.0, prev_month_earnings=29600.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "8,0% acima do mesmo ponto de junho (R$ 29.600,00)" in result

    def test_mom_below(self):
        stats = _make_stats(
            mtd_earnings=20000, pct_goal=40.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_target_needed=1666.67, projection_month_end=30000.0,
            goal=50000.0, elapsed_days=15, year_month="2026-07",
            mom_change_pct=-12.0, prev_month_earnings=22727.0,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "12,0% abaixo do mesmo ponto de junho" in result

    def test_no_mom_when_no_prev_data(self):
        stats = _make_stats(
            mtd_earnings=1500, pct_goal=3.0, days_worked=1,
            remaining_days=30, total_calendar_days=31,
            daily_target_needed=1618.63, projection_month_end=44671.0,
            goal=50000.0, elapsed_days=1, year_month="2026-07",
            mom_change_pct=None, prev_month_earnings=None,
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "mesmo ponto" not in result

    def test_projection_and_path(self):
        stats = _make_stats(
            mtd_earnings=32000, pct_goal=64.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_target_needed=1200, projection_month_end=45000.0,
            goal=50000.0, elapsed_days=15, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "No ritmo atual, o mês fecha em ~R$ 45.000,00" in result
        assert "R$ 5.000,00 abaixo da meta." in result
        assert "Para bater a meta, faltam R$ 18.000,00 em 15 dias restantes" in result
        assert "R$ 1.200,00/dia daqui ao fim." in result

    def test_preliminary_note_when_few_days(self):
        stats = _make_stats(
            mtd_earnings=1500, pct_goal=3.0, days_worked=1,
            remaining_days=30, total_calendar_days=31,
            daily_target_needed=1618.63, projection_month_end=44671.0,
            goal=50000.0, elapsed_days=2, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "projeção preliminar, poucos dias" in result

    def test_no_preliminary_note_when_enough_days(self):
        stats = _make_stats(
            mtd_earnings=32000, pct_goal=64.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_target_needed=1200, projection_month_end=45000.0,
            goal=50000.0, elapsed_days=15, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "preliminar" not in result

    def test_goal_met_mid_month(self):
        stats = _make_stats(
            mtd_earnings=52000, pct_goal=104.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_target_needed=0.0, projection_month_end=104000.0,
            goal=50000.0, elapsed_days=15, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "Meta batida" in result
        assert "15 dias restantes pela frente" in result
        # already reached → no "faltam .../dia" path shown
        assert "Para bater a meta" not in result

    def test_month_closed_below(self):
        stats = _make_stats(
            mtd_earnings=47000, pct_goal=94.0, days_worked=30,
            remaining_days=0, total_calendar_days=30,
            daily_target_needed=0.0, projection_month_end=47000.0,
            goal=50000.0, elapsed_days=30, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "O mês fechou em R$ 47.000,00" in result
        assert "abaixo" in result
        assert "No ritmo atual" not in result

    def test_singular_plural_remaining(self):
        stats = _make_stats(
            mtd_earnings=49000, pct_goal=98.0, days_worked=29,
            remaining_days=1, total_calendar_days=30,
            daily_target_needed=1000, projection_month_end=50000.0,
            goal=50000.0, elapsed_days=29, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        assert "em 1 dia restante:" in result
        assert "1 dias restantes" not in result

    def test_no_tone_adjectives_or_suggestions(self):
        stats = _make_stats(
            mtd_earnings=32000, pct_goal=64.0, days_worked=15,
            remaining_days=15, total_calendar_days=30,
            daily_target_needed=1200, projection_month_end=45000.0,
            goal=50000.0, elapsed_days=15, year_month="2026-07",
        )
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS).lower()
        for banned in ("você", "bateu", "priorize", "sugestão", "ritmo adequado",
                       "atenção ao ritmo", "parabéns", "consolidar", "conservador",
                       "otimista"):
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
            "year_month": "2026-06",
            "current_month_stats": current,
            "mom_change_pct": None, "prev_month_earnings": None,
            "modality_mix_current": {}, "modality_mix_historical": {},
            "consecutive_below_target": 0, "current_month_daily_std": None,
        }
        result = generate_rule_insights(stats, DEFAULT_ACTIVE_MODS)
        # Real MTD = 8*35*6 = 1680 must appear in the narrative.
        assert "1.680,00" in result
        assert "meta" in result.lower()


class TestPrevMonthLabel:
    def test_july_to_june(self):
        assert _prev_month_label("2026-07") == "junho"

    def test_january_to_december(self):
        assert _prev_month_label("2026-01") == "dezembro"