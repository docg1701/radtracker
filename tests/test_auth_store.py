"""Tests for src/auth_store.py — auth.json persistence and gate helpers."""

import json
import os
import stat

import pytest

from src.auth_crypto import totp_code
from src.auth_store import (
    AuthError,
    create_bootstrap_auth,
    is_totp_required,
    load_auth,
    new_session_token,
    save_auth,
    verify_login,
    verify_session_token,
    verify_totp_code,
)


@pytest.fixture
def auth_path(tmp_path):
    return str(tmp_path / "auth.json")


@pytest.fixture
def bootstrapped(auth_path):
    create_bootstrap_auth("admin", "s3cret-password", auth_path)
    return load_auth(auth_path)


class TestCreateBootstrapAuth:
    def test_create_bootstrap_auth_writes_defaults(self, auth_path):
        assert create_bootstrap_auth("admin", "s3cret-password", auth_path) == "created"
        auth = load_auth(auth_path)
        assert auth["version"] == 1
        assert auth["username"] == "admin"
        assert auth["totp_secret"] is None
        assert auth["totp_required"] is False
        assert auth["totp_step_seconds"] == 30
        assert auth["totp_window_steps"] == 1
        assert len(auth["session_secret"]) == 64
        assert auth["session_days"] == 30
        assert auth["session_cookie_secure"] is True

    def test_create_bootstrap_auth_existing_returns_exists_and_keeps_file(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path)
        save_auth({**load_auth(auth_path), "username": "renamed"}, auth_path)
        assert create_bootstrap_auth("other", "other-password", auth_path) == "exists"
        assert load_auth(auth_path)["username"] == "renamed"

    def test_create_bootstrap_auth_short_password_raises(self, auth_path):
        with pytest.raises(AuthError, match="8"):
            create_bootstrap_auth("admin", "short", auth_path)

    def test_create_bootstrap_auth_empty_username_raises(self, auth_path):
        with pytest.raises(AuthError, match="username"):
            create_bootstrap_auth("  ", "s3cret-password", auth_path)

    def test_create_bootstrap_auth_cookie_secure_false(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path, cookie_secure=False)
        assert load_auth(auth_path)["session_cookie_secure"] is False


class TestLoadAuth:
    def test_load_auth_missing_file_raises(self, auth_path):
        with pytest.raises(AuthError, match="not found"):
            load_auth(auth_path)

    def test_load_auth_invalid_json_raises(self, auth_path):
        with open(auth_path, "w") as fh:
            fh.write("{not json")
        with pytest.raises(AuthError, match="invalid JSON"):
            load_auth(auth_path)

    def test_load_auth_missing_key_raises(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path)
        auth = load_auth(auth_path)
        del auth["password_hash"]
        with open(auth_path, "w") as fh:
            json.dump(auth, fh)
        with pytest.raises(AuthError, match="password_hash"):
            load_auth(auth_path)

    def test_load_auth_wrong_type_raises(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path)
        auth = {**load_auth(auth_path), "session_days": "thirty"}
        with open(auth_path, "w") as fh:
            json.dump(auth, fh)
        with pytest.raises(AuthError, match="session_days"):
            load_auth(auth_path)

    def test_load_auth_bool_in_int_field_raises(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path)
        auth = {**load_auth(auth_path), "totp_step_seconds": True}
        with open(auth_path, "w") as fh:
            json.dump(auth, fh)
        with pytest.raises(AuthError, match="totp_step_seconds"):
            load_auth(auth_path)

    def test_load_auth_roundtrip(self, bootstrapped):
        assert bootstrapped["username"] == "admin"


class TestSaveAuth:
    def test_save_auth_mode_0600(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path)
        mode = stat.S_IMODE(os.stat(auth_path).st_mode)
        assert mode == 0o600

    def test_save_auth_overwrites_atomically(self, auth_path):
        create_bootstrap_auth("admin", "s3cret-password", auth_path)
        auth = {**load_auth(auth_path), "session_days": 7}
        save_auth(auth, auth_path)
        assert load_auth(auth_path)["session_days"] == 7
        assert not os.path.exists(auth_path + ".tmp")


class TestGateHelpers:
    def test_verify_login_correct_true(self, bootstrapped):
        assert verify_login(bootstrapped, "admin", "s3cret-password") is True

    def test_verify_login_wrong_password_false(self, bootstrapped):
        assert verify_login(bootstrapped, "admin", "wrong-password") is False

    def test_verify_login_wrong_username_false(self, bootstrapped):
        assert verify_login(bootstrapped, "nobody", "s3cret-password") is False

    def test_is_totp_required_reflects_schema(self, bootstrapped):
        assert is_totp_required(bootstrapped) is False
        assert is_totp_required({**bootstrapped, "totp_required": True}) is True

    def test_verify_totp_code_no_secret_false(self, bootstrapped):
        assert verify_totp_code(bootstrapped, "123456", now=1000) is False

    def test_verify_totp_code_valid_true(self, bootstrapped):
        from src.auth_crypto import new_totp_secret

        secret = new_totp_secret()
        auth = {**bootstrapped, "totp_secret": secret, "totp_required": True}
        assert verify_totp_code(auth, totp_code(secret, t=1000), now=1000) is True

    def test_session_token_roundtrip_true(self, bootstrapped):
        token = new_session_token(bootstrapped, now=1000)
        assert verify_session_token(bootstrapped, token, now=1001) is True

    def test_verify_session_token_expired_false(self, bootstrapped):
        token = new_session_token(bootstrapped, now=1000)
        future = 1000 + bootstrapped["session_days"] * 86400
        assert verify_session_token(bootstrapped, token, now=future) is False

    def test_verify_session_token_tampered_false(self, bootstrapped):
        token = new_session_token(bootstrapped, now=1000)
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert verify_session_token(bootstrapped, tampered, now=1000) is False

    def test_verify_session_token_rotated_secret_false(self, bootstrapped):
        from src.auth_crypto import new_session_secret

        token = new_session_token(bootstrapped, now=1000)
        rotated = {**bootstrapped, "session_secret": new_session_secret()}
        assert verify_session_token(rotated, token, now=1000) is False

    def test_verify_session_token_username_change_false(self, bootstrapped):
        token = new_session_token(bootstrapped, now=1000)
        renamed = {**bootstrapped, "username": "renamed"}
        assert verify_session_token(renamed, token, now=1000) is False

    def test_verify_session_token_malformed_false(self, bootstrapped):
        for bad in (None, "", "nodot", "a.b.c"):
            assert verify_session_token(bootstrapped, bad, now=1000) is False
