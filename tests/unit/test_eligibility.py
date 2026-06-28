"""Eligibility gates and failure modes."""

from rm_copilot.domain.enums import KycStatus
from rm_copilot.domain.money import to_paise
from rm_copilot.services.eligibility import check_eligibility


def _personal_loan(products):
    return products["PROD_PERSONAL_LOAN"]


def test_eligible_customer_passes(make_customer, make_features, products) -> None:
    result = check_eligibility(make_customer(), make_features(), _personal_loan(products))
    assert result.eligible
    assert result.failed_rules == ()


def test_age_below_minimum_fails(make_customer, make_features, products) -> None:
    result = check_eligibility(
        make_customer(age=18), make_features(age=18), _personal_loan(products)
    )
    assert not result.eligible
    assert any("age" in r for r in result.failed_rules)


def test_kyc_not_verified_fails(make_customer, make_features, products) -> None:
    result = check_eligibility(
        make_customer(kyc_status=KycStatus.PENDING), make_features(), _personal_loan(products)
    )
    assert not result.eligible
    assert any("KYC" in r for r in result.failed_rules)


def test_income_below_minimum_fails(make_customer, make_features, products) -> None:
    result = check_eligibility(
        make_customer(),
        make_features(monthly_income_paise=to_paise(10_000)),
        _personal_loan(products),
    )
    assert not result.eligible
    assert any("income" in r for r in result.failed_rules)


def test_already_holds_product_fails(make_customer, make_features, products) -> None:
    held = make_features(held_product_ids=frozenset({"PROD_PERSONAL_LOAN"}))
    result = check_eligibility(make_customer(), held, _personal_loan(products))
    assert not result.eligible
    assert any("already holds" in r for r in result.failed_rules)


def test_delinquency_blocks_new_credit(make_customer, make_features, products) -> None:
    result = check_eligibility(make_customer(), make_features(max_dpd=45), _personal_loan(products))
    assert not result.eligible
    assert any("delinquency" in r for r in result.failed_rules)


def test_too_many_unsecured_facilities_fails(make_customer, make_features, products) -> None:
    result = check_eligibility(
        make_customer(), make_features(active_unsecured_count=2), _personal_loan(products)
    )
    assert not result.eligible
    assert any("unsecured" in r for r in result.failed_rules)


def test_fraud_flag_blocks_new_credit(make_customer, make_features, products) -> None:
    result = check_eligibility(
        make_customer(), make_features(fraud_flag=True), _personal_loan(products)
    )
    assert not result.eligible
    assert any("fraud" in r for r in result.failed_rules)


def test_recent_default_blocks_new_credit(make_customer, make_features, products) -> None:
    result = check_eligibility(
        make_customer(), make_features(has_recent_default=True), _personal_loan(products)
    )
    assert not result.eligible
    assert any("default" in r for r in result.failed_rules)
