"""Schema creation, foreign keys, and indexes."""

from rm_copilot.data.connection import connect
from rm_copilot.data.schema import TABLE_ORDER, create_schema


def test_creates_all_durable_tables() -> None:
    conn = connect(":memory:")
    create_schema(conn)
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(TABLE_ORDER).issubset(names)


def test_foreign_keys_enabled() -> None:
    conn = connect(":memory:")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_key_indexes_exist() -> None:
    conn = connect(":memory:")
    create_schema(conn)
    idx = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_txn_customer_ts" in idx
    assert "idx_holdings_maturity" in idx
    assert "idx_holdings_loanend" in idx
