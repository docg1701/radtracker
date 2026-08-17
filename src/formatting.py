"""Formatting utilities and locale constants for radtracker."""

import math
from decimal import ROUND_HALF_UP, Decimal

MONTHS: dict[str, dict[int, str]] = {
    "en": {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December",
    },
    "pt": {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    },
}


def month_abbr(year_month: str, lang: str = "en") -> str:
    """'2026-03' → 'Mar/26' (3-letter month + 2-digit year)."""
    y, m = int(year_month[:4]), int(year_month[5:7])
    return f"{MONTHS[lang].get(m, f'M{m}')[:3]}/{y % 100:02d}"


def month_name(year_month: str, lang: str = "en") -> str:
    """'2026-03' → 'March' (lang='en') or 'Março' (lang='pt')."""
    try:
        return MONTHS[lang][int(year_month[5:7])]
    except (ValueError, IndexError):
        return year_month


def md_escape(text: str) -> str:
    """Escape $ for Streamlit markdown (prevents LaTeX math-mode corruption).

    Use this on any string containing $ that will be rendered via
    st.markdown, st.expander, st.warning, st.info, or st.metric delta.

    Example:
        >>> md_escape(fmt_money(1250.0, "pt"))
        '$\\ 1.250,00'
    """
    return text.replace("$", "\\$")


def _quantize_half_up(value: float) -> Decimal:
    """Quantize to cents with ROUND_HALF_UP (avoids IEEE-754 artefacts)."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt_money(value: float, lang: str = "en") -> str:
    """Format a float as money: '$1,250.00' (en) / '$1.250,00' (pt).

    The $ symbol marks money generically — the amounts are Brazilian reais.

    Examples:
        >>> fmt_money(1250.0, "en")
        '$1,250.00'
        >>> fmt_money(1250.0, "pt")
        '$1.250,00'
        >>> fmt_money(0.0, "en")
        '$0.00'
    """
    if math.isnan(value):
        return "$ —"
    if math.isinf(value):
        return "$ ∞" if value > 0 else "−$ ∞"
    if value < 0:
        return f"\u2212{fmt_money(-value, lang)}"
    d = _quantize_half_up(value)
    if lang == "pt":
        return "$" + f"{d:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"${d:,.2f}"
