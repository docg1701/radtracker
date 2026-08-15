"""
Rule-based insights engine for radtracker — natural-language analysis.

Produces a short human narrative of where the month stands against the goal:
current total vs. target, comparison with the same point of the previous month,
an end-of-month projection at the current pace, and the daily rate needed from
here to hit the goal. No telegraphic number dumps and no statistics that don't
make sense early in the month.

Pure function: stats dict + active_modalities -> Portuguese markdown string.
Zero database or external dependencies.
"""

from typing import Any

from src.formatting import MONTHS_PT, fmt_brl


def _gap_label(value: float, goal: float) -> str:
    """Return 'R$ X acima' or 'R$ X abaixo' relative to the goal."""
    diff = value - goal
    word = "acima" if diff >= 0 else "abaixo"
    return f"{fmt_brl(abs(diff))} {word}"


def _plural(value: int, singular: str, plural: str) -> str:
    """Return '{value} {singular}' for 1, '{value} {plural}' otherwise."""
    return f"{value} {singular}" if value == 1 else f"{value} {plural}"


def _prev_month_label(year_month: str) -> str:
    """Return the lowercase Portuguese name of the month before year_month."""
    _y, m = (int(x) for x in year_month.split("-"))
    prev = m - 1 if m > 1 else 12
    return MONTHS_PT[prev].lower()


def generate_rule_insights(stats: dict[str, Any]) -> str:
    """Generate a short human narrative of the month vs the goal.

    Covers: current total and % of goal; comparison with the same point of the
    previous month (not a partial-vs-full apples-to-oranges); end-of-month
    projection at the current pace; and the daily rate needed from here to hit
    the goal. Projections are flagged as preliminary while the month has very
    few days; the previous-month comparison is shown only when it exists.
    """
    current = stats.get("current_month_stats")
    if current is None or current.get("days_worked", 0) == 0:
        return (
            "Nenhum registro ainda. Registre sua produção na **barra lateral** "
            "e volte quando tiver alguns dias de trabalho."
        )

    mtd = current["mtd_earnings"]
    pct = current["pct_goal"]
    remaining = current["remaining_days"]
    daily_needed = max(0.0, current.get("daily_target_needed", 0.0))
    proj = current.get("projection_month_end", 0.0)
    goal = current["goal"]
    elapsed = current.get("elapsed_days", 0)
    prev_same = stats.get("prev_month_earnings")
    mom = stats.get("mom_change_pct")
    year_month = stats.get("year_month") or ""

    parts: list[str] = []

    # ── Atual: quanto faturou vs meta ──
    if remaining == 0:
        if pct >= 100.0:
            parts.append(f"**Meta batida** — {fmt_brl(mtd)} de {fmt_brl(goal)} ({pct:.0f}%).")
        else:
            parts.append(
                f"O mês fechou em {fmt_brl(mtd)} — {pct:.0f}% da meta de "
                f"{fmt_brl(goal)} ({_gap_label(mtd, goal)})."
            )
    elif pct >= 100.0:
        parts.append(
            f"**Meta batida** — {fmt_brl(mtd)} de {fmt_brl(goal)} ({pct:.0f}%), "
            f"com {_plural(remaining, 'dia restante', 'dias restantes')} pela frente."
        )
    else:
        parts.append(
            f"Hoje o faturamento está em **{fmt_brl(mtd)}** — {pct:.0f}% da meta "
            f"de {fmt_brl(goal)}. Faltam {fmt_brl(goal - mtd)}."
        )

    # ── Comparação com o mesmo ponto do mês anterior ──
    if mom is not None and prev_same is not None and prev_same > 0 and year_month:
        word = "acima" if mom >= 0 else "abaixo"
        mom_str = f"{abs(mom):.1f}".replace(".", ",")
        parts.append(
            f"Isso é {mom_str}% {word} do mesmo ponto de "
            f"{_prev_month_label(year_month)} ({fmt_brl(prev_same)})."
        )

    # ── Projeção de fechamento + caminho até a meta ──
    if remaining > 0 and pct < 100.0:
        note = " (projeção preliminar, poucos dias)" if elapsed < 7 else ""
        parts.append(
            f"No ritmo atual, o mês fecha em ~{fmt_brl(proj)}{note} — "
            f"{_gap_label(proj, goal)} da meta."
        )
        missing = max(0.0, goal - mtd)
        if missing > 0:
            parts.append(
                f"Para bater a meta, faltam {fmt_brl(missing)} em "
                f"{_plural(remaining, 'dia restante', 'dias restantes')}: "
                f"{fmt_brl(daily_needed)}/dia daqui ao fim."
            )

    return "\n\n".join(parts)