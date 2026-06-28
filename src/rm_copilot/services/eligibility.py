"""Eligibility — hard product gates (data-model §9.1). Deterministic, reason-coded.

A failing gate never silently drops a customer; the specific failed rule(s) are
returned for transparency.
"""

from rm_copilot.domain.assessment import EligibilityResult
from rm_copilot.domain.entities import Customer, Product
from rm_copilot.domain.enums import KycStatus, ProductClass
from rm_copilot.domain.money import format_inr
from rm_copilot.services.features import UNSECURED_TYPES, CustomerFeatures

_NEW_CREDIT_CLASSES = frozenset({ProductClass.LENDING, ProductClass.CARD})


def check_eligibility(
    customer: Customer, features: CustomerFeatures, product: Product
) -> EligibilityResult:
    """Evaluate whether the customer passes the product's hard gates."""
    failed: list[str] = []

    if not (product.min_age <= customer.age <= product.max_age):
        failed.append(f"age {customer.age} outside [{product.min_age}, {product.max_age}]")

    if product.requires_kyc and customer.kyc_status != KycStatus.VERIFIED:
        failed.append(f"KYC not verified ({customer.kyc_status.value})")

    if features.monthly_income_paise < product.min_monthly_income_paise:
        failed.append(
            f"income {format_inr(features.monthly_income_paise)}/mo below minimum "
            f"{format_inr(product.min_monthly_income_paise)}/mo"
        )

    if product.product_id in features.held_product_ids:
        failed.append("already holds this product")

    # New credit (loans/cards) hard gates: no delinquency, fraud flag, or recent default.
    if product.product_class in _NEW_CREDIT_CLASSES:
        if features.max_dpd > 0:
            failed.append(f"active delinquency (DPD {features.max_dpd})")
        if features.fraud_flag:
            failed.append("active fraud flag")
        if features.has_recent_default:
            failed.append("recent default (< 6 months)")

    # Unsecured products cap the number of active unsecured facilities.
    if (
        product.product_type in UNSECURED_TYPES
        and product.max_active_unsecured_loans is not None
        and features.active_unsecured_count >= product.max_active_unsecured_loans
    ):
        failed.append(
            f"{features.active_unsecured_count} active unsecured facilities "
            f"(max {product.max_active_unsecured_loans})"
        )

    return EligibilityResult(eligible=not failed, failed_rules=tuple(failed))
