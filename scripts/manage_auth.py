"""
Interactive SSH CLI to manage radtracker authentication (KIAUH-style).

Run inside the container: `python -m scripts.manage_auth`
(host wrapper: /usr/local/bin/radtracker-auth). Plain input()/getpass,
English-native with a PT-BR option (menu item before Exit). All writes go
through auth_store.save_auth (atomic, 0600). The CLI language lives in
auth.json (`cli_language`) — separate from the web UX language.
"""

import getpass
import os
import shutil
import stat
import subprocess
from collections.abc import Callable

from src.auth_crypto import (
    hash_password,
    new_session_secret,
    new_totp_secret,
    otpauth_uri,
    verify_totp,
)
from src.auth_store import (
    AUTH_PATH,
    MIN_PASSWORD_LEN,
    AuthError,
    create_bootstrap_auth,
    load_auth,
    save_auth,
)
from src.i18n import translate


def _confirm(prompt: str, lang: str) -> bool:
    yes = "y" if lang == "en" else "s"
    return input(translate("cli.confirm", lang, prompt=prompt)).strip().lower() == yes


def _read_new_password(lang: str) -> str | None:
    first = getpass.getpass(translate("cli.new_password", lang))
    if first != getpass.getpass(translate("cli.repeat_password", lang)):
        print(translate("cli.passwords_mismatch", lang))
        return None
    if len(first) < MIN_PASSWORD_LEN:
        print(translate("cli.password_too_short", lang, min=MIN_PASSWORD_LEN))
        return None
    return first


def _enable_2fa(auth: dict, lang: str) -> None:
    if auth["totp_required"]:
        print(translate("cli.2fa_already", lang))
    secret = new_totp_secret()
    uri = otpauth_uri(secret, auth["username"])
    if shutil.which("qrencode"):
        subprocess.run(["qrencode", "-t", "ANSIUTF8", uri], check=False)
    else:
        print(translate("cli.qrencode_missing", lang))
    print(translate("cli.manual_uri", lang, uri=uri))
    code = input(translate("cli.enter_code", lang)).strip()
    ok = verify_totp(
        secret,
        code,
        step_seconds=auth["totp_step_seconds"],
        window_steps=auth["totp_window_steps"],
    )
    if not ok:
        print(translate("cli.2fa_invalid", lang))
        return
    auth["totp_secret"] = secret
    auth["totp_required"] = True
    save_auth(auth, AUTH_PATH)
    print(translate("cli.2fa_enabled", lang))


def _disable_2fa(auth: dict, lang: str) -> None:
    if not _confirm(translate("cli.confirm_disable_2fa", lang), lang):
        print(translate("cli.nothing_changed", lang))
        return
    auth["totp_required"] = False
    save_auth(auth, AUTH_PATH)
    print(translate("cli.2fa_disabled", lang))


def _change_password(auth: dict, lang: str) -> None:
    password = _read_new_password(lang)
    if password is None:
        return
    auth["password_hash"] = hash_password(password)
    auth["session_secret"] = new_session_secret()
    save_auth(auth, AUTH_PATH)
    print(translate("cli.password_changed", lang))


def _change_username(auth: dict, lang: str) -> None:
    username = input(translate("cli.new_username", lang)).strip()
    if not username:
        print(translate("cli.username_empty", lang))
        return
    auth["username"] = username
    save_auth(auth, AUTH_PATH)
    print(translate("cli.username_changed", lang))


def _status(auth: dict, lang: str) -> None:
    mode = stat.S_IMODE(os.stat(AUTH_PATH).st_mode)
    state = (
        translate("cli.status.2fa_on", lang)
        if auth["totp_required"]
        else translate("cli.status.2fa_off", lang)
    )
    print(translate("cli.status.user", lang, name=auth["username"]))
    print(translate("cli.status.2fa", lang, state=state))
    print(translate(
        "cli.status.totp", lang,
        step=auth["totp_step_seconds"], window=auth["totp_window_steps"],
    ))
    print(translate(
        "cli.status.session", lang,
        days=auth["session_days"], secure=auth["session_cookie_secure"],
    ))
    print(translate("cli.status.file", lang, path=AUTH_PATH, mode=mode))


def _repair(lang: str) -> None:
    """Re-init auth.json after confirming; removes a corrupt file first."""
    if not _confirm(translate("cli.repair_confirm", lang, path=AUTH_PATH), lang):
        print(translate("cli.nothing_changed", lang))
        return
    username = input(translate("cli.username_prompt", lang)).strip()
    password = _read_new_password(lang)
    if password is None:
        return
    https = _confirm(translate("cli.https_confirm", lang), lang)
    if os.path.exists(AUTH_PATH):
        os.remove(AUTH_PATH)
    create_bootstrap_auth(username, password, AUTH_PATH, cookie_secure=https)
    print(translate("cli.repaired", lang))


def _repair_if_healthy(auth: dict, lang: str) -> None:
    load_auth(AUTH_PATH)
    print(translate("cli.healthy", lang))


def _set_session_days(auth: dict, lang: str) -> None:
    """Change session cookie lifetime; rotates the secret so existing
    cookies die immediately and every browser must log in again."""
    prompt = translate(
        "cli.session_days_prompt", lang, current=auth["session_days"]
    )
    raw = input(prompt).strip()
    try:
        days = int(raw)
    except ValueError:
        print(translate("cli.invalid_number", lang))
        return
    if not 1 <= days <= 365:
        print(translate("cli.out_of_range", lang))
        return
    auth["session_days"] = days
    auth["session_secret"] = new_session_secret()
    save_auth(auth, AUTH_PATH)
    print(translate("cli.session_updated", lang, days=days))


def _toggle_language(auth: dict, lang: str) -> None:
    """Flip cli_language in auth.json (web UX language is separate)."""
    new_lang = "pt" if lang == "en" else "en"
    auth["cli_language"] = new_lang
    save_auth(auth, AUTH_PATH)
    print(translate("cli.lang_switched", new_lang))


def _menu(lang: str) -> str:
    """Build the menu box with the language option right before Exit."""
    lines = [
        f"Radtracker — {translate('cli.menu.subtitle', lang)}",
    ] + [
        f"{i}) {translate(f'cli.menu.{i}', lang)}" for i in range(1, 9)
    ] + [
        f"0) {translate('cli.menu.exit', lang)}",
    ]
    width = max(len(line) for line in lines) + 4
    box = ["┌" + "─" * width + "┐"]
    for line in lines:
        box.append(f"│  {line.ljust(width - 2)}│")
    box.append("└" + "─" * width + "┘")
    return "\n".join(box)


def _dispatch(choice: str, auth: dict, lang: str) -> None:
    actions: dict[str, Callable[[dict, str], None]] = {
        "1": _enable_2fa,
        "2": _disable_2fa,
        "3": _change_password,
        "4": _change_username,
        "5": _set_session_days,
        "6": _repair_if_healthy,
        "7": _status,
        "8": _toggle_language,
    }
    action = actions.get(choice)
    if action is None:
        print(translate("cli.invalid_option", lang))
        return
    action(auth, lang)


def main() -> int:
    """Menu loop. Usage: `python -m scripts.manage_auth` (needs a TTY)."""
    try:
        auth = load_auth(AUTH_PATH)
    except AuthError as exc:
        print(translate("cli.auth_problem", "en", path=AUTH_PATH, error=exc))
        if _confirm(translate("cli.repair_now", "en"), "en"):
            _repair("en")
        return 1
    while True:
        lang = auth.get("cli_language", "en")
        print(_menu(lang))
        try:
            choice = input(translate("cli.option.prompt", lang)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice == "0":
            return 0
        try:
            _dispatch(choice, auth, lang)
        except (AuthError, EOFError, KeyboardInterrupt) as exc:
            print(translate("cli.operation_aborted", lang, error=exc))


if __name__ == "__main__":
    raise SystemExit(main())
