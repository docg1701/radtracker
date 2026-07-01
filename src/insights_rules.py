"""
Rule-based insights engine for radtracker — v2 dynamic modalities.

Factual, dense output: percentages, absolute BRL, projection scenarios, and
real comparisons (MoM, modality mix). No tone adjectives, no "you did it"
phrases, no generic suggestions — only the numbers that matter.

Pure function: stats dict + active_modalities -> Portuguese markdown string.
Zero database or external dependencies.
"""

from typing import Any

from src.formatting import fmt_brl


def _gap_label(value: float, goal: float) -> str:
    """Return 'R$ X acima' or 'R$ X abaixo' relative to the goal."""
    diff = value - goal
    word = "acima" if diff >= 0 else "abaixo"
    return f"{fmt_brl(abs(diff))} {word}"


def _projection_scenarios(
    mtd: float, daily_avg: float, remaining: int,
    std: float | None, base: float,
) -> tuple[float, float, float]:
    """Return (conservative, base, optimistic) month-end projections."""
    if std is not None and std > 0 and remaining > 0:
        conserv = mtd + max(0.0, daily_avg - std) * remaining
        optim = mtd + (daily_avg + std) * remaining
    else:
        conserv = base
        optim = base
    return conserv, base, optim


def generate_rule_insights(
    stats: dict[str, Any],
    active_modalities: list[dict[str, Any]],
) -> str:
    """Generate factual Portuguese insights from historical statistics.

    Args:
        stats: Dict from compute_historical_stats() with keys:
            current_month_stats, current_month_daily_std, prev_month_earnings,
            mom_change_pct, modality_mix_current, consecutive_below_target.
        active_modalities: List of active modality dicts (slug, label, price).

    Returns:
        Markdown-formatted Portuguese insight string: % of goal, worked/elapsed/
        remaining days, daily average, 3 projection scenarios, required per-day,
        MoM, top-3 modality mix, and consecutive-below-target streak.
    """
    current = stats.get("current_month_stats")
    if current is None or current.get("days_worked", 0) == 0:
        return (
            "Nenhum registro ainda — registre sua produção "
            "na **barra lateral** e volte aqui quando "
            "tiver pelo menos alguns dias de trabalho."
        )

    mtd = current["mtd_earnings"]
    pct = current["pct_goal"]
    days_worked = current["days_worked"]
    elapsed = current.get("elapsed_days", 0)
    remaining = current["remaining_days"]
    daily_avg = current.get("daily_avg", 0.0)
    daily_needed = max(0.0, current.get("daily_target_needed", 0.0))
    base = current.get("projection_month_end", 0.0)
    goal = current.get("goal") or ((mtd / pct * 100) if pct > 0 else 0.0)
    std = stats.get("current_month_daily_std")
    prev_earnings = stats.get("prev_month_earnings")
    mom = stats.get("mom_change_pct")
    mix = stats.get("modality_mix_current", {})
    below = stats.get("consecutive_below_target", 0)

    lines: list[str] = []

    # ── Cabeçalho factual ──
    lines.append(f"**{pct:.0f}%** da meta — {fmt_brl(mtd)} de {fmt_brl(goal)}.")
    lines.append(
        f"{days_worked} dias trabalhados · {elapsed} decorridos · "
        f"{remaining} restantes · média {fmt_brl(daily_avg)}/dia corrido."
    )

    # ── Projeção de fechamento em 3 cenários ──
    conserv, base_proj, optim = _projection_scenarios(
        mtd, daily_avg, remaining, std, base,
    )
    if remaining > 0:
        lines.append("")
        lines.append("**Projeção de fechamento:**")
        lines.append(f"• Conservador: {fmt_brl(conserv)} — {_gap_label(conserv, goal)}.")
        lines.append(
            f"• Base (média atual): {fmt_brl(base_proj)} — {_gap_label(base_proj, goal)}."
        )
        lines.append(f"• Otimista: {fmt_brl(optim)} — {_gap_label(optim, goal)}.")
        lines.append("Mais provável: **base**.")
        missing = max(0.0, goal - mtd)
        if missing > 0:
            lines.append(
                f"Faltam {fmt_brl(missing)}: {fmt_brl(daily_needed)}/dia "
                f"nos {remaining} restantes."
            )
    else:
        lines.append(
            f"Projeção de fechamento: {fmt_brl(mtd)} ({_gap_label(mtd, goal)} da meta)."
        )

    # ── MoM ──
    if mom is not None:
        sign = "+" if mom >= 0 else ""
        mom_str = f"{mom:.1f}".replace(".", ",")
        prev_str = fmt_brl(prev_earnings) if prev_earnings is not None else "—"
        lines.append(f"MoM: {sign}{mom_str}% ({fmt_brl(mtd)} vs {prev_str}).")

    # ── Mix de modalidades (top 3 por share) ──
    slug_to_label = {m["slug"]: m["label"] for m in active_modalities}
    if mix:
        top = sorted(mix.items(), key=lambda kv: kv[1], reverse=True)[:3]
        parts = [f"{slug_to_label.get(s, s)} {p:.0f}%" for s, p in top if p > 0]
        if parts:
            lines.append("Mix: " + " · ".join(parts) + ".")

    # ── Dias consecutivos abaixo da meta diária ──
    if below >= 3:
        lines.append(f"{below} dias consecutivos abaixo da meta diária.")

    return "\n".join(lines)