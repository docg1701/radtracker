"""
Streamlit login gate: session restore, password form, TOTP step,
2FA-off banner, logout.

Only st.form usage in the project — the gate is a state machine and
forms keep Enter-submits atomic (no rerun per keystroke).
"""

import time

import streamlit as st
from streamlit_extras.cookie_manager import CookieManager

from src.auth_store import (
    is_totp_required,
    new_session_token,
    verify_login,
    verify_session_token,
    verify_totp_code,
)
from src.cookies import delete_session_token, get_session_token, set_session_token


def render_login_gate(auth: dict, mgr: CookieManager | None) -> None:
    """Block the app until authenticated.

    Usage: `render_login_gate(load_auth(AUTH_PATH), cookie_mgr)` in app.py.
    Session restore runs only when the key is absent (once per server
    session) — after logout the key is False and the (async) cookie delete
    must not immediately re-authenticate.
    """
    if "auth_authenticated" not in st.session_state:
        _restore_session(auth, mgr)
    if st.session_state.get("auth_authenticated"):
        _render_2fa_banner(auth)
        return
    _render_login_form(auth, mgr)
    st.stop()


def render_logout_button(mgr: CookieManager | None) -> None:
    """Sidebar logout: clears session state + session cookie, then reruns."""
    if st.sidebar.button("Sair", icon=":material/logout:", key="auth_logout"):
        st.session_state.auth_authenticated = False
        st.session_state.pop("auth_username", None)
        delete_session_token(mgr)
        st.rerun()


def _restore_session(auth: dict, mgr: CookieManager | None) -> None:
    token = get_session_token(mgr)
    if verify_session_token(auth, token, int(time.time())):
        st.session_state.auth_authenticated = True
        st.session_state.auth_username = auth["username"]


def _establish_session(auth: dict, mgr: CookieManager | None) -> None:
    now = int(time.time())
    st.session_state.auth_authenticated = True
    st.session_state.auth_username = auth["username"]
    set_session_token(
        mgr,
        new_session_token(auth, now),
        max_age=auth["session_days"] * 86400,
        secure=auth["session_cookie_secure"],
    )


def _render_2fa_banner(auth: dict) -> None:
    if is_totp_required(auth):
        return
    st.warning("2FA desativada — rode `radtracker-auth` no servidor para ativar.")


def _render_login_form(auth: dict, mgr: CookieManager | None) -> None:
    if st.session_state.get("auth_awaiting_totp"):
        _render_totp_form(auth, mgr)
        return
    st.markdown(":material/lock: **radtracker — acesso restrito**")
    with st.form("auth_login"):
        username = st.text_input("Usuário", key="auth_login_username")
        password = st.text_input("Senha", type="password", key="auth_login_password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if not submitted:
        return
    if not verify_login(auth, username, password):
        st.error("Usuário ou senha inválidos.")
        return
    if is_totp_required(auth):
        st.session_state.auth_awaiting_totp = True
    else:
        _establish_session(auth, mgr)
    st.rerun()


def _render_totp_form(auth: dict, mgr: CookieManager | None) -> None:
    st.markdown(":material/lock: **radtracker — verificação em duas etapas**")
    with st.form("auth_totp"):
        code = st.text_input(
            "Código do autenticador", type="password", max_chars=6, key="auth_totp_code"
        )
        submitted = st.form_submit_button("Verificar", type="primary")
    if not submitted:
        return
    if not verify_totp_code(auth, code, int(time.time())):
        st.error("Código inválido ou expirado.")
        return
    st.session_state.pop("auth_awaiting_totp", None)
    _establish_session(auth, mgr)
    st.rerun()
