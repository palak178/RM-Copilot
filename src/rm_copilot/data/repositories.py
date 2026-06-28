"""Repositories — the only gateway to persisted data.

Callers never see raw SQL. All statements are parameterized (named params). For
milestone M1 these cover seeding (`add_many`), reads (`get` / `list_for_customer`),
and the signal queries that prove docs/data-model.md §5 signals are queryable and
that milestone M2's scoring will build on.

Transactions are append-only: no update/delete methods are exposed.
"""

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime

from rm_copilot.data import mappers
from rm_copilot.domain.entities import (
    Customer,
    Interaction,
    OutreachLog,
    Product,
    ProductHolding,
    Transaction,
)


def _insert_sql(table: str, columns: Iterable[str]) -> str:
    cols = list(columns)
    names = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    return f"INSERT INTO {table} ({names}) VALUES ({placeholders})"


class CustomerRepository:
    """Read/seed access to customers."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add_many(self, customers: Sequence[Customer]) -> None:
        rows = [mappers.customer_to_params(c) for c in customers]
        if rows:
            self._conn.executemany(_insert_sql("customers", rows[0].keys()), rows)

    def get(self, customer_id: str) -> Customer | None:
        row = self._conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        return mappers.row_to_customer(row) if row else None

    def list_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT customer_id FROM customers ORDER BY customer_id"
        ).fetchall()
        return [r["customer_id"] for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]


class ProductRepository:
    """Read/seed access to the product catalog."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add_many(self, products: Sequence[Product]) -> None:
        rows = [mappers.product_to_params(p) for p in products]
        if rows:
            self._conn.executemany(_insert_sql("products", rows[0].keys()), rows)

    def get(self, product_id: str) -> Product | None:
        row = self._conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        return mappers.row_to_product(row) if row else None

    def list_active(self) -> list[Product]:
        rows = self._conn.execute(
            "SELECT * FROM products WHERE is_active = 1 ORDER BY product_id"
        ).fetchall()
        return [mappers.row_to_product(r) for r in rows]


class ProductHoldingRepository:
    """Read/seed access to holdings, including date-windowed signal queries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add_many(self, holdings: Sequence[ProductHolding]) -> None:
        rows = [mappers.holding_to_params(h) for h in holdings]
        if rows:
            self._conn.executemany(_insert_sql("product_holdings", rows[0].keys()), rows)

    def list_for_customer(self, customer_id: str) -> list[ProductHolding]:
        rows = self._conn.execute(
            "SELECT * FROM product_holdings WHERE customer_id = ? ORDER BY holding_id",
            (customer_id,),
        ).fetchall()
        return [mappers.row_to_holding(r) for r in rows]

    def find_fd_maturing_between(self, start: date, end: date) -> list[ProductHolding]:
        """Active FD/RD holdings maturing within [start, end] — the FD-maturing trigger."""
        rows = self._conn.execute(
            """
            SELECT h.* FROM product_holdings h
            JOIN products p ON h.product_id = p.product_id
            WHERE p.product_type IN ('FD', 'RD')
              AND h.status = 'ACTIVE'
              AND h.maturity_date IS NOT NULL
              AND h.maturity_date BETWEEN ? AND ?
            ORDER BY h.maturity_date
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [mappers.row_to_holding(r) for r in rows]

    def find_loans_ending_between(self, start: date, end: date) -> list[ProductHolding]:
        """Active loans whose final EMI falls within [start, end] — the EMI-ending trigger."""
        rows = self._conn.execute(
            """
            SELECT * FROM product_holdings
            WHERE status = 'ACTIVE'
              AND loan_end_date IS NOT NULL
              AND loan_end_date BETWEEN ? AND ?
            ORDER BY loan_end_date
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [mappers.row_to_holding(r) for r in rows]


class TransactionRepository:
    """Read/seed access to the append-only transaction ledger."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add_many(self, transactions: Sequence[Transaction]) -> None:
        rows = [mappers.transaction_to_params(t) for t in transactions]
        if rows:
            self._conn.executemany(_insert_sql("transactions", rows[0].keys()), rows)

    def list_for_customer(
        self, customer_id: str, since: datetime | None = None
    ) -> list[Transaction]:
        if since is None:
            rows = self._conn.execute(
                "SELECT * FROM transactions WHERE customer_id = ? ORDER BY txn_ts",
                (customer_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM transactions WHERE customer_id = ? AND txn_ts >= ? ORDER BY txn_ts",
                (customer_id, since.isoformat()),
            ).fetchall()
        return [mappers.row_to_transaction(r) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"]


class InteractionRepository:
    """Read/seed access to interaction history."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add_many(self, interactions: Sequence[Interaction]) -> None:
        rows = [mappers.interaction_to_params(i) for i in interactions]
        if rows:
            self._conn.executemany(_insert_sql("interactions", rows[0].keys()), rows)

    def list_for_customer(self, customer_id: str) -> list[Interaction]:
        rows = self._conn.execute(
            "SELECT * FROM interactions WHERE customer_id = ? ORDER BY interaction_ts",
            (customer_id,),
        ).fetchall()
        return [mappers.row_to_interaction(r) for r in rows]


class OutreachLogRepository:
    """Write/read access to the outreach audit log (the dry-run 'send')."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, record: OutreachLog) -> None:
        params = mappers.outreach_to_params(record)
        self._conn.execute(_insert_sql("outreach_log", params.keys()), params)

    def get(self, outreach_id: str) -> OutreachLog | None:
        row = self._conn.execute(
            "SELECT * FROM outreach_log WHERE outreach_id = ?", (outreach_id,)
        ).fetchone()
        return mappers.row_to_outreach(row) if row else None

    def list_for_customer(self, customer_id: str) -> list[OutreachLog]:
        rows = self._conn.execute(
            "SELECT * FROM outreach_log WHERE customer_id = ? ORDER BY created_at",
            (customer_id,),
        ).fetchall()
        return [mappers.row_to_outreach(r) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS n FROM outreach_log").fetchone()["n"]
