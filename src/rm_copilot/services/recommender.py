"""Recommendation — recommend the product when suitable, decline with reasons when not
(data-model §9.2). Deterministic.

If eligible, recommends the requested product (fit = propensity) with rationale and
lists eligible cross-sell alternatives. If ineligible, declines and returns the
failed rules — never fabricates a recommendation.
"""

from collections.abc import Iterable

from rm_copilot.domain.assessment import EligibilityResult, Recommendation, Score
from rm_copilot.domain.entities import Customer, Product
from rm_copilot.domain.enums import KycStatus, ProductClass
from rm_copilot.services.features import CustomerFeatures

_CROSS_SELL_CLASSES = frozenset({ProductClass.LENDING, ProductClass.CARD})
_MAX_RATIONALE = 4


def recommend(
    customer: Customer,
    features: CustomerFeatures,
    product: Product,
    eligibility: EligibilityResult,
    propensity: Score,
    products: Iterable[Product],
) -> Recommendation:
    """Build a recommendation for the requested product."""
    if not eligibility.eligible:
        return Recommendation(
            recommended_product_id=None,
            fit_score=0,
            rationale=eligibility.failed_rules,
            alternatives=(),
        )

    rationale = propensity.reasons[:_MAX_RATIONALE]
    alternatives = tuple(
        p.product_id
        for p in products
        if p.product_id != product.product_id
        and p.product_class in _CROSS_SELL_CLASSES
        and p.product_id not in features.held_product_ids
        and _basic_eligible(customer, features, p)
    )
    return Recommendation(
        recommended_product_id=product.product_id,
        fit_score=propensity.score,
        rationale=rationale,
        alternatives=alternatives,
    )


def _basic_eligible(customer: Customer, features: CustomerFeatures, product: Product) -> bool:
    """Lightweight gate for ranking cross-sell alternatives (age/KYC/income/delinquency)."""
    if not (product.min_age <= customer.age <= product.max_age):
        return False
    if product.requires_kyc and customer.kyc_status != KycStatus.VERIFIED:
        return False
    if features.monthly_income_paise < product.min_monthly_income_paise:
        return False
    return features.max_dpd == 0
