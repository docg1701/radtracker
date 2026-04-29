"""
Shared color palette for all Plotly charts.

Every chart module imports from here — no inline hex values anywhere else.
Colors are colorblind-safe and semantically named.
"""

CHART_COLORS = {
    # Modality colors — used in bar, pie, stacked charts
    "rm": "#2563EB",      # Blue-600
    "tc": "#D97706",      # Amber-600
    "rx": "#0891B2",      # Cyan-600

    # Semantic — used in progress gauge, delta indicators
    "success": "#16A34A",  # Green-600
    "warning": "#CA8A04",  # Yellow-600
    "danger": "#DC2626",   # Red-600

    # Chart accent
    "primary": "#0D9488",  # Teal-600 — main line/bar color
    "muted": "#94A3B8",    # Slate-400 — secondary lines, grid
    "neutral": "#64748B",  # Slate-500 — annotations

    # Progress milestone segments
    "progress_danger": "#DC2626",   # 0-25%
    "progress_warning": "#CA8A04",  # 25-50%
    "progress_on_track": "#0D9488", # 50-75%
    "progress_achieved": "#16A34A", # 75-100%

    # Chart background / grid
    "track": "#E2E8F0",  # Slate-200 — progress gauge background, gridlines
}
