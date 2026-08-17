"""App-level regression test: saving production data must not reset the active tab.

The Salvar button used to call st.rerun() from the sidebar, aborting the run
before the tab radio rendered. Streamlit deletes the state of any widget not
rendered in a run, so the radio fell back to index=0 (Hoje). The button click
itself already triggers a full rerun, so the explicit st.rerun() is redundant.

Runs the real app.py under AppTest in a temp cwd with a scratch DB + auth.
Two Streamlit internals cannot work under AppTest and are stubbed:
- CCv2 cookie components (no component server) — reader returns no snapshot,
  the cold-cookie scenario from the bug report.
- st.connection is replaced by the project's SqliteConn: SQLConnection.query
  leaks pooled connections (never closes after pd.read_sql), and on Python
  3.13 the gate's st.stop() pins the run frames via its traceback, so the
  pool exhausts and the next run deadlocks. SqliteConn closes every time.
"""

import shutil
from datetime import date
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import src.cookies as cookies
from src.auth_store import create_bootstrap_auth
from src.db import SqliteConn, load_daily_items

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _StubReaderResult:
    snapshot_json = None


def _fake_st_connection(tmp_path: Path):
    db_path = str(tmp_path / "data" / "telerrad.db")
    return lambda *args, **kwargs: SqliteConn(db_path)


@pytest.fixture
def app_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.chdir(tmp_path)
    # app.py opens pyproject.toml relative to cwd (sidebar version caption)
    shutil.copyfile(PROJECT_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "data").mkdir()
    create_bootstrap_auth("dev", "dev-password-123", "data/auth.json", cookie_secure=False)
    monkeypatch.setattr(cookies, "_COOKIE_READER", lambda **kwargs: _StubReaderResult())
    monkeypatch.setattr(cookies, "_COOKIE_WRITER", lambda **kwargs: None)
    monkeypatch.setattr(st, "connection", _fake_st_connection(tmp_path))
    return AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30)


def test_salvar_keeps_active_tab(app_test: AppTest, tmp_path: Path) -> None:
    app_test.run()
    # authenticate by seeding the gate state directly (cookie restore is stubbed)
    app_test.session_state["auth_authenticated"] = True
    app_test.session_state["auth_username"] = "dev"
    app_test.session_state["lang"] = "en"
    app_test.run()

    assert app_test.radio(key="main_tabs").value.startswith(":material/today:")

    # switch to the Analysis tab, then save today's production from the sidebar
    app_test.radio(key="main_tabs").set_value(":material/trending_up: Analysis")
    app_test.run()
    assert app_test.radio(key="main_tabs").value.startswith(":material/trending_up:")

    first_slug = app_test.session_state["active_modalities"][0]["slug"]
    today = date.today().isoformat()
    app_test.sidebar.number_input(key=f"sidebar_{first_slug}_{today}").set_value(7)

    save_btns = [b for b in app_test.sidebar.button if b.label == "Save"]
    assert save_btns, f"Save button not found: {[b.label for b in app_test.sidebar.button]}"
    save_btns[0].click()
    app_test.run()

    # regression: the active tab must survive the save
    assert app_test.radio(key="main_tabs").value.startswith(":material/trending_up:")

    # the save itself still persists without the old st.rerun()
    assert app_test.toast, "save toast not shown"
    conn = SqliteConn(str(tmp_path / "data" / "telerrad.db"))
    assert load_daily_items(conn, today) == {first_slug: 7}
