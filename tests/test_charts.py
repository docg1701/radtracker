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


# ── v2.1: price-vigency in charts (donut + WoW) ──

class TestChartsVigency:
    """Charts use the price-vigent 'revenue' column, never the current
    modalities.price — a price change does not rewrite past charts."""

    _MODS = [
        {"slug": "tc_geral", "label": "TC Geral", "price": 25.0,
         "exams_per_hour": 7.5, "active": 1, "sort_order": 1, "color": "#6366F1"},
    ]

    def _items_df(self):
        import pandas as pd
        # 10 tc_geral at the vigent price of 25 -> revenue 250 (fixed)
        return pd.DataFrame([
            {"date": "2026-03-01", "modality_slug": "tc_geral",
             "count": 10, "revenue": 250.0},
        ])

    def test_donut_uses_vigent_revenue_not_current_price(self):
        from src.charts import build_monthly_modality_donut
        df = self._items_df()
        fig25 = build_monthly_modality_donut(df, self._MODS)
        # Raise the current price to 40 — the donut slice must stay 250, not 400.
        mods_40 = [dict(self._MODS[0], price=40.0)]
        fig40 = build_monthly_modality_donut(df, mods_40)
        val25 = float(fig25.data[0].values[0])
        val40 = float(fig40.data[0].values[0])
        assert val25 == 250.0
        assert val40 == 250.0  # unchanged: uses revenue, not current price

    def test_donut_without_revenue_column_renders_zero(self):
        import pandas as pd

        from src.charts import build_monthly_modality_donut
        # df without a revenue column -> no vigent revenue available -> zeros,
        # never a silent fallback to current price.
        df = pd.DataFrame([
            {"date": "2026-03-01", "modality_slug": "tc_geral", "count": 10},
        ])
        fig = build_monthly_modality_donut(df, self._MODS)
        # placeholder zero slice (values == [0])
        assert list(fig.data[0].values) == [0]

    def test_wow_uses_vigent_revenue_not_current_price(self):
        import pandas as pd

        from src.charts_analysis import build_wow_comparison_chart
        # Two weeks of tc_geral at vigent price 25 -> revenue 250 each day
        rows = []
        for d in range(10, 18):  # prev week + current week (forced today=2026-03-17)
            rows.append({"date": f"2026-03-{d:02d}", "modality_slug": "tc_geral",
                          "count": 10, "revenue": 250.0})
        items_df = pd.DataFrame(rows)
        fig25 = build_wow_comparison_chart(items_df, self._MODS)
        mods_40 = [dict(self._MODS[0], price=40.0)]
        fig40 = build_wow_comparison_chart(items_df, mods_40)
        # Both weeks' bar values come from revenue (250/day), independent of price.
        sum25 = sum(sum(t.y) for t in fig25.data)
        sum40 = sum(sum(t.y) for t in fig40.data)
        assert sum25 == sum40  # price change does not move the WoW bars
