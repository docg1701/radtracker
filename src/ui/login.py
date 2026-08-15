"""
Streamlit login gate: session restore, password form, TOTP step,
2FA sidebar footer, logout.

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


def render_login_gate(auth: dict) -> None:
    """Block the app until authenticated.

    Usage: `render_login_gate(load_auth(AUTH_PATH))` in app.py.
    Session restore runs only when the key is absent (once per server
    session) — after logout the key is False and the (async) cookie delete
    must not immediately re-authenticate.
    """
    render_cookie_writer()
    if "auth_authenticated" not in st.session_state:
        _restore_session(auth)
    if st.session_state.get("auth_authenticated"):
        return
    _render_login_form(auth)
    st.stop()


@st.cache_data(show_spinner=False)
def _app_version() -> str:
    """Version from pyproject.toml (single source of truth), cached per run."""
    import tomllib

    with open("pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def render_sidebar_footer(auth: dict) -> None:
    """Sidebar footer: version/mode line + 2FA status, same typography.

    Usage: `render_sidebar_footer(auth)` in app.py AFTER render_sidebar.
    """
    st.sidebar.divider()
    mode = os.environ.get("RADTRACKER_MODE", "local")
    st.sidebar.caption(f"Radtracker v{_app_version()} · {mode}")
    if is_totp_required(auth):
        st.sidebar.caption("2FA ativado.")
    else:
        st.sidebar.caption("2FA desativado.")


def render_sidebar_header() -> None:
    """Sidebar top row: 'Radtracker' h1 left + Sair button right.

    The button is stretched inside its column; the sidebar has a fixed
    desktop width, so the resulting button width is stable regardless of
    window size (no letter stacking).
    """
    if not st.session_state.get("auth_authenticated"):
        return
    title_col, logout_col = st.sidebar.columns([4, 2.5], vertical_alignment="center")
    with title_col:
        st.markdown("# Radtracker")
    with logout_col:
        if st.button("Sair", icon=":material/logout:", key="auth_logout", width="stretch"):
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
                username = st.text_input("Usuário", key="auth_login_username")
                password = st.text_input("Senha", type="password", key="auth_login_password")
                submitted = st.form_submit_button(
                    "Entrar", type="primary", icon=":material/login:"
                )
        if not submitted:
            return
        if not verify_login(auth, username, password):
            st.error("Usuário ou senha inválidos.")
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
            st.markdown("## :material/verified_user: **Verificação em duas etapas**")
            with st.form("auth_totp"):
                code = st.text_input(
                    "Código do autenticador",
                    type="password",
                    max_chars=6,
                    key="auth_totp_code",
                )
                submitted = st.form_submit_button(
                    "Verificar", type="primary", icon=":material/key:"
                )
        if not submitted:
            return
        if not verify_totp_code(auth, code, int(time.time())):
            st.error("Código inválido ou expirado.")
            return
        st.session_state.pop("auth_awaiting_totp", None)
        _establish_session(auth)
        st.rerun()
