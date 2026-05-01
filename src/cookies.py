"""
Cookie-based preference persistence for radtracker.

Uses streamlit-extras cookie_manager to remember the last active tab
across browser sessions. All functions are best-effort — they silently
fall back to defaults when cookies are unavailable or not yet synced.
"""


def _get_manager():
    """Get cookie manager if ready, None otherwise."""
    try:
        from streamlit_extras.cookie_manager import cookie_manager
        mgr = cookie_manager()
        return mgr if mgr.ready() else None
    except Exception:
        return None


def get_last_tab_index(default: str = "0") -> str:
    """Return the last-viewed tab index from cookies, or default."""
    mgr = _get_manager()
    if mgr is None:
        return default
    try:
        return mgr.get("radtracker_last_tab", default)
    except Exception:
        return default


def set_last_tab_index(tab_index: str) -> None:
    """Persist the active tab index to a browser cookie."""
    mgr = _get_manager()
    if mgr is None:
        return
    try:
        mgr["radtracker_last_tab"] = tab_index
    except Exception:
        pass
