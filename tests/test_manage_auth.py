"""Tests for scripts/manage_auth.py — session-days option (CLI helpers)."""

import json

import scripts.manage_auth as ma


def test_set_session_days_valid_updates_days_and_rotates_secret(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    monkeypatch.setattr(ma, "AUTH_PATH", str(auth_path))
    monkeypatch.setattr("builtins.input", lambda _: "45")
    auth = {"session_days": 30, "session_secret": "old-secret"}
    ma._set_session_days(auth, "en")
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
    ma._set_session_days(auth, "en")
    assert auth == {"session_days": 30, "session_secret": "keep"}
    assert not auth_path.exists()


def test_set_session_days_out_of_range_leaves_auth_unchanged(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    monkeypatch.setattr(ma, "AUTH_PATH", str(auth_path))
    monkeypatch.setattr("builtins.input", lambda _: "400")
    auth = {"session_days": 30, "session_secret": "keep"}
    ma._set_session_days(auth, "en")
    assert auth == {"session_days": 30, "session_secret": "keep"}
    assert not auth_path.exists()


def test_menu_language_option_before_exit():
    menu_en = ma._menu("en")
    assert "8) Language / Idioma (EN)" in menu_en
    assert "0) Exit" in menu_en
    # 8 comes before 0 in the menu order
    assert menu_en.index("8) Language / Idioma") < menu_en.index("0) Exit")
    # numbered items 1-7 present
    for i in range(1, 8):
        assert f"{i}) " in menu_en


def test_menu_pt_after_toggle():
    menu_pt = ma._menu("pt")
    assert "Idioma / Language (PT)" in menu_pt
    assert "0) Sair" in menu_pt


def test_toggle_language_flips_and_persists(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    monkeypatch.setattr(ma, "AUTH_PATH", str(auth_path))
    auth = {"cli_language": "en"}
    ma._toggle_language(auth, "en")
    assert auth["cli_language"] == "pt"
    import json
    saved = json.loads(auth_path.read_text())
    assert saved["cli_language"] == "pt"
    # web UX language stays untouched (separate config)
    assert "language" not in saved
