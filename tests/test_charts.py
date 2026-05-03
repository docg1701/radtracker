"""Tests for src.charts — build_modality_bar with/without custom colors."""

from src.chart_colors import MODALITY_COLORS
from src.charts import build_modality_bar


class TestBuildModalityBar:
    def test_build_modality_bar_with_custom_colors(self):
        """Build bar chart with modalities list containing custom colors."""
        mods = [
            {"slug": "tc_geral", "color": "#FF0000"},
            {"slug": "radiografia", "color": "#00FF00", "label": "Radiografia"},
        ]
        labels = {"tc_geral": "TC Geral", "radiografia": "Radiografia"}
        counts = {"tc_geral": 5, "radiografia": 20}

        fig = build_modality_bar(counts, labels, modalities=mods)

        # Extract bar colors from the trace
        bar_trace = fig.data[0]
        bar_colors = bar_trace.marker.color
        assert list(bar_colors) == ["#FF0000", "#00FF00"]  # Custom colors, ascending order

    def test_build_modality_bar_without_modalities(self):
        """Build bar chart without modalities param, uses hardcoded colors."""
        labels = {"tc_geral": "TC Geral", "radiografia": "Radiografia"}
        counts = {"tc_geral": 5, "radiografia": 20}

        fig = build_modality_bar(counts, labels)

        bar_trace = fig.data[0]
        bar_colors = bar_trace.marker.color
        # Should use hardcoded palette colors (ascending by total: tc_geral=5 first)
        assert list(bar_colors) == [
            MODALITY_COLORS["tc_geral"],
            MODALITY_COLORS["radiografia"],
        ]

    def test_build_modality_bar_empty_counts(self):
        """Empty counts produce muted fallback bar."""
        fig = build_modality_bar({}, {})
        bar_trace = fig.data[0]
        assert bar_trace.y[0] == "\u2014"  # em dash
        assert bar_trace.x[0] == 0
