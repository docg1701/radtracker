"""Tests for src/auth_bootstrap.py — non-interactive Ansible bootstrap."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_bootstrap(cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "src.auth_bootstrap"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def workdir(tmp_path):
    (tmp_path / "data").mkdir()
    return tmp_path


def write_creds(workdir: Path, lines: list[str]) -> None:
    (workdir / "data" / ".auth_creds").write_text("\n".join(lines) + "\n")


def read_auth(workdir: Path) -> dict:
    return json.loads((workdir / "data" / "auth.json").read_text())


class TestBootstrap:
    def test_no_creds_no_auth_json_exit_1(self, workdir):
        result = run_bootstrap(workdir)
        assert result.returncode == 1
        assert ".auth_creds" in result.stderr

    def test_no_creds_but_auth_json_exists_exit_0(self, workdir):
        write_creds(workdir, ["galvani", "s3cret-password"])
        run_bootstrap(workdir)
        (workdir / "data" / ".auth_creds").unlink()
        result = run_bootstrap(workdir)
        assert result.returncode == 0
        assert result.stdout.strip() == "exists"

    def test_creds_create_auth_json_with_defaults(self, workdir):
        write_creds(workdir, ["galvani", "s3cret-password"])
        result = run_bootstrap(workdir)
        assert result.returncode == 0
        assert result.stdout.strip() == "created"
        auth = read_auth(workdir)
        assert auth["username"] == "galvani"
        assert auth["totp_required"] is False
        assert auth["totp_secret"] is None
        assert auth["session_days"] == 30
        assert len(auth["session_secret"]) == 64
        assert auth["session_cookie_secure"] is True
        mode = stat.S_IMODE((workdir / "data" / "auth.json").stat().st_mode)
        assert mode == 0o600

    def test_creds_line3_cookie_secure_false(self, workdir):
        write_creds(workdir, ["galvani", "s3cret-password", "cookie_secure:false"])
        result = run_bootstrap(workdir)
        assert result.returncode == 0
        assert read_auth(workdir)["session_cookie_secure"] is False

    def test_creds_line3_garbage_exit_1(self, workdir):
        write_creds(workdir, ["galvani", "s3cret-password", "bogus"])
        result = run_bootstrap(workdir)
        assert result.returncode == 1
        assert "cookie_secure" in result.stderr

    def test_existing_auth_json_not_overwritten(self, workdir):
        write_creds(workdir, ["galvani", "s3cret-password"])
        run_bootstrap(workdir)
        auth_file = workdir / "data" / "auth.json"
        auth_file.write_text(auth_file.read_text().replace('"galvani"', '"renamed"'))
        result = run_bootstrap(workdir)
        assert result.returncode == 0
        assert result.stdout.strip() == "exists"
        assert read_auth(workdir)["username"] == "renamed"

    def test_short_password_exit_1(self, workdir):
        write_creds(workdir, ["galvani", "short"])
        result = run_bootstrap(workdir)
        assert result.returncode == 1
        assert not (workdir / "data" / "auth.json").exists()

    def test_incomplete_creds_exit_1(self, workdir):
        write_creds(workdir, ["galvani"])
        result = run_bootstrap(workdir)
        assert result.returncode == 1
        assert not (workdir / "data" / "auth.json").exists()
