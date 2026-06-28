"""Derived value objects — the output of the deterministic services (data-model §2.8).

These are computed on demand and never persisted as authoritative rows (only an
assessment snapshot is logged for audit). Pure data; no I/O.
"""

from dataclasses import dataclass, field

from rm_copilot.domain.enums import Confidence


@dataclass(frozen=True, slots=True)
class FactorContribution:
    """One factor's contribution to a score, with a human-readable reason."""

    key: str
    detail: str
    weight: float
    normalized: float  # 0..1
    contribution: float  # points contributed to the 0..100 score
    reason: str


@dataclass(frozen=True, slots=True)
class Trigger:
    """A detected time-bound event that raises propensity 'this month'."""

    key: str
    detail: str
    boost: int
    reason: str


@dataclass(frozen=True, slots=True)
class Score:
    """A 0..100 score with its factor breakdown, confidence, and (optional) triggers."""

    score: int
    confidence: Confidence
    factors: tuple[FactorContribution, ...]
    triggers: tuple[Trigger, ...] = ()

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(f.reason for f in self.factors) + tuple(t.reason for t in self.triggers)


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """Whether a customer passes a product's hard gates, with any failed rules."""

    eligible: bool
    failed_rules: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A product recommendation (or a decline) with rationale and alternatives."""

    recommended_product_id: str | None
    fit_score: int
    rationale: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Assessment:
    """Full assessment of one customer for one product."""

    customer_id: str
    product_id: str
    value: Score
    propensity: Score
    eligibility: EligibilityResult
    recommendation: Recommendation
    aum_paise: int
    tenure_months: int
    monthly_income_paise: int

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return self.value.reasons + self.propensity.reasons


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """An assessed customer with its composite ranking score."""

    customer_id: str
    rank_score: float
    assessment: Assessment


@dataclass(frozen=True, slots=True)
class ComplianceResult:
    """Outcome of the deterministic compliance guardrail."""

    passed: bool
    violations: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class GroundednessResult:
    """Outcome of the deterministic groundedness check on a drafted message."""

    grounded: bool
    unsupported_claims: tuple[str, ...] = field(default=())
