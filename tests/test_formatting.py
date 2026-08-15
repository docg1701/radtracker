"""Tests for formatting utilities: fmt_money, month names, md_escape."""

from src.formatting import MONTHS, fmt_money, md_escape, month_abbr, month_name


class TestFmtMoneyEn:
    def test_fmt_money_integer(self):
        assert fmt_money(1000.0, "en") == "$1,000.00"

    def test_fmt_money_with_cents(self):
        assert fmt_money(1250.50, "en") == "$1,250.50"

    def test_fmt_money_zero(self):
        assert fmt_money(0.0, "en") == "$0.00"

    def test_fmt_money_negative(self):
        assert fmt_money(-500.0, "en") == "−$500.00"

    def test_fmt_money_large_number(self):
        assert fmt_money(1234567.89, "en") == "$1,234,567.89"

    def test_fmt_money_half_centavo_round_up(self):
        assert fmt_money(0.005, "en") == "$0.01"

    def test_fmt_money_nan(self):
        assert fmt_money(float("nan"), "en") == "$ —"

    def test_fmt_money_infinity(self):
        assert fmt_money(float("inf"), "en") == "$ ∞"
        assert fmt_money(float("-inf"), "en") == "−$ ∞"

    def test_fmt_money_floating_point_trap_one_point_zero_zero_five(self):
        assert fmt_money(1.005, "en") == "$1.01"


class TestFmtMoneyPt:
    def test_fmt_money_pt_uses_brazilian_separators(self):
        assert fmt_money(1250.0, "pt") == "$1.250,00"
        assert fmt_money(1234567.89, "pt") == "$1.234.567,89"

    def test_fmt_money_pt_zero(self):
        assert fmt_money(0.0, "pt") == "$0,00"

    def test_fmt_money_pt_negative(self):
        assert fmt_money(-500.0, "pt") == "−$500,00"

    def test_fmt_money_pt_round_up(self):
        assert fmt_money(1.005, "pt") == "$1,01"


class TestMonths:
    def test_months_have_both_languages_with_twelve_entries(self):
        assert set(MONTHS) == {"en", "pt"}
        assert len(MONTHS["en"]) == 12
        assert len(MONTHS["pt"]) == 12

    def test_month_name_en(self):
        assert month_name("2026-03", "en") == "March"
        assert month_name("2026-01", "en") == "January"

    def test_month_name_pt(self):
        assert month_name("2026-03", "pt") == "Março"
        assert month_name("2026-01", "pt") == "Janeiro"

    def test_month_name_malformed_returns_input(self):
        assert month_name("not-a-date", "en") == "not-a-date"

    def test_month_abbr_en(self):
        assert month_abbr("2026-03", "en") == "Mar/26"

    def test_month_abbr_pt(self):
        assert month_abbr("2026-03", "pt") == "Mar/26"


class TestMdEscape:
    def test_md_escape_escapes_dollar(self):
        assert md_escape("$1,250.00") == "\\$1,250.00"
        assert md_escape("$ 100") == "\\$ 100"
