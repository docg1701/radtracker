"""
Interactive SSH CLI to manage radtracker authentication (KIAUH-style).

Run inside the container: `python -m scripts.manage_auth`
(host wrapper: /usr/local/bin/radtracker-auth). Plain input()/getpass,
PT-BR. All writes go through auth_store.save_auth (atomic, 0600).
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

_MENU = """
┌──────────────────────────────────────────┐
│ Radtracker — Gestão de autenticação      │
├──────────────────────────────────────────┤
│ 1) Ativar / reconfigurar 2FA (QR code)   │
│ 2) Desativar 2FA                         │
│ 3) Trocar senha                          │
│ 4) Trocar usuário                        │
│ 5) Sessão web (dias)                     │
│ 6) Reparar auth.json                     │
│ 7) Status                                │
│ 0) Sair                                  │
└──────────────────────────────────────────┘"""


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [s/N] ").strip().lower() == "s"


def _read_new_password() -> str | None:
    first = getpass.getpass("Nova senha: ")
    if first != getpass.getpass("Repita a nova senha: "):
        print("As senhas não conferem.")
        return None
    if len(first) < MIN_PASSWORD_LEN:
        print(f"Senha curta demais — mínimo {MIN_PASSWORD_LEN} caracteres.")
        return None
    return first


def _enable_2fa(auth: dict) -> None:
    if auth["totp_required"]:
        print("2FA já ativada — o QR abaixo contém um NOVO segredo; "
              "re-escaneie antes de digitar o código.")
    secret = new_totp_secret()
    uri = otpauth_uri(secret, auth["username"])
    if shutil.which("qrencode"):
        subprocess.run(["qrencode", "-t", "ANSIUTF8", uri], check=False)
    else:
        print("qrencode não encontrado — cadastre a URI manualmente.")
    print(f"\nURI manual: {uri}\n")
    code = input("Digite o código atual do autenticador: ").strip()
    ok = verify_totp(
        secret,
        code,
        step_seconds=auth["totp_step_seconds"],
        window_steps=auth["totp_window_steps"],
    )
    if not ok:
        print("Código inválido — 2FA inalterada.")
        return
    auth["totp_secret"] = secret
    auth["totp_required"] = True
    save_auth(auth, AUTH_PATH)
    print("2FA ativada.")


def _disable_2fa(auth: dict) -> None:
    if not _confirm("Confirma desativar a 2FA?"):
        print("Nada alterado.")
        return
    auth["totp_required"] = False
    save_auth(auth, AUTH_PATH)
    print("2FA desativada (segredo mantido para reativação).")


def _change_password(auth: dict) -> None:
    password = _read_new_password()
    if password is None:
        return
    auth["password_hash"] = hash_password(password)
    auth["session_secret"] = new_session_secret()
    save_auth(auth, AUTH_PATH)
    print("Senha alterada — todas as sessões web foram encerradas.")


def _change_username(auth: dict) -> None:
    username = input("Novo usuário: ").strip()
    if not username:
        print("Usuário não pode ser vazio.")
        return
    auth["username"] = username
    save_auth(auth, AUTH_PATH)
    print("Usuário alterado — sessões web anteriores foram encerradas.")


def _status(auth: dict) -> None:
    mode = stat.S_IMODE(os.stat(AUTH_PATH).st_mode)
    print(f"Usuário: {auth['username']}")
    print(f"2FA: {'ativada' if auth['totp_required'] else 'DESATIVADA'}")
    print(f"TOTP: passo {auth['totp_step_seconds']}s, janela ±{auth['totp_window_steps']}")
    print(f"Sessão web: {auth['session_days']} dias, cookie secure={auth['session_cookie_secure']}")
    print(f"Arquivo: {AUTH_PATH} (modo {mode:o})")


def _repair() -> None:
    """Re-init auth.json after confirming; removes a corrupt file first."""
    if not _confirm(f"Re-inicializar {AUTH_PATH} (2FA desativada)?"):
        print("Nada alterado.")
        return
    username = input("Usuário: ").strip()
    password = _read_new_password()
    if password is None:
        return
    https = _confirm("Acesso via HTTPS (domínio com certificado)?")
    if os.path.exists(AUTH_PATH):
        os.remove(AUTH_PATH)
    create_bootstrap_auth(username, password, AUTH_PATH, cookie_secure=https)
    print("auth.json re-inicializado.")


def _repair_if_healthy(auth: dict) -> None:
    load_auth(AUTH_PATH)
    print("auth.json íntegro — nada a reparar.")


def _set_session_days(auth: dict) -> None:
    """Change session cookie lifetime; rotates the secret so existing
    cookies die immediately and every browser must log in again."""
    raw = input(f"Dias de duração da sessão (atual: {auth['session_days']}, 1–365): ").strip()
    try:
        days = int(raw)
    except ValueError:
        print("Valor inválido — precisa ser um número inteiro.")
        return
    if not 1 <= days <= 365:
        print("Fora do intervalo permitido (1–365).")
        return
    auth["session_days"] = days
    auth["session_secret"] = new_session_secret()
    save_auth(auth, AUTH_PATH)
    print(f"Sessão web agora dura {days} dia(s). "
          "Cookies existentes foram invalidados — faça login novamente.")


def _dispatch(choice: str, auth: dict) -> None:
    actions: dict[str, Callable[[dict], None]] = {
        "1": _enable_2fa,
        "2": _disable_2fa,
        "3": _change_password,
        "4": _change_username,
        "5": _set_session_days,
        "6": _repair_if_healthy,
        "7": _status,
    }
    action = actions.get(choice)
    if action is None:
        print("Opção inválida.")
        return
    action(auth)


def main() -> int:
    """Menu loop. Usage: `python -m scripts.manage_auth` (needs a TTY)."""
    try:
        auth = load_auth(AUTH_PATH)
    except AuthError as exc:
        print(f"Problema em {AUTH_PATH}: {exc}")
        if _confirm("Reparar agora?"):
            _repair()
        return 1
    while True:
        print(_MENU)
        try:
            choice = input("Opção: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice == "0":
            return 0
        try:
            _dispatch(choice, auth)
        except (AuthError, EOFError, KeyboardInterrupt) as exc:
            print(f"\nOperação abortada: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
