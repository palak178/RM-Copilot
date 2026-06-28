"""Feature extraction from holdings + transactions."""

from datetime import date, datetime

from rm_copilot.domain.enums import Confidence, TxnCategory, TxnChannel, TxnDirection
from rm_copilot.domain.money import to_paise
from rm_copilot.services.features import extract_features

AS_OF = date(2026, 6, 15)


def test_extracts_core_features(
    make_customer, make_holding, make_txn, products, scoring_config
) -> None:
    customer = make_customer(employment_type=make_customer().employment_type)
    holdings = [
        make_holding(
            holding_id="H1", product_id="PROD_SAVINGS", current_balance_paise=to_paise(300_000)
        ),
        make_holding(holding_id="H2", product_id="PROD_FD", principal_paise=to_paise(500_000)),
        make_holding(
            holding_id="H3", product_id="PROD_AUTO_LOAN", emi_amount_paise=to_paise(12_400)
        ),
        make_holding(
            holding_id="H4",
            product_id="PROD_CREDIT_CARD",
            credit_limit_paise=to_paise(400_000),
            current_outstanding_paise=to_paise(40_000),
            dpd=0,
        ),
    ]
    txns = [
        make_txn(
            transaction_id=f"S{m}",
            txn_ts=datetime(2026, m, 1, 0, 0, 0),
            amount_paise=to_paise(150_000),
            direction=TxnDirection.CREDIT,
            category=TxnCategory.SALARY,
            channel=TxnChannel.NEFT,
        )
        for m in (3, 4, 5)
    ]

    f = extract_features(customer, holdings, txns, products, AS_OF, scoring_config)

    assert f.aum_paise == to_paise(800_000)  # savings + FD
    assert f.product_depth == 4
    assert f.monthly_income_paise == to_paise(150_000)  # median salary
    assert f.existing_emi_paise == to_paise(12_400)
    assert abs(f.card_utilization - 0.10) < 1e-6
    assert f.max_dpd == 0
    assert f.active_unsecured_count == 1  # the credit card
    assert f.has_salary_signal is True
    assert f.confidence == Confidence.LOW  # only 3 transactions


def test_no_transactions_falls_back_to_declared_income(
    make_customer, products, scoring_config
) -> None:
    customer = make_customer(declared_annual_income_paise=to_paise(1_200_000))
    f = extract_features(customer, [], [], products, AS_OF, scoring_config)
    assert f.monthly_income_paise == to_paise(1_200_000) // 12
    assert f.has_salary_signal is False
    assert f.aum_paise == 0
    assert f.confidence == Confidence.LOW
