"""Run radtracker DB migrations (init_db) against the SQLite file.

Idempotent: ``CREATE TABLE IF NOT EXISTS`` and one-shot backfills guarded by
``user_settings`` flags. Invoked by the Ansible update/deploy playbooks so
schema migrations run on every deploy — independently of Streamlit, which only
runs ``app.py`` (and thus ``init_db``) when a browser session opens.

Usage (inside the radtracker container, WORKDIR=/app)::

    python -m src.migrate
"""

import sys

import pandas as pd
import sqlalchemy as sa

from src.db import init_db, load_price_vigencies

DB_PATH = "/app/data/telerrad.db"


class _FileConn:
    """Minimal conn emulating st.connection('telerrad'): .connect() + .query()."""

    def __init__(self, path: str = DB_PATH) -> None:
        self._engine = sa.create_engine(f"sqlite:///{path}")

    def connect(self):
        return self._engine.connect()

    def query(self, sql: str, *, params: dict | None = None, ttl: int = 0) -> pd.DataFrame:
        with self._engine.connect() as c:
            result = c.execute(sa.text(sql), params or {})
            return pd.DataFrame(result.fetchall(), columns=result.keys())


def main() -> int:
    conn = _FileConn()
    init_db(conn)
    vigs = load_price_vigencies(conn)
    print(f"init_db OK — {len(vigs)} price vigencies", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())