"""
Pure crypto for radtracker authentication.

scrypt password hashing, RFC 6238 TOTP, otpauth URIs, and HMAC-signed
session tokens. No I/O, no Streamlit. All verifiers return False (never
raise) on malformed input.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse

_SCRYPT_PARAMS = {"n": 16384, "r": 8, "p": 1, "dklen": 32}
_SALT_BYTES = 16
_TOTP_STEP_SECONDS = 30
_TOTP_DIGITS_MOD = 1_000_000
_SESSION_LABEL = "radtracker-session"


def hash_password(password: str) -> str:
    """Hash a password with scrypt. Usage: `stored = hash_password("s3cret")`."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT_PARAMS)
    n, r, p = _SCRYPT_PARAMS["n"], _SCRYPT_PARAMS["r"], _SCRYPT_PARAMS["p"]
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against the stored scrypt format string. Never raises."""
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def new_totp_secret() -> str:
    """Random 20-byte TOTP secret, base32 without padding (32 chars)."""
    return base64.b32encode(secrets.token_bytes(20)).rstrip(b"=").decode()


def _decode_secret(secret_b32: str) -> bytes:
    padded = secret_b32.upper() + "=" * (-len(secret_b32) % 8)
    return base64.b32decode(padded)


def _hotp(key: bytes, counter: int) -> str:
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % _TOTP_DIGITS_MOD:06d}"


def totp_code(secret_b32: str, t: int | None = None) -> str:
    """6-digit TOTP code at time t (epoch seconds; defaults to now)."""
    if t is None:
        t = int(time.time())
    return _hotp(_decode_secret(secret_b32), t // _TOTP_STEP_SECONDS)


def verify_totp(
    secret_b32: str,
    code: str,
    *,
    step_seconds: int = _TOTP_STEP_SECONDS,
    window_steps: int = 1,
    now: int | None = None,
) -> bool:
    """True when code matches any counter within ±window_steps. Never raises."""
    if not code.isascii() or not code.isdigit():
        return False
    try:
        key = _decode_secret(secret_b32)
    except ValueError:
        return False
    if now is None:
        now = int(time.time())
    counter = now // step_seconds
    for delta in range(-window_steps, window_steps + 1):
        if hmac.compare_digest(_hotp(key, counter + delta), code):
            return True
    return False


def otpauth_uri(secret_b32: str, username: str, issuer: str = "radtracker") -> str:
    """otpauth:// URI for authenticator apps. Usage: otpauth_uri(secret, "admin")."""
    quoted = urllib.parse.quote(username)
    return f"otpauth://totp/{issuer}:{quoted}?secret={secret_b32}&issuer={issuer}"


def new_session_secret() -> str:
    """Random 256-bit secret (64 hex chars) for signing session cookies."""
    return secrets.token_hex(32)


def sign_session(username: str, secret_hex: str, expires: int) -> str:
    """Signed session token: "<expires>.<hmac_hex>"."""
    key = bytes.fromhex(secret_hex)
    msg = f"{_SESSION_LABEL}:{username}:{expires}".encode()
    return f"{expires}.{hmac.new(key, msg, hashlib.sha256).hexdigest()}"


def verify_session(username: str, secret_hex: str, token: str, now: int) -> bool:
    """True when token is well-signed and not expired. Never raises."""
    if not token.isascii():
        return False
    parts = token.split(".")
    if len(parts) != 2:
        return False
    try:
        expires = int(parts[0])
        key = bytes.fromhex(secret_hex)
    except ValueError:
        return False
    if now >= expires:
        return False
    msg = f"{_SESSION_LABEL}:{username}:{expires}".encode()
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts[1])
