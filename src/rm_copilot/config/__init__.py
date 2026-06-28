"""Config layer — typed settings loading (pydantic-settings) and scoring config access.

Loads environment settings (prefix RM_COPILOT_, see ../../.env.example) and parses
config/scoring.yaml (factors, weights, thresholds, confidence, reason-code
templates, trigger rules — designed in docs/data-model.md §6).

Rules:
- Secrets come from the environment only; never hardcoded or committed.
- Scoring behaviour is config-driven so factors/weights change without code edits.

Implemented (M1): typed environment Settings. (M2): typed scoring.yaml loader.
"""
