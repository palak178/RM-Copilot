"""Database facade — single entry point to persistence.

Owns one connection, exposes the repositories, and controls schema lifecycle and
transactions. Keeps connection management in one place so callers work with
repositories and a `transaction()` context manager rather than raw SQLite.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rm_copilot.data import schema
from rm_copilot.data.connection import connect
from rm_copilot.data.repositories import (
    CustomerRepository,
    InteractionRepository,
    OutreachLogRepository,
    ProductHoldingRepository,
    ProductRepository,
    TransactionRepository,
)


class Database:
    """Holds a connection and the repository set."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.customers = CustomerRepository(conn)
        self.products = ProductRepository(conn)
        self.holdings = ProductHoldingRepository(conn)
        self.transactions = TransactionRepository(conn)
        self.interactions = InteractionRepository(conn)
        self.outreach = OutreachLogRepository(conn)

    @classmethod
    def connect(cls, db_path: str | Path) -> "Database":
        return cls(connect(db_path))

    def create_schema(self) -> None:
        """Create all tables/indexes if absent, and commit."""
        schema.create_schema(self._conn)
        self._conn.commit()

    def clear_all(self) -> None:
        with self.transaction():
            schema.clear_all(self._conn)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a unit of work; commit on success, roll back on error."""
        with self._conn:
            yield self._conn

    def close(self) -> None:
        self._conn.close()
