"""Tests for src/auth_crypto.py — pure crypto (scrypt, TOTP, session tokens)."""

import base64

from src.auth_crypto import (
    hash_password,
    new_session_secret,
    new_totp_secret,
    otpauth_uri,
    sign_session,
    verify_password,
    verify_session,
    verify_totp,
)

# RFC 6238 Appendix B seed (SHA1): ASCII "12345678901234567890"
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()

RFC_VECTORS = [
    (59, "287082"),
    (1111111109, "081804"),
    (1111111111, "050471"),
    (1234567890, "005924"),
    (2000000000, "279037"),
    (20000000000, "353130"),
]


class TestTotpCode:
    def test_totp_code_rfc_vectors_match(self):
        from src.auth_crypto import totp_code

        for t, expected in RFC_VECTORS:
            assert totp_code(RFC_SECRET, t=t) == expected


class TestVerifyTotp:
    def test_verify_totp_current_code_true(self):
        assert verify_totp(RFC_SECRET, "287082", now=59) is True

    def test_verify_totp_wrong_code_false(self):
        assert verify_totp(RFC_SECRET, "000000", now=59) is False

    def test_verify_totp_within_window_true(self):
        # code from counter 1 (t=59); now=89 is counter 2, one step ahead
        assert verify_totp(RFC_SECRET, "287082", now=89, window_steps=1) is True

    def test_verify_totp_beyond_window_false(self):
        # now=119 is counter 3, two steps ahead of the code's counter
        assert verify_totp(RFC_SECRET, "287082", now=119, window_steps=1) is False

    def test_verify_totp_malformed_secret_false(self):
        assert verify_totp("not!base32!", "123456", now=59) is False

    def test_verify_totp_empty_secret_false(self):
        assert verify_totp("", "123456", now=59) is False

    def test_verify_totp_non_numeric_code_false(self):
        assert verify_totp(RFC_SECRET, "abcdef", now=59) is False

    def test_verify_totp_non_ascii_code_false_no_exception(self):
        assert verify_totp(RFC_SECRET, "١٢٣٤٥٦", now=59) is False


class TestNewTotpSecret:
    def test_new_totp_secret_32_char_base32(self):
        secret = new_totp_secret()
        assert len(secret) == 32
        base64.b32decode(secret + "=" * (-len(secret) % 8))

    def test_new_totp_secret_two_calls_differ(self):
        assert new_totp_secret() != new_totp_secret()


class TestOtpauthUri:
    def test_otpauth_uri_exact_format(self):
        uri = otpauth_uri("ABCDEF", "admin")
        assert uri == "otpauth://totp/radtracker:admin?secret=ABCDEF&issuer=radtracker"

    def test_otpauth_uri_username_url_encoded(self):
        uri = otpauth_uri("ABCDEF", "user name@x")
        assert "user%20name%40x" in uri


class TestPasswordHashing:
    def test_hash_password_format(self):
        stored = hash_password("s3cret-password")
        scheme, n, r, p, salt, digest = stored.split("$")
        assert scheme == "scrypt"
        assert (int(n), int(r), int(p)) == (16384, 8, 1)
        assert len(salt) == 32
        assert len(digest) == 64

    def test_verify_password_roundtrip_true(self):
        assert verify_password("s3cret-password", hash_password("s3cret-password")) is True

    def test_verify_password_wrong_password_false(self):
        assert verify_password("wrong", hash_password("s3cret-password")) is False

    def test_verify_password_tampered_hash_false(self):
        stored = hash_password("s3cret-password")
        flipped = stored[:-1] + ("0" if stored[-1] != "0" else "1")
        assert verify_password("s3cret-password", flipped) is False

    def test_verify_password_malformed_stored_false(self):
        for bad in ("", "plainstring", "scrypt$1$2$3", "scrypt$abc$8$1$zz$zz"):
            assert verify_password("x", bad) is False


class TestSessionToken:
    def test_new_session_secret_64_hex(self):
        secret = new_session_secret()
        assert len(secret) == 64
        bytes.fromhex(secret)

    def test_new_session_secret_two_calls_differ(self):
        assert new_session_secret() != new_session_secret()

    def test_sign_verify_session_roundtrip_true(self):
        token = sign_session("admin", "ab" * 32, expires=2000)
        assert verify_session("admin", "ab" * 32, token, now=1000) is True

    def test_verify_session_wrong_secret_false(self):
        token = sign_session("admin", "ab" * 32, expires=2000)
        assert verify_session("admin", "cd" * 32, token, now=1000) is False

    def test_verify_session_tampered_token_false(self):
        token = sign_session("admin", "ab" * 32, expires=2000)
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert verify_session("admin", "ab" * 32, tampered, now=1000) is False

    def test_verify_session_expired_false(self):
        token = sign_session("admin", "ab" * 32, expires=2000)
        assert verify_session("admin", "ab" * 32, token, now=2000) is False

    def test_verify_session_malformed_false(self):
        for bad in ("", "nodot", "a.b.c", "xyz.abc"):
            assert verify_session("admin", "ab" * 32, bad, now=1000) is False

    def test_verify_session_non_ascii_token_false_no_exception(self):
        assert verify_session("admin", "ab" * 32, "2000.áéí", now=1000) is False
