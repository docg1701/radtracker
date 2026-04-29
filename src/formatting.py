"""Formatting utilities and locale constants for radtracker."""

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


def fmt_brl(value: float) -> str:
    """
    Format a float as Brazilian Real currency.

    Example:
        >>> fmt_brl(1250.0)
        'R$ 1.250,00'
        >>> fmt_brl(0.0)
        'R$ 0,00'
    """
    if value < 0:
        return f"\u2212{fmt_brl(-value)}"
    # int(value*100 + 0.5) gives correct half-up rounding.
    # Built-in round() uses banker's rounding (round(0.5)==0), which
    # would under-round half-centavos when non-standard prices are in use.
    cents = int(value * 100 + 0.5)
    integer_part = cents // 100
    decimal_part = cents % 100
    int_str = f"{integer_part:,}".replace(",", ".")
    return f"R$ {int_str},{decimal_part:02d}"
