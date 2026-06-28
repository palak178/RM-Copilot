"""Build the deterministic synthetic SQLite dataset (milestone M1).

Usage:  python scripts/seed_db.py   (or: make seed)
Controlled by RM_COPILOT_DB_PATH / RM_COPILOT_SEED / RM_COPILOT_CUSTOMER_COUNT.
"""

from pathlib import Path

from rm_copilot.config.settings import get_settings
from rm_copilot.data.database import Database
from rm_copilot.data.seed import seed_database


def main() -> None:
    settings = get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    db = Database.connect(settings.db_path)
    try:
        counts = seed_database(db, seed=settings.seed, customer_count=settings.customer_count)
    finally:
        db.close()
    print(f"Seeded {settings.db_path} (seed={settings.seed}):")
    for name, n in counts.items():
        print(f"  {name:14s} {n}")


if __name__ == "__main__":
    main()
