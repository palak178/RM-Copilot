"""Recommender and ranker."""

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.assessment import (
    Assessment,
    EligibilityResult,
    Recommendation,
    Score,
)
from rm_copilot.domain.enums import Confidence
from rm_copilot.services.propensity_scorer import score_propensity
from rm_copilot.services.ranker import rank
from rm_copilot.services.recommender import recommend


def test_recommends_requested_product_when_eligible(
    make_customer, make_features, products, scoring_config
) -> None:
    product = products["PROD_PERSONAL_LOAN"]
    features = make_features()
    propensity = score_propensity(features, (), product, scoring_config)
    elig = EligibilityResult(eligible=True)
    rec = recommend(make_customer(), features, product, elig, propensity, products.values())
    assert rec.recommended_product_id == "PROD_PERSONAL_LOAN"
    assert rec.fit_score == propensity.score
    assert rec.rationale


def test_declines_when_ineligible(make_customer, make_features, products, scoring_config) -> None:
    product = products["PROD_PERSONAL_LOAN"]
    propensity = score_propensity(make_features(), (), product, scoring_config)
    elig = EligibilityResult(eligible=False, failed_rules=("KYC not verified (PENDING)",))
    rec = recommend(make_customer(), make_features(), product, elig, propensity, products.values())
    assert rec.recommended_product_id is None
    assert rec.rationale == ("KYC not verified (PENDING)",)


def _assessment(cid: str, value: int, propensity: int, tenure: int = 60) -> Assessment:
    score = lambda s: Score(score=s, confidence=Confidence.HIGH, factors=())  # noqa: E731
    return Assessment(
        customer_id=cid,
        product_id="PROD_PERSONAL_LOAN",
        value=score(value),
        propensity=score(propensity),
        eligibility=EligibilityResult(eligible=True),
        recommendation=Recommendation(
            recommended_product_id="PROD_PERSONAL_LOAN", fit_score=propensity
        ),
        aum_paise=0,
        tenure_months=tenure,
        monthly_income_paise=0,
    )


def test_ranking_orders_by_composite(scoring_config: ScoringConfig) -> None:
    a = _assessment("CUST_A", value=90, propensity=40)
    b = _assessment("CUST_B", value=50, propensity=95)
    c = _assessment("CUST_C", value=20, propensity=20)
    ranked = rank([a, b, c], scoring_config)
    # propensity weighted 0.6 > value 0.4, so B should top A.
    assert [r.customer_id for r in ranked] == ["CUST_B", "CUST_A", "CUST_C"]
    assert ranked[0].rank_score >= ranked[1].rank_score >= ranked[2].rank_score


def test_ranking_is_deterministic_on_ties(scoring_config: ScoringConfig) -> None:
    a = _assessment("CUST_Z", value=50, propensity=50, tenure=10)
    b = _assessment("CUST_A", value=50, propensity=50, tenure=10)
    ranked = rank([a, b], scoring_config)
    assert [r.customer_id for r in ranked] == ["CUST_A", "CUST_Z"]  # tie-break by customer_id
