"""Formatting utilities and locale constants for radtracker."""

import math
from decimal import ROUND_HALF_UP, Decimal

MONTHS_PT: dict[int, str] = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def md_escape(text: str) -> str:
    """Escape $ for Streamlit markdown (prevents LaTeX math-mode corruption).

    Use this on any string containing R$ that will be rendered via
    st.markdown, st.expander, st.warning, st.info, or st.metric delta.

    Example:
        >>> md_escape(fmt_brl(1250.0))
        'R\\$ 1.250,00'
    """
    return text.replace("$", "\\$")


def fmt_brl(value: float) -> str:
    """
    Format a float as Brazilian Real currency.

    Uses Decimal quantize with ROUND_HALF_UP to avoid IEEE-754
    floating-point artefacts (e.g. 1.005 * 100 != 100.5).

    Example:
        >>> fmt_brl(1250.0)
        'R$ 1.250,00'
        >>> fmt_brl(0.0)
        'R$ 0,00'
    """
    if math.isnan(value):
        return "R$ —"
    if math.isinf(value):
        return "R$ ∞" if value > 0 else "−R$ ∞"
    if value < 0:
        return f"\u2212{fmt_brl(-value)}"
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    integer_part = int(d)
    decimal_part = int((d - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", ".")
    return f"R$ {int_str},{decimal_part:02d}"
