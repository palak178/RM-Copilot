"""End-to-end analytics over the seeded database — the M2 acceptance criterion.

Runs the full scoring pipeline WITHOUT the agent and asserts reason-coded output.
"""

from datetime import date

import pytest

from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.data.database import Database
from rm_copilot.services.assessment import (
    AssessmentService,
    CustomerNotFoundError,
    ProductNotFoundError,
)

# Must match the seeded_db fixture's as_of so "this month" triggers line up.
AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"


def _service(db: Database) -> AssessmentService:
    return AssessmentService(db, load_scoring_config(), as_of=AS_OF)


@pytest.mark.integration
def test_hero_is_high_value_eligible_and_triggered(seeded_db: Database) -> None:
    a = _service(seeded_db).assess("CUST000001", PERSONAL_LOAN)
    assert a.eligibility.eligible
    assert a.value.score > 50
    assert a.propensity.triggers  # FD maturing / EMI ending / large outflow
    assert a.reason_codes  # fully reason-coded, no hardcoding
    assert a.recommendation.recommended_product_id == PERSONAL_LOAN


@pytest.mark.integration
def test_ineligible_customer_is_declined(seeded_db: Database) -> None:
    a = _service(seeded_db).assess("CUST000005", PERSONAL_LOAN)
    assert not a.eligibility.eligible
    assert a.recommendation.recommended_product_id is None
    assert a.recommendation.rationale  # explains why


@pytest.mark.integration
def test_rank_prospects_surfaces_hero(seeded_db: Database) -> None:
    ranked = _service(seeded_db).rank_prospects(PERSONAL_LOAN, top_n=5)
    assert ranked
    assert all(r.assessment.eligibility.eligible for r in ranked)
    assert "CUST000001" in {r.customer_id for r in ranked}
    scores = [r.rank_score for r in ranked]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.integration
def test_unknown_lookups_raise(seeded_db: Database) -> None:
    service = _service(seeded_db)
    with pytest.raises(CustomerNotFoundError):
        service.assess("CUST999999", PERSONAL_LOAN)
    with pytest.raises(ProductNotFoundError):
        service.assess("CUST000001", "PROD_NOPE")
