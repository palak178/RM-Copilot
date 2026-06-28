"""SQLite connection factory.

Centralizes connection setup: row access by name and enforced foreign keys.
The only place that opens a database connection.
"""

import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with project conventions applied.

    Use ``":memory:"`` for ephemeral databases (tests).

    ``check_same_thread=False`` lets the API server share one connection across its
    worker/SSE threads (reads dominate; the only writes are short, serialized audit-log
    inserts). A production deployment would use a per-request connection or a pool.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
