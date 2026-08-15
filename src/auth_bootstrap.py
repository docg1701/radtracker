"""
Non-interactive auth bootstrap, run by Ansible inside the container.

Reads data/.auth_creds (line 1 = username, line 2 = password, optional
line 3 = cookie_secure:true|false), creates data/auth.json once, and
prints "created" or "exists" (Ansible keys changed_when off stdout).
"""

import os
import sys

from src.auth_store import AUTH_PATH, AuthError, create_bootstrap_auth

_CREDS_PATH = "data/.auth_creds"


def _parse_creds(text: str) -> tuple[str, str, bool]:
    lines = text.splitlines()
    if len(lines) < 2:
        raise AuthError(
            f"{_CREDS_PATH}: expected line 1 = username, line 2 = password, "
            f"got {len(lines)} line(s)"
        )
    cookie_secure = _parse_cookie_secure(lines[2] if len(lines) >= 3 else "")
    return lines[0].strip(), lines[1], cookie_secure


def _parse_cookie_secure(line: str) -> bool:
    flag = line.strip().lower()
    if not flag or flag == "cookie_secure:true":
        return True
    if flag == "cookie_secure:false":
        return False
    raise AuthError(f"{_CREDS_PATH} line 3: expected cookie_secure:true|false, got {line!r}")


def _handle_missing_creds() -> int:
    if os.path.exists(AUTH_PATH):
        print("exists")
        return 0
    print(
        f"error: {_CREDS_PATH} not found and {AUTH_PATH} missing — run the Ansible deploy",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    """Bootstrap entry point. Usage: `python -m src.auth_bootstrap` (cwd=/app)."""
    try:
        with open(_CREDS_PATH, encoding="utf-8") as fh:
            username, password, cookie_secure = _parse_creds(fh.read())
    except FileNotFoundError:
        return _handle_missing_creds()
    except AuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        result = create_bootstrap_auth(
            username, password, AUTH_PATH, cookie_secure=cookie_secure
        )
    except AuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
