"""find_and_rank_prospects — the coarse hot-path tool (assessment-plan.md §14).

Deterministic. Wraps AssessmentService.rank_prospects and returns reason-coded,
ranked prospects for a product.
"""

from pydantic import BaseModel, Field

from rm_copilot.data.database import Database
from rm_copilot.services.assessment import AssessmentService
from rm_copilot.tools.base import Tool


class FindProspectsInput(BaseModel):
    product_id: str = Field(description="Catalog product id, e.g. PROD_PERSONAL_LOAN")
    top_n: int = Field(default=10, ge=1, le=50, description="Number of prospects to return")
    eligible_only: bool = Field(default=True, description="Exclude customers failing eligibility")


class ProspectSummary(BaseModel):
    customer_id: str
    first_name: str
    city: str
    rank_score: float
    value_score: int
    propensity_score: int
    confidence: str
    recommended_product_id: str | None
    triggers: list[str]
    reason_codes: list[str]


class FindProspectsOutput(BaseModel):
    product_id: str
    count: int
    prospects: list[ProspectSummary]


class FindAndRankProspectsTool(Tool):
    name = "find_and_rank_prospects"
    description = (
        "Find and rank existing customers most likely to convert for a given product now. "
        "Returns the top-N ranked prospects with value and propensity scores, the temporal "
        "triggers driving conversion this month, and reason codes explaining each."
    )
    input_model = FindProspectsInput

    def __init__(self, db: Database, service: AssessmentService) -> None:
        self._db = db
        self._service = service

    def execute(self, args: FindProspectsInput) -> FindProspectsOutput:
        ranked = self._service.rank_prospects(
            args.product_id, top_n=args.top_n, eligible_only=args.eligible_only
        )
        prospects = []
        for r in ranked:
            a = r.assessment
            customer = self._db.customers.get(r.customer_id)
            prospects.append(
                ProspectSummary(
                    customer_id=r.customer_id,
                    first_name=customer.first_name if customer else "",
                    city=customer.city if customer else "",
                    rank_score=round(r.rank_score, 1),
                    value_score=a.value.score,
                    propensity_score=a.propensity.score,
                    confidence=a.propensity.confidence.value,
                    recommended_product_id=a.recommendation.recommended_product_id,
                    triggers=[t.key for t in a.propensity.triggers],
                    reason_codes=list(a.reason_codes),
                )
            )
        return FindProspectsOutput(
            product_id=args.product_id, count=len(prospects), prospects=prospects
        )
