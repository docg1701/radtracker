"""Tests for src.chart_colors — v2 hex_to_rgba, palette, and modality colors."""

from src.chart_colors import (
    CHART_COLORS,
    MODALITY_COLORS,
    color_for_modality,
    hex_to_rgba,
)


class TestHexToRgba:
    def test_hex_to_rgba_full(self):
        result = hex_to_rgba("#ff0000", 0.5)
        assert result == "rgba(255, 0, 0, 0.5)"

    def test_hex_to_rgba_short(self):
        result = hex_to_rgba("#0D9", 1.0)
        assert result == "rgba(0, 221, 153, 1.0)"

    def test_hex_to_rgba_black(self):
        result = hex_to_rgba("#000000", 0.0)
        assert result == "rgba(0, 0, 0, 0.0)"


class TestChartColors:
    def test_chart_colors_has_required_keys(self):
        required = {"primary", "muted", "neutral", "track", "progress_danger"}
        assert required.issubset(set(CHART_COLORS.keys()))

    def test_chart_colors_has_legacy_aliases(self):
        assert "rm" in CHART_COLORS
        assert "tc" in CHART_COLORS
        assert "rx" in CHART_COLORS

    def test_all_start_with_hash(self):
        for key, value in CHART_COLORS.items():
            assert isinstance(value, str), f"{key} should be str"
            assert value.startswith("#"), f"{key}={value!r} should start with #"


class TestModalityColors:
    def test_has_all_11_modalities(self):
        expected = {
            "tc_abdome_total", "tc_geral", "angiotomografia",
            "ressonancia_magnetica", "ultrassonografia", "dopplervelocimetria",
            "mamografia", "radiografia", "radiografia_contrastada",
            "ultrassom_morfologico", "densitometria",
        }
        assert set(MODALITY_COLORS.keys()) == expected

    def test_all_colors_unique(self):
        """All 11 modality colors should be distinct."""
        values = list(MODALITY_COLORS.values())
        assert len(values) == len(set(values))

    def test_all_colors_valid_hex(self):
        for slug, color in MODALITY_COLORS.items():
            assert color.startswith("#"), f"{slug}={color!r}"
            assert len(color) == 7  # #RRGGBB

    def test_color_for_modality_known(self):
        assert color_for_modality("ressonancia_magnetica") == (
            MODALITY_COLORS["ressonancia_magnetica"]
        )
        assert color_for_modality("tc_geral") == MODALITY_COLORS["tc_geral"]

    def test_color_for_modality_unknown_fallback(self):
        assert color_for_modality("desconhecido") == "#64748B"

    def test_color_for_modality_with_lookup(self):
        """Lookup param overrides hardcoded color."""
        mods = [{"slug": "radiografia", "color": "#FF0000"}]
        assert color_for_modality("radiografia", mods) == "#FF0000"

    def test_color_for_modality_with_lookup_fallback(self):
        """Unknown slug in lookup falls back to #64748B."""
        mods = [{"slug": "radiografia", "color": "#FF0000"}]
        assert color_for_modality("desconhecido", mods) == "#64748B"

    def test_color_for_modality_lookup_missing_color_key(self):
        """Lookup entry without 'color' key falls back to hardcoded palette."""
        mods = [{"slug": "tc_geral"}]
        assert color_for_modality("tc_geral", mods) == MODALITY_COLORS["tc_geral"]
