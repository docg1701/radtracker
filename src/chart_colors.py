"""
Shared color palette for all Plotly charts.

Every chart module imports from here — no inline hex values anywhere else.
Colors are colorblind-safe and semantically named.
"""


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert a 3- or 6-digit hex color to an rgba string."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


# Modalidade → cor fixa (11 modalidades, paleta fria com boa separação)
MODALITY_COLORS: dict[str, str] = {
    "radiografia": "#2563EB",              # Blue-600
    "tc_geral": "#6366F1",                 # Indigo-500
    "tc_abdome_total": "#0891B2",          # Cyan-600
    "ressonancia_magnetica": "#7C3AED",    # Violet-600
    "angiotomografia": "#0D9488",           # Teal-600
    "ultrassonografia": "#A855F7",          # Purple-500
    "dopplervelocimetria": "#059669",       # Emerald-600
    "radiografia_contrastada": "#475569",   # Slate-600
    "ultrassom_morfologico": "#0EA5E9",     # Sky-500
    "mamografia": "#BE123C",                # Rose-700
    "densitometria": "#A16207",             # Amber-700
}


def color_for_modality(slug: str, modalities: list[dict] | None = None) -> str:
    """Return the color for a modality slug; fallback to Slate-500.

    When modalities (from DB) is provided, uses DB-stored color if available,
    falling back to the hardcoded palette.

    Example:
        >>> color_for_modality("ressonancia_magnetica")
        '#7C3AED'
        >>> color_for_modality("radiografia", [{"slug": "radiografia", "color": "#FF0000"}])
        '#FF0000'
        >>> color_for_modality("desconhecido")
        '#64748B'
    """
    if modalities is not None:
        for m in modalities:
            if m["slug"] == slug:
                return m.get("color", MODALITY_COLORS.get(slug, "#64748B"))
    return MODALITY_COLORS.get(slug, "#64748B")


# Modality color aliases for backward compatibility in tests
CHART_COLORS: dict[str, str] = {
    **MODALITY_COLORS,
    # Legacy aliases (kept for transition)
    "rm": MODALITY_COLORS["ressonancia_magnetica"],
    "tc": MODALITY_COLORS["tc_geral"],
    "rx": MODALITY_COLORS["radiografia"],

    # Chart accent
    "primary": "#0D9488",  # Teal-600 — main line/bar color
    "muted": "#94A3B8",    # Slate-400 — secondary lines, grid
    "neutral": "#64748B",  # Slate-500 — annotations

    # Progress milestone segments (teal monochrome gradient)
    "progress_danger": "#CCFBF1",      # teal-50  — 0-25%
    "progress_warning": "#5EEAD4",    # teal-300 — 25-50%
    "progress_on_track": "#14B8A6",   # teal-500 — 50-75%
    "progress_achieved": "#0F766E",    # teal-700 — 75-100%

    # Chart background / grid
    "track": "#E2E8F0",  # Slate-200 — progress gauge background, gridlines
}


def get_chart_text_color() -> str:
    """Return the chart annotation color for the current Streamlit theme.

    Returns #E5E7EB for dark theme (readable on #101010 background),
    #0F172A for light theme (readable on #FFFFFF background).
    Falls back to light theme when called outside Streamlit runtime
    (e.g., during tests).
    """
    try:
        import streamlit as st  # noqa: PLC0415 — lazy import to avoid test dependency
        return "#E5E7EB" if st.context.theme.base == "dark" else "#0F172A"
    except Exception:
        return "#0F172A"
