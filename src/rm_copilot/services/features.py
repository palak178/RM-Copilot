"""Behavioral feature extraction — shared inputs for scoring and eligibility.

Computes a customer's features once from holdings + transactions, so value,
propensity, and eligibility do not duplicate aggregation logic. Pure: operates on
domain objects, no I/O.
"""

import statistics
from dataclasses import dataclass
from datetime import date, datetime

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.entities import Customer, Product, ProductHolding, Transaction
from rm_copilot.domain.enums import (
    Confidence,
    HoldingStatus,
    ProductClass,
    ProductType,
    TxnCategory,
    TxnDirection,
)

UNSECURED_TYPES = frozenset({ProductType.PERSONAL_LOAN, ProductType.CREDIT_CARD})
_SALARY_LOOKBACK_MONTHS = 6
_RECENT_DEFAULT_DAYS = 180


@dataclass(frozen=True, slots=True)
class CustomerFeatures:
    """Numeric/behavioral features derived from a customer's holdings + transactions."""

    customer_id: str
    age: int
    aum_paise: int
    product_depth: int
    tenure_months: int
    monthly_income_paise: int
    existing_emi_paise: int
    card_utilization: float  # 0..1 (0 if no card)
    max_dpd: int
    active_unsecured_count: int
    has_salary_signal: bool
    transaction_count: int
    held_product_ids: frozenset[str]
    confidence: Confidence
    fraud_flag: bool
    has_recent_default: bool


def _months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def _monthly_income_paise(
    customer: Customer, transactions: list[Transaction], as_of: date
) -> tuple[int, bool]:
    """Median monthly salary credit; fall back to declared income. Returns (paise, has_salary)."""
    cutoff = datetime.combine(as_of, datetime.min.time())
    salary = [
        t.amount_paise
        for t in transactions
        if t.category == TxnCategory.SALARY
        and t.direction == TxnDirection.CREDIT
        and _months_between(t.txn_ts.date(), as_of) < _SALARY_LOOKBACK_MONTHS
        and t.txn_ts <= cutoff
    ]
    if salary:
        return int(statistics.median(salary)), True
    if customer.declared_annual_income_paise:
        return customer.declared_annual_income_paise // 12, False
    return 0, False


def extract_features(
    customer: Customer,
    holdings: list[ProductHolding],
    transactions: list[Transaction],
    products: dict[str, Product],
    as_of: date,
    config: ScoringConfig,
) -> CustomerFeatures:
    """Compute the feature vector for one customer."""
    active = [h for h in holdings if h.status == HoldingStatus.ACTIVE]

    aum = 0
    existing_emi = 0
    max_dpd = 0
    utilization = 0.0
    unsecured = 0
    held: set[str] = set()
    for h in active:
        held.add(h.product_id)
        product = products.get(h.product_id)
        pclass = product.product_class if product else None
        ptype = product.product_type if product else None
        if pclass == ProductClass.DEPOSIT:
            aum += (h.current_balance_paise or 0) + (h.principal_paise or 0)
        if h.emi_amount_paise:
            existing_emi += h.emi_amount_paise
        if h.dpd:
            max_dpd = max(max_dpd, h.dpd)
        if h.credit_limit_paise:
            utilization = max(
                utilization, (h.current_outstanding_paise or 0) / h.credit_limit_paise
            )
        if ptype in UNSECURED_TYPES:
            unsecured += 1

    income, has_salary = _monthly_income_paise(customer, transactions, as_of)
    txn_count = len(transactions)
    confidence = _confidence(txn_count, has_salary, config)
    recent_default = bool(
        customer.last_default_date
        and 0 <= (as_of - customer.last_default_date).days <= _RECENT_DEFAULT_DAYS
    )

    return CustomerFeatures(
        customer_id=customer.customer_id,
        age=customer.age,
        aum_paise=aum,
        product_depth=len(held),
        tenure_months=_months_between(customer.relationship_start_date, as_of),
        monthly_income_paise=income,
        existing_emi_paise=existing_emi,
        card_utilization=utilization,
        max_dpd=max_dpd,
        active_unsecured_count=unsecured,
        has_salary_signal=has_salary,
        transaction_count=txn_count,
        held_product_ids=frozenset(held),
        confidence=confidence,
        fraud_flag=customer.fraud_flag,
        has_recent_default=recent_default,
    )


def _confidence(txn_count: int, has_salary: bool, config: ScoringConfig) -> Confidence:
    c = config.confidence
    if txn_count >= c.high_min_transactions and has_salary:
        return Confidence.HIGH
    if txn_count >= c.medium_min_transactions:
        return Confidence.MEDIUM
    return Confidence.LOW
