"""Services layer — deterministic business logic (the "logic" the rubric names).

Houses the value scorer, propensity scorer (incl. temporal triggers), eligibility
engine, recommender, ranker, compliance validator, and groundedness checker
(docs/data-model.md §6, §9). Config-driven via config/scoring.yaml.

Rules:
- 100% deterministic and unit-testable WITHOUT the LLM.
- Every score/recommendation emits reason codes (no opaque outputs).
- Depends only on `domain` (and `data` repositories via injected interfaces).
- No LLM calls here.

Implemented (M2): feature extraction, temporal triggers, value & propensity
scorers, eligibility, recommender, ranker, compliance + groundedness guardrails,
and the AssessmentService that composes them over the repositories.
"""
