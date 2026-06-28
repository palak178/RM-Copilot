"""Ranking — order assessed candidates by a configurable Value x Propensity composite
(data-model §9.5). Deterministic.

Tie-break: propensity, then value, then tenure, then customer_id — so identical
inputs always produce identical order.
"""

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.assessment import Assessment, RankedCandidate


def rank(assessments: list[Assessment], config: ScoringConfig) -> list[RankedCandidate]:
    """Rank assessments by composite score (highest first)."""
    cfg = config.ranking
    candidates = [
        RankedCandidate(
            customer_id=a.customer_id,
            rank_score=cfg.value_weight * a.value.score
            + cfg.propensity_weight * a.propensity.score,
            assessment=a,
        )
        for a in assessments
    ]
    candidates.sort(
        key=lambda c: (
            -c.rank_score,
            -c.assessment.propensity.score,
            -c.assessment.value.score,
            -c.assessment.tenure_months,
            c.customer_id,
        )
    )
    return candidates
