"""
Streamlit login gate: session restore, password form, TOTP step,
2FA sidebar footer, language selector, logout.

Only st.form usage in the project — the gate is a state machine and
forms keep Enter-submits atomic (no rerun per keystroke).
"""

import os
import time

import streamlit as st

from src.auth_store import (
    is_totp_required,
    new_session_token,
    verify_login,
    verify_session_token,
    verify_totp_code,
)
from src.cookies import (
    delete_session_token,
    get_session_token,
    render_cookie_writer,
    set_session_token,
)
from src.db import get_connection, init_db, load_setting, save_setting
from src.i18n import t

_LANG_NAMES: dict[str, str] = {"en": "English", "pt": "Português"}


def render_language_selector() -> None:
    """Sidebar EN/PT selector; persists to user_settings.

    Rendered in exactly one of two mutually exclusive spots per run:
    pre-gate (unauthenticated — login screen) or inside
    render_sidebar_footer (authenticated). Same visual position in both:
    the sidebar footer zone.

    st.session_state dies on browser reload (new WebSocket), so the
    persisted preference is loaded here on the first render of a server
    session — the login screen must honor it too.
    """
    if "lang" not in st.session_state:
        conn = get_connection()
        init_db(conn)  # first boot: user_settings must exist before the read
        st.session_state.lang = load_setting(conn, "language", "en")
    st.sidebar.segmented_control(
        f":material/translate: {t('web.lang.label')}",
        options=["en", "pt"],
        format_func=lambda code: _LANG_NAMES[code],
        default=st.session_state.lang,
        key="lang_selector",
        on_change=_on_language_change,
    )


def _on_language_change() -> None:
    lang = st.session_state.lang_selector
    st.session_state.lang = lang
    save_setting(get_connection(), "language", lang)


def render_login_gate(auth: dict) -> None:
    """Block the app until authenticated.

    Usage: `render_login_gate(load_auth(AUTH_PATH))` in app.py.
    Session restore runs only when the key is absent (once per server
    session) — after logout the key is False and the (async) cookie delete
    must not immediately re-authenticate.

    Invariant: the language selector renders in exactly one of two
    mutually exclusive spots per run — here (unauthenticated, before
    st.stop) or in render_sidebar_footer (authenticated). It must NOT be
    rendered before the gate: on a cookie-restore run, session state is
    still unauthenticated at that point, so both spots would render and
    Streamlit raises StreamlitDuplicateElementKey.
    """
    render_cookie_writer()
    if "auth_authenticated" not in st.session_state:
        _restore_session(auth)
    if st.session_state.get("auth_authenticated"):
        return
    render_language_selector()
    _render_login_form(auth)
    st.stop()


@st.cache_data(show_spinner=False)
def _app_version() -> str:
    """Version from pyproject.toml (single source of truth), cached per run."""
    import tomllib

    with open("pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def render_sidebar_footer(auth: dict) -> None:
    """Sidebar footer: language selector, version/mode line, 2FA status."""
    st.sidebar.divider()
    render_language_selector()
    mode = os.environ.get("RADTRACKER_MODE", "local")
    st.sidebar.caption(f"Radtracker v{_app_version()} · {mode}")
    if is_totp_required(auth):
        st.sidebar.caption(t("web.footer.two_fa_on"))
    else:
        st.sidebar.caption(t("web.footer.two_fa_off"))


def render_sidebar_header() -> None:
    """Sidebar title: 'Radtracker' h1, left aligned."""
    st.sidebar.markdown("# Radtracker")


def render_logout_button() -> None:
    """Main-area logout button, rendered in the tab row (right aligned).

    Only rendered while authenticated — a stale button must never survive
    into the login screen (the gate stops the script before app.py reaches
    this call, but the guard keeps the invariant explicit).
    """
    if not st.session_state.get("auth_authenticated"):
        return
    if st.button(t("web.auth.logout"), icon=":material/logout:", key="auth_logout"):
        st.session_state.auth_authenticated = False
        st.session_state.pop("auth_username", None)
        delete_session_token(
            secure=bool(st.session_state.get("_auth_cookie_secure", True))
        )
        st.rerun()


def _restore_session(auth: dict) -> None:
    token = get_session_token()
    if verify_session_token(auth, token, int(time.time())):
        st.session_state.auth_authenticated = True
        st.session_state.auth_username = auth["username"]
        st.session_state._auth_cookie_secure = auth["session_cookie_secure"]


def _establish_session(auth: dict) -> None:
    now = int(time.time())
    st.session_state.auth_authenticated = True
    st.session_state.auth_username = auth["username"]
    st.session_state._auth_cookie_secure = auth["session_cookie_secure"]
    set_session_token(
        new_session_token(auth, now),
        max_age=auth["session_days"] * 86400,
        secure=auth["session_cookie_secure"],
    )


def _render_login_form(auth: dict) -> None:
    if st.session_state.get("auth_awaiting_totp"):
        _render_totp_form(auth)
        return
    left, card, right = st.columns([1, 1.4, 1], vertical_alignment="center")
    with card:
        with st.container(border=True, vertical_alignment="center"):
            st.markdown("## :material/lock: **Radtracker**")
            with st.form("auth_login"):
                username = st.text_input(t("web.auth.username"), key="auth_login_username")
                password = st.text_input(
                    t("web.auth.password"), type="password", key="auth_login_password"
                )
                submitted = st.form_submit_button(
                    t("web.auth.login"), type="primary", icon=":material/login:"
                )
        if not submitted:
            return
        if not verify_login(auth, username, password):
            st.error(t("web.auth.invalid_credentials"))
            return
        if is_totp_required(auth):
            st.session_state.auth_awaiting_totp = True
        else:
            _establish_session(auth)
        st.rerun()


def _render_totp_form(auth: dict) -> None:
    left, card, right = st.columns([1, 1.4, 1], vertical_alignment="center")
    with card:
        with st.container(border=True, vertical_alignment="center"):
            st.markdown(f"## :material/verified_user: **{t('web.auth.totp_title')}**")
            with st.form("auth_totp"):
                code = st.text_input(
                    t("web.auth.totp_code"),
                    type="password",
                    max_chars=6,
                    key="auth_totp_code",
                )
                submitted = st.form_submit_button(
                    t("web.auth.totp_verify"), type="primary", icon=":material/key:"
                )
        if not submitted:
            return
        if not verify_totp_code(auth, code, int(time.time())):
            st.error(t("web.auth.totp_invalid"))
            return
        st.session_state.pop("auth_awaiting_totp", None)
        _establish_session(auth)
        st.rerun()
