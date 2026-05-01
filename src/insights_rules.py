"""
Rule-based insights engine for radtracker — Sprint 4.

Pure function: dict in, Portuguese markdown string out.
Zero database or external dependencies.
"""

from typing import Any

from src.formatting import fmt_brl


def generate_rule_insights(stats: dict[str, Any]) -> str:
    """
    Generate Portuguese-language insights from historical statistics.

    Tone is determined by whether the current pace can realistically
    hit the goal, not just by a fixed pct_goal threshold.

    Also checks WoW/MoM trends, modality mix shifts, and
    consecutive below-target days.

    Args:
        stats: Dict from compute_historical_stats() with keys:
            current_month_stats, wow_change_pct, mom_change_pct,
            modality_mix_current, modality_mix_historical,
            consecutive_below_target.

    Returns:
        Markdown-formatted Portuguese insight string.
    """
    current = stats.get("current_month_stats")
    if current is None or current.get("days_worked", 0) == 0:
        return (
            "Nenhum registro ainda — registre sua produção "
            "na **barra lateral** e volte aqui quando "
            "tiver pelo menos alguns dias de trabalho."
        )

    pct = current["pct_goal"]
    mtd = current["mtd_earnings"]
    days_worked = current["days_worked"]
    remaining = current["remaining_calendar_days"]
    total_days = current["total_calendar_days"]
    daily_avg = current.get("daily_avg", 0.0)
    daily_needed = max(0.0, current.get("daily_target_needed", 0.0))
    projection = current.get("projection_month_end", 0.0)
    goal = (mtd / pct * 100) if pct > 0 else 0.0

    # ── Tone: can the current pace hit the goal? ──
    # When days_worked is small (< 5), daily_needed vs daily_avg
    # ratio is unstable — fall back to linear-expected-progress logic.
    if remaining == 0:
        tone = "success" if pct >= 100 else "danger"
    elif daily_needed <= 0:
        tone = "success"
    elif days_worked >= 5:
        if daily_avg > 0 and daily_needed <= daily_avg * 1.1:
            tone = "on_track"
        elif daily_avg > 0 and daily_needed <= daily_avg * 1.5:
            tone = "warning"
        elif daily_avg > 0:
            tone = "danger"
        else:
            tone = "on_track"  # days_worked >= 5 with no daily_avg is impossible
    else:
        expected_pct = (days_worked / total_days) * 100
        if pct >= expected_pct * 1.1:
            tone = "success"
        elif pct >= expected_pct:
            tone = "on_track"
        elif pct >= expected_pct * 0.5:
            tone = "warning"
        else:
            tone = "danger"

    lines: list[str] = []

    # ── Plural-aware helpers ──
    def _dia(n: int) -> str:
        return "dia" if n == 1 else "dias"

    def _restar(n: int) -> str:
        return "Resta" if n == 1 else "Restam"

    def _restante(n: int) -> str:
        return "restante" if n == 1 else "restantes"

    # ── Opening paragraph ──
    lines.append(
        f"**{pct:.0f}%** da meta ({fmt_brl(mtd)} de {fmt_brl(goal)}) "
        f"em **{days_worked}** {_dia(days_worked)} trabalhados. "
    )

    # ── Remaining-days projection line ──
    if remaining > 0:
        if tone == "success":
            lines.append(
                f"Com apenas **{remaining}** {_dia(remaining)} "
                f"{_restante(remaining)} e faturamento de "
                f"{fmt_brl(mtd)}, faltam "
                f"**{fmt_brl(max(0, goal - mtd))}**. "
                f"Sua projeção é fechar em "
                f"**{fmt_brl(projection)}**."
            )
        elif tone == "on_track":
            lines.append(
                f"{_restar(remaining)} **{remaining}** "
                f"{_dia(remaining)}. Seu ritmo atual de "
                f"**{fmt_brl(daily_avg)}/dia** "
                f"projeta **{fmt_brl(projection)}** — suficiente "
                f"para bater a meta."
            )
        elif tone == "warning":
            gap = daily_needed - daily_avg
            lines.append(
                f"{_restar(remaining)} **{remaining}** "
                f"{_dia(remaining)}. Para bater a meta, você "
                f"precisa de **{fmt_brl(daily_needed)}/dia**, "
                f"mas sua média atual é "
                f"**{fmt_brl(daily_avg)}/dia** "
                f"({fmt_brl(gap)}/dia acima do seu ritmo). "
                f"Projeção atual: **{fmt_brl(projection)}**."
            )
        else:
            missing = goal - projection
            lines.append(
                f"{_restar(remaining)} **{remaining}** "
                f"{_dia(remaining)}. Você precisaria de "
                f"**{fmt_brl(daily_needed)}/dia**, "
                f"mas sua média é **{fmt_brl(daily_avg)}/dia**. "
                f"No ritmo atual, fecharia em "
                f"**{fmt_brl(projection)}** "
                f"— **{fmt_brl(missing)}** abaixo da meta."
            )

    # ── Tone-based assessment ──
    if tone == "success":
        lines.append(
            "\n:material/check_circle: **Você já bateu a meta!** "
            "O ritmo foi excelente este mês."
        )
    elif tone == "on_track":
        lines.append(
            "\n:material/check_circle: **Ritmo adequado.** "
            "Mantendo a média atual, a meta será atingida."
        )

    # ── WoW trend ──
    wow = stats.get("wow_change_pct")
    if wow is not None:
        if wow > 0:
            direction = ":material/trending_up:"
            trend_word = "crescimento"
        elif wow < 0:
            direction = ":material/trending_down:"
            trend_word = "queda"
        else:
            direction = ":material/trending_flat:"
            trend_word = "estável"
        lines.append(
            f"\n{direction} **Semana a semana:** "
            f"{trend_word} de **{abs(wow):.1f}%** no faturamento."
        )

    # ── MoM trend ──
    mom = stats.get("mom_change_pct")
    if mom is not None:
        if mom > 0:
            direction = ":material/trending_up:"
            trend_word = "crescimento"
        elif mom < 0:
            direction = ":material/trending_down:"
            trend_word = "queda"
        else:
            direction = ":material/trending_flat:"
            trend_word = "estável"
        lines.append(
            f"\n{direction} **Mês a mês:** "
            f"{trend_word} de **{abs(mom):.1f}%** "
            f"em relação ao mês anterior."
        )

    # ── Modality mix shift ──
    mix_current = stats.get("modality_mix_current", {})
    mix_history = stats.get("modality_mix_historical", {})
    if days_worked > 0 and mix_history and len(mix_history) >= 2:
        months_sorted = sorted(mix_history.keys())
        current_ym = max(months_sorted)
        past_months = [m for m in months_sorted if m != current_ym]
        if past_months:
            avg_mix: dict[str, float] = {"rm": 0.0, "tc": 0.0, "rx": 0.0}
            for m in past_months:
                for mod in ("rm", "tc", "rx"):
                    avg_mix[mod] += mix_history[m][mod]
            for mod in avg_mix:
                avg_mix[mod] /= len(past_months)

            shifts: list[str] = []
            for mod, label in (("rm", "RM"), ("tc", "TC"), ("rx", "RX")):
                diff = mix_current.get(mod, 0.0) - avg_mix[mod]
                if abs(diff) > 10:
                    dir_word = "aumento" if diff > 0 else "redução"
                    shifts.append(
                        f"{label}: {dir_word} de {abs(diff):.1f} p.p. "
                        f"(média histórica {avg_mix[mod]:.1f}%)"
                    )
            if shifts:
                lines.append(
                    "\n**Mudança no mix de modalidades:** "
                    + "; ".join(shifts) + "."
                )

    # ── Consecutive below target ──
    below = stats.get("consecutive_below_target", 0)
    if below >= 3:
        lines.append(
            f"\n:material/warning: **{below}** {_dia(below)} consecutivos "
            f"abaixo da meta diária. Pode ser um bom momento para "
            f"revisar a carga de trabalho."
        )

    # ── Suggestions (context-aware) ──
    if tone == "success":
        lines.append(
            "\n:material/lightbulb: **Sugestão:** O momento é de "
            "consolidar o bom ritmo. Documente o que funcionou "
            "bem este mês para replicar nos próximos."
        )
    elif tone == "on_track":
        lines.append(
            f"\n:material/lightbulb: **Sugestão:** Continue no ritmo "
            f"atual. Se conseguir alguns dias acima de "
            f"**{fmt_brl(daily_avg)}**, você fecha com folga."
        )
    elif tone in ("warning", "danger"):
        lines.append(
            "\n:material/lightbulb: **Sugestão:** Para melhorar o "
            "faturamento, priorize exames de **RM** "
            "(maior remuneração). Se a demanda não permitir, "
            "considere ajustar a meta na aba "
            "**:material/settings: Configuração** para refletir "
            "a realidade atual."
        )

    return "\n".join(lines)
