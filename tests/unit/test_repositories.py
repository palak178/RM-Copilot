"""Repository reads, signal queries, FK enforcement, CHECK constraints, append-only."""

import sqlite3
from datetime import date, datetime

import pytest

from rm_copilot.data.database import Database
from rm_copilot.domain.entities import ProductHolding, Transaction
from rm_copilot.domain.enums import HoldingStatus, Segment, TxnCategory, TxnChannel, TxnDirection

AS_OF = date(2026, 6, 15)
NOW = datetime(2026, 6, 15, 0, 0, 0)


def test_get_returns_typed_customer(seeded_db: Database) -> None:
    ids = seeded_db.customers.list_ids()
    assert ids
    customer = seeded_db.customers.get(ids[0])
    assert customer is not None
    assert customer.customer_id == ids[0]
    assert isinstance(customer.segment, Segment)
    assert isinstance(customer.dob, date)
    assert isinstance(customer.created_at, datetime)


def test_get_unknown_customer_returns_none(seeded_db: Database) -> None:
    assert seeded_db.customers.get("CUST999999") is None


def test_count_matches_seed(seeded_db: Database) -> None:
    assert seeded_db.customers.count() == 20


def test_transactions_for_customer(seeded_db: Database) -> None:
    txns = seeded_db.transactions.list_for_customer("CUST000001")
    assert txns
    assert all(t.customer_id == "CUST000001" for t in txns)
    assert all(t.amount_paise > 0 for t in txns)


def test_fd_maturing_query_finds_hero(seeded_db: Database) -> None:
    maturing = seeded_db.holdings.find_fd_maturing_between(date(2026, 6, 1), date(2026, 6, 30))
    assert maturing
    assert any(h.customer_id == "CUST000001" for h in maturing)


def test_loans_ending_query_finds_hero(seeded_db: Database) -> None:
    from datetime import timedelta

    ending = seeded_db.holdings.find_loans_ending_between(AS_OF, AS_OF + timedelta(days=30))
    assert any(h.customer_id == "CUST000001" for h in ending)


def test_foreign_key_enforced(seeded_db: Database) -> None:
    orphan = ProductHolding(
        holding_id="HOLD99999999",
        customer_id="CUST_DOES_NOT_EXIST",
        product_id="PROD_SAVINGS",
        status=HoldingStatus.ACTIVE,
        opened_date=AS_OF,
        created_at=NOW,
        updated_at=NOW,
        current_balance_paise=1000,
    )
    with pytest.raises(sqlite3.IntegrityError), seeded_db.transaction():
        seeded_db.holdings.add_many([orphan])


def test_amount_check_constraint(seeded_db: Database) -> None:
    bad = Transaction(
        transaction_id="TXN_BAD",
        customer_id="CUST000001",
        txn_ts=NOW,
        amount_paise=0,  # violates CHECK (amount_paise > 0)
        direction=TxnDirection.DEBIT,
        category=TxnCategory.OTHER,
        channel=TxnChannel.UPI,
        created_at=NOW,
    )
    with pytest.raises(sqlite3.IntegrityError), seeded_db.transaction():
        seeded_db.transactions.add_many([bad])


def test_transaction_repository_is_append_only(seeded_db: Database) -> None:
    repo = seeded_db.transactions
    assert not hasattr(repo, "update")
    assert not hasattr(repo, "delete")
