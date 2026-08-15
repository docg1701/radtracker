"""
Streamlit login gate: session restore, password form, TOTP step,
2FA sidebar footer, logout.

Only st.form usage in the project — the gate is a state machine and
forms keep Enter-submits atomic (no rerun per keystroke).
"""

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


def render_2fa_footer(auth: dict) -> None:
    """Small sidebar footer note when 2FA is off.

    Usage: `render_2fa_footer(auth)` in app.py AFTER render_sidebar, so the
    note lands at the bottom of the sidebar instead of the page top.
    """
    if is_totp_required(auth):
        return
    st.sidebar.caption("2FA desativada — rode `radtracker-auth` no servidor para ativar.")


def render_logout_button() -> None:
    """Sidebar logout: clears session state + session cookie, then reruns.

    Only rendered while authenticated — a stale sidebar button must never
    survive into the login screen (the gate stops the script before
    app.py reaches this call, but the guard keeps the invariant explicit).
    """
    if not st.session_state.get("auth_authenticated"):
        return
    if st.sidebar.button("Sair", icon=":material/logout:", key="auth_logout"):
        st.session_state.auth_authenticated = False
        st.session_state.pop("auth_username", None)
        delete_session_token(secure=bool(st.session_state.get("_auth_cookie_secure", True)))
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
            st.markdown("## :material/lock: **radtracker**")
            with st.form("auth_login"):
                username = st.text_input("Usuário", key="auth_login_username")
                password = st.text_input("Senha", type="password", key="auth_login_password")
                submitted = st.form_submit_button(
                    "Entrar", icon=":material/login:"
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
                    "Verificar", icon=":material/key:"
                )
        if not submitted:
            return
        if not verify_totp_code(auth, code, int(time.time())):
            st.error("Código inválido ou expirado.")
            return
        st.session_state.pop("auth_awaiting_totp", None)
        _establish_session(auth)
        st.rerun()
