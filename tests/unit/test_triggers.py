"""Temporal trigger detection."""

from datetime import date, datetime

from rm_copilot.domain.enums import TxnCategory, TxnDirection
from rm_copilot.domain.money import to_paise
from rm_copilot.services.triggers import detect_triggers

AS_OF = date(2026, 6, 15)
INCOME = to_paise(150_000)


def _keys(triggers) -> set[str]:
    return {t.key for t in triggers}


def test_no_triggers_when_no_signals(scoring_config) -> None:
    assert detect_triggers([], [], INCOME, scoring_config, AS_OF) == ()


def test_fd_maturing_detected(make_holding, scoring_config) -> None:
    fd = make_holding(
        product_id="PROD_FD", principal_paise=to_paise(500_000), maturity_date=date(2026, 6, 30)
    )
    triggers = detect_triggers([fd], [], INCOME, scoring_config, AS_OF)
    assert "fd_maturing" in _keys(triggers)


def test_emi_ending_detected(make_holding, scoring_config) -> None:
    loan = make_holding(
        product_id="PROD_AUTO_LOAN",
        emi_amount_paise=to_paise(12_400),
        loan_end_date=date(2026, 6, 25),
    )
    triggers = detect_triggers([loan], [], INCOME, scoring_config, AS_OF)
    assert "emi_ending" in _keys(triggers)


def test_large_outflow_detected(make_txn, scoring_config) -> None:
    big = make_txn(
        amount_paise=to_paise(300_000),
        direction=TxnDirection.DEBIT,
        category=TxnCategory.TRANSFER,
        txn_ts=datetime(2026, 6, 10, 0, 0, 0),
    )
    triggers = detect_triggers([], [big], INCOME, scoring_config, AS_OF)
    assert "large_outflow" in _keys(triggers)


def test_salary_hike_detected(make_txn, scoring_config) -> None:
    salaries = [
        make_txn(
            transaction_id=f"S{m}",
            amount_paise=to_paise(150_000),
            direction=TxnDirection.CREDIT,
            category=TxnCategory.SALARY,
            txn_ts=datetime(2026, m, 1, 0, 0, 0),
        )
        for m in (3, 4, 5)
    ]
    salaries.append(
        make_txn(
            transaction_id="S6",
            amount_paise=to_paise(170_000),
            direction=TxnDirection.CREDIT,
            category=TxnCategory.SALARY,
            txn_ts=datetime(2026, 6, 1, 0, 0, 0),
        )
    )
    triggers = detect_triggers([], salaries, INCOME, scoring_config, AS_OF)
    assert "salary_hike" in _keys(triggers)


def test_festival_window_detected(scoring_config) -> None:
    triggers = detect_triggers([], [], INCOME, scoring_config, date(2026, 10, 1))
    assert "festival_window" in _keys(triggers)
