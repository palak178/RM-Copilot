# scripts/

Operational entry points (thin wrappers over the package; no business logic of
their own).

Scripts:
- `seed_db.py` (M1, **implemented**) — build the deterministic synthetic SQLite
  dataset (`make seed`). Driven by `RM_COPILOT_DB_PATH` / `RM_COPILOT_SEED` /
  `RM_COPILOT_CUSTOMER_COUNT`.
- `demo.py` (M5) — scripted happy-path walkthrough of the 3 demo use cases for
  the video. _Not implemented yet._
