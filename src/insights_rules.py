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

    Uses 4 tone levels based on pct_goal:
        ≥75%  → success   (🟢 celebratory)
        50-75% → on-track (🟡 encouraging)
        25-50% → warning  (🟠 concerned, actionable)
        <25%   → danger   (🔴 urgent)

    Also checks WoW trend, modality mix shifts, and consecutive below-target days.
    Addresses the user as "Galvani".

    Args:
        stats: Dict from compute_historical_stats() with keys:
            current_month_stats, wow_change_pct, mom_change_pct,
            modality_mix_current, modality_mix_historical,
            consecutive_below_target.

    Returns:
        Markdown-formatted Portuguese insight string.
    """
    current = stats.get("current_month_stats")
    if current is None:
        return (
            "Ainda não há dados suficientes para gerar insights. "
            "Registre sua produção diária na aba **📊 Hoje** e volte aqui "
            "quando tiver pelo menos alguns dias de trabalho."
        )

    pct = current["pct_goal"]
    mtd = current["mtd_earnings"]
    days_worked = current["days_worked"]
    total_days = current["total_work_days"]

    # ── Tone selection ──
    if pct >= 75:
        tone = "success"
    elif pct >= 50:
        tone = "on_track"
    elif pct >= 25:
        tone = "warning"
    else:
        tone = "danger"

    lines: list[str] = []

    # ── Main tone-based opening ──
    if tone == "success":
        lines.append(
            f"🟢 **Excelente, Galvani!** Você já alcançou **{pct:.0f}%** "
            f"da meta mensal com **{fmt_brl(mtd)}** faturados em "
            f"**{days_worked}** de {total_days} dias úteis. "
            f"O ritmo está forte — continue assim!"
        )
    elif tone == "on_track":
        remaining = max(0.0, current.get("daily_target_needed", 0))
        lines.append(
            f"🟡 **No caminho certo, Galvani.** Você está com **{pct:.0f}%** "
            f"da meta ({fmt_brl(mtd)} em {days_worked} dias). "
            f"Para fechar o mês, precisa de cerca de **{fmt_brl(remaining)}/dia** "
            f"nos próximos {current['remaining_work_days']} dias úteis."
        )
    elif tone == "warning":
        missing = max(0.0, current.get("daily_target_needed", 0))
        lines.append(
            f"🟠 **Atenção, Galvani.** Você está em **{pct:.0f}%** da meta "
            f"({fmt_brl(mtd)} em {days_worked} dias). "
            f"O gap está em **{fmt_brl(missing)}/dia** — "
            f"vale revisar o volume de exames nos próximos "
            f"{current['remaining_work_days']} dias."
        )
    else:
        lines.append(
            f"🔴 **Alerta, Galvani.** Apenas **{pct:.0f}%** da meta foi atingido "
            f"({fmt_brl(mtd)} em {days_worked} dias). "
            f"Considere rever a meta mensal ou buscar fontes adicionais "
            f"de exames para os próximos {current['remaining_work_days']} dias."
        )

    # ── WoW trend ──
    wow = stats.get("wow_change_pct")
    if wow is not None:
        direction = "📈" if wow > 0 else "📉" if wow < 0 else "➡️"
        lines.append(
            f"\n{direction} **Semana a semana:** "
            f"{'crescimento' if wow > 0 else 'queda' if wow < 0 else 'estável'}"
            f" de **{abs(wow):.1f}%** no faturamento."
        )

    # ── MoM trend ──
    mom = stats.get("mom_change_pct")
    if mom is not None:
        direction = "📈" if mom > 0 else "📉" if mom < 0 else "➡️"
        lines.append(
            f"\n{direction} **Mês a mês:** "
            f"{'crescimento' if mom > 0 else 'queda' if mom < 0 else 'estável'}"
            f" de **{abs(mom):.1f}%** em relação ao mês anterior."
        )

    # ── Modality mix shift ──
    mix_current = stats.get("modality_mix_current", {})
    mix_history = stats.get("modality_mix_historical", {})
    if days_worked > 0 and mix_history and len(mix_history) >= 2:
        # Compute historical average (excluding current month if present)
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

            # Detect shifts >10 percentage points
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
                    "\n🔍 **Mudança no mix de modalidades:** "
                    + "; ".join(shifts)
                    + "."
                )

    # ── Consecutive below target ──
    below = stats.get("consecutive_below_target", 0)
    if below >= 3:
        lines.append(
            f"\n⚠️ Você está há **{below} dias consecutivos** "
            f"abaixo da meta diária. Pode ser um bom momento para "
            f"revisar a carga de trabalho ou ajustar a meta."
        )

    # ── Actionable suggestions ──
    if tone in ("warning", "danger"):
        lines.append(
            "\n💡 **Sugestão:** Avalie se há possibilidade de aumentar "
            "o volume de exames de **RM** (maior remuneração) ou revisar "
            "a meta para refletir melhor a demanda atual."
        )

    if tone == "success":
        lines.append(
            "\n💡 **Sugestão:** O momento é de consolidar o bom ritmo. "
            "Considere documentar o que está funcionando bem este mês "
            "para replicar nos próximos."
        )

    return "\n".join(lines)



