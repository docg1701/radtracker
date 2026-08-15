"""
Cookie-based persistence for radtracker: last active tab + signed
session token.

Two tiny CCv2 components, both one-way:

- Reader: publishes document.cookie ONCE per server session (until a
  non-empty snapshot arrives), then renders with read=False forever.
- Writer: applies queued write/delete operations and never publishes.

Why: streamlit-extras CookieManager publishes its snapshot on EVERY
cookie change, and setStateValue always reruns the script — each tab
click changed a cookie and the extra rerun raced the user's next click
(tab radio reverted on the first click). One-way components produce
zero cookie-driven reruns.
"""

import json

import streamlit as st
import streamlit.components.v2 as components

_TAB_COOKIE = "radtracker_last_tab"
_SESSION_COOKIE = "radtracker_session"
_WRITE_OPS_KEY = "_radtracker_cookie_write_ops"
_SNAPSHOT_KEY = "_radtracker_cookie_snapshot"

_COOKIE_READER = components.component(
    name="radtracker.cookie_reader",
    html="<div aria-hidden='true'></div>",
    js="""
    export default function (component) {
        if (!component.data?.read) {
            return () => {};
        }
        const snapshot = {};
        const raw = document.cookie || "";
        raw.split(";").forEach((part) => {
            const trimmed = part.trim();
            if (!trimmed) {
                return;
            }
            const idx = trimmed.indexOf("=");
            if (idx < 0) {
                return;
            }
            let name = trimmed.slice(0, idx).trim();
            let value = trimmed.slice(idx + 1).trim();
            try {
                name = decodeURIComponent(name);
                value = decodeURIComponent(value);
            } catch (_) {
                // keep raw
            }
            snapshot[name] = value;
        });
        component.setStateValue("snapshot_json", JSON.stringify(snapshot));
        return () => {};
    }
    """,
)

_COOKIE_WRITER = components.component(
    name="radtracker.cookie_writer",
    html="<div aria-hidden='true'></div>",
    js="""
    export default function (component) {
        const ops = component.data?.operations ?? [];
        ops.forEach((op) => {
            const attrs = [
                `${encodeURIComponent(op.name)}=${encodeURIComponent(op.value)}`,
                "path=/",
            ];
            if (op.maxAge !== null && op.maxAge !== undefined) {
                attrs.push(`max-age=${op.maxAge}`);
            }
            if (op.secure) {
                attrs.push("secure");
            }
            attrs.push("samesite=lax");
            document.cookie = attrs.join("; ");
        });
        return () => {};
    }
    """,
)


def read_cookies_once() -> dict[str, str]:
    """Return the browser cookies, synced once per server session.

    Usage: `snapshot = read_cookies_once()` — empty dict on the very first
    run (the browser has not published yet); a rerun follows automatically.
    """
    if _SNAPSHOT_KEY in st.session_state:
        return st.session_state[_SNAPSHOT_KEY]
    result = _COOKIE_READER(
        data={"read": True},
        default={"snapshot_json": None},
        on_snapshot_json_change=lambda: None,
    )
    snapshot_json = result.snapshot_json
    if snapshot_json:
        st.session_state[_SNAPSHOT_KEY] = json.loads(snapshot_json)
    return st.session_state.get(_SNAPSHOT_KEY, {})


def queue_cookie_write(
    name: str, value: str, *, max_age: int | None = None, secure: bool = True
) -> None:
    """Queue a cookie write for render_cookie_writer()."""
    ops = st.session_state.setdefault(_WRITE_OPS_KEY, [])
    ops.append({"name": name, "value": value, "maxAge": max_age, "secure": secure})


def render_cookie_writer() -> None:
    """Render the one-way writer with all queued operations, then clear them.

    Call at the end of every flow (app.py and the gate) so queued writes
    reach the browser in the same run without triggering reruns back.
    """
    ops = st.session_state.setdefault(_WRITE_OPS_KEY, [])
    _COOKIE_WRITER(data={"operations": ops})
    st.session_state[_WRITE_OPS_KEY] = []


def get_last_tab_index(default: str = "0") -> str:
    """Return the last-viewed tab index from the synced cookie snapshot."""
    try:
        return read_cookies_once().get(_TAB_COOKIE, default)
    except Exception:
        return default


def set_last_tab_index(tab_index: str) -> None:
    """Queue the active tab index as a cookie write (non-secure, harmless data)."""
    queue_cookie_write(_TAB_COOKIE, tab_index, secure=False)


def get_session_token() -> str | None:
    """Return the session cookie value from the synced snapshot, or None."""
    try:
        token = read_cookies_once().get(_SESSION_COOKIE)
    except Exception:
        return None
    return token if isinstance(token, str) and token else None


def set_session_token(token: str, *, max_age: int, secure: bool) -> None:
    """Queue the signed session token as a cookie write (login)."""
    queue_cookie_write(_SESSION_COOKIE, token, max_age=max_age, secure=secure)


def delete_session_token(secure: bool) -> None:
    """Queue the session cookie deletion (logout) as a max-age=0 write."""
    queue_cookie_write(_SESSION_COOKIE, "", max_age=0, secure=secure)
