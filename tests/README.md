# tests/

- `unit/` — one+ test per service and tool; edge cases (no transactions, ties,
  ineligible, empty set, fabricated number rejected by groundedness).
- `integration/` — golden-path end-to-end (mocked LLM, real SQLite). Mark with
  `@pytest.mark.integration`.
- `fixtures/` — small static datasets / expected snapshots.

The LLM is always mocked in tests — no network, no token spend. See `conftest.py`.
