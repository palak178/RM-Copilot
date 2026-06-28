"""End-to-end seeding against a real file-backed SQLite database."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from rm_copilot.data.database import Database
from rm_copilot.data.seed import seed_database

AS_OF = date(2026, 6, 15)


@pytest.mark.integration
def test_seed_persists_and_signals_queryable(tmp_path: Path) -> None:
    db_path = tmp_path / "rm.db"
    db = Database.connect(str(db_path))
    counts = seed_database(db, seed=42, customer_count=40, as_of=AS_OF)
    assert counts["customers"] == 40
    assert counts["products"] == 8
    assert counts["transactions"] > 0

    maturing = db.holdings.find_fd_maturing_between(date(2026, 6, 1), date(2026, 6, 30))
    assert any(h.customer_id == "CUST000001" for h in maturing)
    ending = db.holdings.find_loans_ending_between(AS_OF, AS_OF + timedelta(days=30))
    assert any(h.customer_id == "CUST000001" for h in ending)
    db.close()

    # Data persisted on disk: reopen and confirm.
    reopened = Database.connect(str(db_path))
    assert reopened.customers.count() == 40
    reopened.close()


@pytest.mark.integration
def test_reseed_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "rm.db"
    db = Database.connect(str(db_path))
    first = seed_database(db, seed=42, customer_count=30, as_of=AS_OF)
    second = seed_database(db, seed=42, customer_count=30, as_of=AS_OF)
    assert first == second
    assert db.customers.count() == 30  # cleared, not duplicated
    db.close()
