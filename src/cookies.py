"""
Cookie-based persistence for radtracker.

Uses streamlit-extras cookie_manager to remember the last active tab and
the signed session token across browser sessions. All helpers are
best-effort — they silently fall back to defaults when cookies are
unavailable or not yet synced.

Hard rule: construct the manager ONCE per run (get_cookie_manager in
app.py) and pass it down — a second construction in the same run raises
StreamlitDuplicateElementKey. Constructing every run is also what flushes
queued set/delete operations to the browser.
"""

from streamlit_extras.cookie_manager import CookieManager, cookie_manager

_TAB_COOKIE = "radtracker_last_tab"
_SESSION_COOKIE = "radtracker_session"


def get_cookie_manager() -> CookieManager | None:
    """Construct this run's CookieManager. Usage: `mgr = get_cookie_manager()`."""
    try:
        return cookie_manager()
    except Exception:
        return None


def get_last_tab_index(mgr: CookieManager | None, default: str = "0") -> str:
    """Return the last-viewed tab index from cookies, or default."""
    if mgr is None or not mgr.ready():
        return default
    try:
        return mgr.get(_TAB_COOKIE, default)
    except Exception:
        return default


def set_last_tab_index(mgr: CookieManager | None, tab_index: str) -> None:
    """Persist the active tab index to a browser cookie."""
    if mgr is None or not mgr.ready():
        return
    try:
        mgr[_TAB_COOKIE] = tab_index
    except Exception:
        pass


def get_session_token(mgr: CookieManager | None) -> str | None:
    """Return the session cookie value, or None when unavailable."""
    if mgr is None or not mgr.ready():
        return None
    try:
        value = mgr.get(_SESSION_COOKIE)
    except Exception:
        return None
    return value if isinstance(value, str) else None


def set_session_token(
    mgr: CookieManager | None, token: str, *, max_age: int, secure: bool
) -> None:
    """Persist the signed session token (login). secure=False on plain-HTTP LAN."""
    if mgr is None or not mgr.ready():
        return
    try:
        mgr.set(_SESSION_COOKIE, token, max_age=max_age, secure=secure, samesite="lax")
    except Exception:
        pass


def delete_session_token(mgr: CookieManager | None) -> None:
    """Delete the session cookie (logout). Identity is name+path+domain."""
    if mgr is None or not mgr.ready():
        return
    try:
        mgr.delete(_SESSION_COOKIE)
    except Exception:
        pass
