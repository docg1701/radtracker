"""Tests for scripts/manage_auth.py — session-days option (CLI helpers)."""

import json

import scripts.manage_auth as ma


def test_set_session_days_valid_updates_days_and_rotates_secret(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    monkeypatch.setattr(ma, "AUTH_PATH", str(auth_path))
    monkeypatch.setattr("builtins.input", lambda _: "45")
    auth = {"session_days": 30, "session_secret": "old-secret"}
    ma._set_session_days(auth)
    assert auth["session_days"] == 45
    assert auth["session_secret"] != "old-secret"
    saved = json.loads(auth_path.read_text())
    assert saved["session_days"] == 45
    assert saved["session_secret"] == auth["session_secret"]


def test_set_session_days_non_numeric_leaves_auth_unchanged(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    monkeypatch.setattr(ma, "AUTH_PATH", str(auth_path))
    monkeypatch.setattr("builtins.input", lambda _: "abc")
    auth = {"session_days": 30, "session_secret": "keep"}
    ma._set_session_days(auth)
    assert auth == {"session_days": 30, "session_secret": "keep"}
    assert not auth_path.exists()


def test_set_session_days_out_of_range_leaves_auth_unchanged(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    monkeypatch.setattr(ma, "AUTH_PATH", str(auth_path))
    monkeypatch.setattr("builtins.input", lambda _: "400")
    auth = {"session_days": 30, "session_secret": "keep"}
    ma._set_session_days(auth)
    assert auth == {"session_days": 30, "session_secret": "keep"}
    assert not auth_path.exists()
