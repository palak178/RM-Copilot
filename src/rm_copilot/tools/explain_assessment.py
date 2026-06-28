"""explain_assessment — full factor/trigger breakdown for one (customer, product).

Deterministic. Wraps AssessmentService.assess and exposes the reason-coded value
and propensity factors, eligibility, and recommendation (the "why").
"""

from pydantic import BaseModel

from rm_copilot.domain.assessment import Assessment, Score
from rm_copilot.services.assessment import AssessmentService
from rm_copilot.tools.base import Tool


class ExplainInput(BaseModel):
    customer_id: str
    product_id: str


class FactorOut(BaseModel):
    key: str
    reason: str
    contribution: float
    weight: float
    normalized: float


class TriggerOut(BaseModel):
    key: str
    reason: str
    boost: int


class ScoreOut(BaseModel):
    score: int
    confidence: str
    factors: list[FactorOut]
    triggers: list[TriggerOut] = []


class EligibilityOut(BaseModel):
    eligible: bool
    failed_rules: list[str]


class RecommendationOut(BaseModel):
    recommended_product_id: str | None
    fit_score: int
    rationale: list[str]
    alternatives: list[str]


class ExplainOutput(BaseModel):
    customer_id: str
    product_id: str
    value: ScoreOut
    propensity: ScoreOut
    eligibility: EligibilityOut
    recommendation: RecommendationOut
    aum_paise: int
    tenure_months: int
    monthly_income_paise: int


def _score_out(score: Score) -> ScoreOut:
    return ScoreOut(
        score=score.score,
        confidence=score.confidence.value,
        factors=[
            FactorOut(
                key=f.key,
                reason=f.reason,
                contribution=round(f.contribution, 2),
                weight=f.weight,
                normalized=round(f.normalized, 3),
            )
            for f in score.factors
        ],
        triggers=[TriggerOut(key=t.key, reason=t.reason, boost=t.boost) for t in score.triggers],
    )


class ExplainAssessmentTool(Tool):
    name = "explain_assessment"
    description = (
        "Explain why a specific customer is (or isn't) a fit for a product: the value and "
        "propensity factor breakdown with reason codes, temporal triggers, eligibility, and "
        "the recommendation."
    )
    input_model = ExplainInput

    def __init__(self, service: AssessmentService) -> None:
        self._service = service

    def execute(self, args: ExplainInput) -> ExplainOutput:
        a: Assessment = self._service.assess(args.customer_id, args.product_id)
        return ExplainOutput(
            customer_id=a.customer_id,
            product_id=a.product_id,
            value=_score_out(a.value),
            propensity=_score_out(a.propensity),
            eligibility=EligibilityOut(
                eligible=a.eligibility.eligible, failed_rules=list(a.eligibility.failed_rules)
            ),
            recommendation=RecommendationOut(
                recommended_product_id=a.recommendation.recommended_product_id,
                fit_score=a.recommendation.fit_score,
                rationale=list(a.recommendation.rationale),
                alternatives=list(a.recommendation.alternatives),
            ),
            aum_paise=a.aum_paise,
            tenure_months=a.tenure_months,
            monthly_income_paise=a.monthly_income_paise,
        )
