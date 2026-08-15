"""
Authentication state: data/auth.json load/save/validate plus pure
gate-logic helpers. No Streamlit.

AUTH_PATH is relative to cwd, matching src/db.py ("sqlite:///data/...")
and scripts/import_csv.py. In the container WORKDIR=/app resolves it to
the bind-mounted data/.
"""

import json
import os

from src.auth_crypto import (
    hash_password,
    new_session_secret,
    sign_session,
    verify_password,
    verify_session,
    verify_totp,
)

AUTH_PATH = "data/auth.json"

_SCHEMA_VERSION = 1
MIN_PASSWORD_LEN = 8
_SESSION_SECRET_HEX_LEN = 64


class AuthError(Exception):
    """Raised when auth.json or credentials are missing/invalid."""


def _check_type(key: str, value: object, expected: type) -> None:
    if expected is int and isinstance(value, bool):
        raise AuthError(f"auth key {key!r}: expected int, got bool {value!r}")
    if not isinstance(value, expected):
        raise AuthError(
            f"auth key {key!r}: expected {expected.__name__}, got {type(value).__name__}"
        )


def _validate(auth: object) -> dict:
    """Validate the auth.json schema; raise AuthError describing any violation."""
    if not isinstance(auth, dict):
        raise AuthError(f"auth root: expected object, got {type(auth).__name__}")
    spec: dict[str, type] = {
        "version": int,
        "username": str,
        "password_hash": str,
        "totp_required": bool,
        "totp_step_seconds": int,
        "totp_window_steps": int,
        "session_secret": str,
        "session_days": int,
        "session_cookie_secure": bool,
    }
    for key, expected in spec.items():
        if key not in auth:
            raise AuthError(f"auth key {key!r}: missing (expected {expected.__name__})")
        _check_type(key, auth[key], expected)
    if auth["totp_secret"] is not None and not isinstance(auth["totp_secret"], str):
        got = type(auth["totp_secret"]).__name__
        raise AuthError(f"auth key 'totp_secret': expected str or null, got {got}")
    return auth


def load_auth(path: str) -> dict:
    """Load and validate auth.json. Raises AuthError — fail loud, no defaults."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError as exc:
        raise AuthError(f"auth file not found: {path!r} (expected a JSON object)") from exc
    except json.JSONDecodeError as exc:
        raise AuthError(f"invalid JSON in {path!r}: {exc}") from exc
    return _validate(raw)


def save_auth(auth: dict, path: str) -> None:
    """Atomically write auth.json. chmod the tmp file BEFORE os.replace."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(auth, fh, indent=2)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def create_bootstrap_auth(
    username: str, password: str, path: str, *, cookie_secure: bool = True
) -> str:
    """Create auth.json once; never overwrite. Returns "created" or "exists"."""
    if os.path.exists(path):
        return "exists"
    if not username.strip():
        raise AuthError("username is empty: expected a non-empty username")
    if len(password) < MIN_PASSWORD_LEN:
        raise AuthError(
            f"password too short ({len(password)} chars): expected >= {MIN_PASSWORD_LEN}"
        )
    save_auth(
        {
            "version": _SCHEMA_VERSION,
            "username": username,
            "password_hash": hash_password(password),
            "totp_secret": None,
            "totp_required": False,
            "totp_step_seconds": 30,
            "totp_window_steps": 1,
            "session_secret": new_session_secret(),
            "session_days": 30,
            "session_cookie_secure": cookie_secure,
        },
        path,
    )
    return "created"


def verify_login(auth: dict, username: str, password: str) -> bool:
    """True when username and password match the stored credentials."""
    if username != auth["username"]:
        return False
    return verify_password(password, auth["password_hash"])


def is_totp_required(auth: dict) -> bool:
    """True when 2FA is active (manage_auth.py option 1)."""
    return bool(auth["totp_required"])


def verify_totp_code(auth: dict, code: str, now: int) -> bool:
    """True when the TOTP code verifies. False (never raises) without a secret."""
    secret = auth["totp_secret"]
    if not secret:
        return False
    return verify_totp(
        secret,
        code,
        step_seconds=auth["totp_step_seconds"],
        window_steps=auth["totp_window_steps"],
        now=now,
    )


def new_session_token(auth: dict, now: int) -> str:
    """Signed session token valid for auth["session_days"] days from now."""
    return sign_session(
        auth["username"], auth["session_secret"], now + auth["session_days"] * 86400
    )


def verify_session_token(auth: dict, token: str | None, now: int) -> bool:
    """True when the session cookie token is valid and unexpired. Never raises."""
    if not token:
        return False
    return verify_session(auth["username"], auth["session_secret"], token, now)
