"""Data layer — persistence: SQLite connection, schema, repositories, seeding.

Owns the 6 durable tables + optional conversation_sessions (docs/data-model.md
§4) behind the repository pattern, plus the deterministic synthetic-data
generator (§5). Depends only on `domain` (and stdlib sqlite3 / Faker for seeding).

Rules:
- All access via repository interfaces; callers never see raw SQL.
- Parameterized queries only (no string interpolation into SQL).
- Transactions are append-only; money read/written as integer paise.

Implemented (M1): connection, schema, mappers, repositories, the product catalog,
the deterministic synthetic generator, and seed orchestration.
"""
