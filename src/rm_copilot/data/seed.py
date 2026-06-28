"""Seed orchestration — build a dataset and load it into the database.

Idempotent: creates the schema, clears existing rows, then inserts a freshly
generated deterministic dataset in a single transaction.
"""

from datetime import date

from rm_copilot.data.database import Database
from rm_copilot.data.synthetic import generate_dataset


def seed_database(
    db: Database, *, seed: int, customer_count: int, as_of: date | None = None
) -> dict[str, int]:
    """Populate ``db`` with a reproducible synthetic dataset. Returns row counts."""
    db.create_schema()
    db.clear_all()
    dataset = generate_dataset(seed=seed, customer_count=customer_count, as_of=as_of)
    with db.transaction():
        db.products.add_many(dataset.products)
        db.customers.add_many(dataset.customers)
        db.holdings.add_many(dataset.holdings)
        db.transactions.add_many(dataset.transactions)
        db.interactions.add_many(dataset.interactions)
    return {
        "products": len(dataset.products),
        "customers": len(dataset.customers),
        "holdings": len(dataset.holdings),
        "transactions": len(dataset.transactions),
        "interactions": len(dataset.interactions),
    }
