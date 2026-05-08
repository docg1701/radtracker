"""Tests for src.formatting — Brazilian Real currency formatting, month constants."""

from src.formatting import MONTHS_PT, fmt_brl


class TestFmtBrl:
    def test_fmt_brl_integer(self):
        assert fmt_brl(1000.0) == "R$ 1.000,00"

    def test_fmt_brl_with_cents(self):
        assert fmt_brl(1250.50) == "R$ 1.250,50"

    def test_fmt_brl_zero(self):
        assert fmt_brl(0.0) == "R$ 0,00"

    def test_fmt_brl_negative(self):
        assert fmt_brl(-500.0) == "−R$ 500,00"

    def test_fmt_brl_large_number(self):
        assert fmt_brl(1234567.89) == "R$ 1.234.567,89"

    def test_fmt_brl_half_centavo_round_up(self):
        # 0.005 → cents = int(0.5 + 0.5) = 1 → "R$ 0,01"
        assert fmt_brl(0.005) == "R$ 0,01"

    def test_fmt_brl_nan(self):
        assert fmt_brl(float("nan")) == "R$ —"

    def test_fmt_brl_infinity(self):
        assert fmt_brl(float("inf")) == "R$ ∞"
        assert fmt_brl(float("-inf")) == "−R$ ∞"

    def test_fmt_brl_floating_point_trap_one_point_zero_zero_five(self):
        # 1.005 in IEEE-754 is slightly below 1.005, so naive
        # int(value*100 + 0.5) incorrectly yields R$ 1,00.
        assert fmt_brl(1.005) == "R$ 1,01"


class TestMonthsPt:
    def test_months_pt_all_12(self):
        assert len(MONTHS_PT) == 12

    def test_months_pt_january(self):
        assert MONTHS_PT[1] == "Janeiro"
