"""
Rule-based insights engine for radtracker — natural-language analysis.

Produces a short human narrative of where the month stands against the goal:
current total vs. target, comparison with the same point of the previous month,
an end-of-month projection at the current pace, and the daily rate needed from
here to hit the goal. No telegraphic number dumps and no statistics that don't
make sense early in the month.

Pure function: stats dict + active_modalities -> markdown string in the
requested language (default EN). Zero database or external dependencies.
"""

from typing import Any

from src.formatting import fmt_money, month_name
from src.i18n import translate


def _gap_label(value: float, goal: float, lang: str) -> str:
    """Return '$ X above' or '$ X below' relative to the goal."""
    diff = value - goal
    word_key = "web.insights.above" if diff >= 0 else "web.insights.below"
    return f"{fmt_money(abs(diff), lang)} {translate(word_key, lang)}"


def _plural(value: int, one_key: str, many_key: str, lang: str) -> str:
    """Return the singular key for 1, the many-key with {count} otherwise."""
    if value == 1:
        return translate(one_key, lang)
    return translate(many_key, lang, count=value)


def _prev_month_label(year_month: str, lang: str) -> str:
    """Return the lowercase month name (per lang) of the month before year_month."""
    _y, m = (int(x) for x in year_month.split("-"))
    prev = m - 1 if m > 1 else 12
    return month_name(f"{_y}-{prev:02d}", lang).lower()


def generate_rule_insights(stats: dict[str, Any], lang: str = "en") -> str:
    """Generate a short human narrative of the month vs the goal.

    Covers: current total and % of goal; comparison with the same point of the
    previous month (not a partial-vs-full apples-to-oranges); end-of-month
    projection at the current pace; and the daily rate needed from here to hit
    the goal. Projections are flagged as preliminary while the month has very
    few days; the previous-month comparison is shown only when it exists.
    """
    current = stats.get("current_month_stats")
    if current is None or current.get("days_worked", 0) == 0:
        return translate("web.insights.no_data", lang)

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

    # ── Current: revenue vs goal ──
    if remaining == 0:
        if pct >= 100.0:
            parts.append(translate(
                "web.insights.status_beat_closed", lang,
                mtd=fmt_money(mtd, lang), goal=fmt_money(goal, lang),
                pct=f"{pct:.0f}",
            ))
        else:
            parts.append(translate(
                "web.insights.status_closed_under", lang,
                mtd=fmt_money(mtd, lang), goal=fmt_money(goal, lang),
                pct=f"{pct:.0f}", gap=_gap_label(mtd, goal, lang),
            ))
    elif pct >= 100.0:
        parts.append(translate(
            "web.insights.status_beat_remaining", lang,
            mtd=fmt_money(mtd, lang), goal=fmt_money(goal, lang),
            pct=f"{pct:.0f}",
            days=_plural(
                remaining,
                "web.insights.day_one_remaining",
                "web.insights.day_many_remaining",
                lang,
            ),
        ))
    else:
        parts.append(translate(
            "web.insights.status_current", lang,
            mtd=fmt_money(mtd, lang), goal=fmt_money(goal, lang),
            pct=f"{pct:.0f}", missing=fmt_money(goal - mtd, lang),
        ))

    # ── Same point of previous month ──
    if mom is not None and prev_same is not None and prev_same > 0 and year_month:
        word = translate(
            "web.insights.above" if mom >= 0 else "web.insights.below", lang
        )
        mom_str = f"{abs(mom):.1f}"
        if lang == "pt":
            mom_str = mom_str.replace(".", ",")
        parts.append(translate(
            "web.insights.mom_compare", lang,
            pct=mom_str, word=word,
            month=_prev_month_label(year_month, lang),
            value=fmt_money(prev_same, lang),
        ))

    # ── End-of-month projection + path to goal ──
    if remaining > 0 and pct < 100.0:
        note = translate("web.insights.projection_note", lang) if elapsed < 7 else ""
        parts.append(translate(
            "web.insights.projection", lang,
            proj=fmt_money(proj, lang), note=note,
            gap=_gap_label(proj, goal, lang),
        ))
        missing = max(0.0, goal - mtd)
        if missing > 0:
            parts.append(translate(
                "web.insights.needed", lang,
                missing=fmt_money(missing, lang),
                days=_plural(
                    remaining,
                    "web.insights.day_one_remaining",
                    "web.insights.day_many_remaining",
                    lang,
                ),
                needed=fmt_money(daily_needed, lang),
            ))

    return "\n\n".join(parts)
