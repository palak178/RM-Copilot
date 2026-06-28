"""Observability layer — cross-cutting: structured logging, audit, execution trace.

Owns the ExecutionEvent model and the per-turn timeline/tool-trace/metrics that
the UI renders (assessment-plan.md §16), plus PII masking for logs.

Rules:
- Stdlib logging with a JSON formatter by default (no extra runtime dependency).
- Mask PII in logs (first-name/token only; never full PAN/account numbers).
- Surface tool decisions, guardrail outcomes, tokens/cost/latency — and only
  SUMMARIZED thinking, never raw chain-of-thought.
- The durable audit record lives in the data layer (outreach_log); this layer
  formats and emits, it does not own business persistence.

Implemented across M4/M5. Intentionally empty for now.
"""
