"""Run radtracker DB migrations (init_db) against the SQLite file.

Idempotent: ``CREATE TABLE IF NOT EXISTS`` and one-shot backfills guarded by
``user_settings`` flags. Invoked by the Ansible update/deploy playbooks so
schema migrations run on every deploy — independently of Streamlit, which only
runs ``app.py`` (and thus ``init_db``) when a browser session opens.

Usage (inside the radtracker container, WORKDIR=/app)::

    python -m src.migrate
"""

import sys

from src.db import SqliteConn, init_db, load_price_vigencies

DB_PATH = "/app/data/telerrad.db"


def main() -> int:
    conn = SqliteConn(DB_PATH)
    init_db(conn)
    vigs = load_price_vigencies(conn)
    print(f"init_db OK — {len(vigs)} price vigencies", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())