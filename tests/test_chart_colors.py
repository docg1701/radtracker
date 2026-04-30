"""Tests for src.chart_colors — hex_to_rgba and palette validation."""

from src.chart_colors import CHART_COLORS, hex_to_rgba


class TestHexToRgba:
    def test_hex_to_rgba_full(self):
        result = hex_to_rgba("#ff0000", 0.5)
        assert result == "rgba(255, 0, 0, 0.5)"

    def test_hex_to_rgba_short(self):
        # "#0D9" → "00DD99" → (0, 221, 153)
        result = hex_to_rgba("#0D9", 1.0)
        assert result == "rgba(0, 221, 153, 1.0)"

    def test_hex_to_rgba_black(self):
        result = hex_to_rgba("#000000", 0.0)
        assert result == "rgba(0, 0, 0, 0.0)"


class TestChartColors:
    def test_chart_colors_has_required_keys(self):
        required = {"rm", "tc", "rx", "primary", "muted", "progress_danger"}
        assert required.issubset(set(CHART_COLORS.keys()))

    def test_chart_colors_all_start_with_hash(self):
        for key, value in CHART_COLORS.items():
            assert isinstance(value, str), f"{key} should be str"
            assert value.startswith("#"), f"{key}={value!r} should start with #"
