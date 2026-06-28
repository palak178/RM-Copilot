"""Deterministic synthetic generator: reproducibility, invariants, embedded signals."""

from datetime import date, timedelta

from rm_copilot.data.synthetic import generate_dataset
from rm_copilot.domain.enums import KycStatus, ProductType, Segment

AS_OF = date(2026, 6, 15)
MONTH_START = date(2026, 6, 1)
MONTH_END = date(2026, 6, 30)


def test_generation_is_deterministic() -> None:
    a = generate_dataset(seed=42, customer_count=25, as_of=AS_OF)
    b = generate_dataset(seed=42, customer_count=25, as_of=AS_OF)
    assert [c.customer_id for c in a.customers] == [c.customer_id for c in b.customers]
    assert [c.full_name for c in a.customers] == [c.full_name for c in b.customers]
    assert len(a.transactions) == len(b.transactions)
    assert sum(t.amount_paise for t in a.transactions) == sum(
        t.amount_paise for t in b.transactions
    )
    assert len(a.holdings) == len(b.holdings)


def test_count_and_catalog() -> None:
    d = generate_dataset(seed=1, customer_count=15, as_of=AS_OF)
    assert len(d.customers) == 15
    assert len(d.products) == 8


def test_every_customer_has_savings_and_money_is_positive_int() -> None:
    d = generate_dataset(seed=1, customer_count=15, as_of=AS_OF)
    with_savings = {h.customer_id for h in d.holdings if h.product_id == "PROD_SAVINGS"}
    assert with_savings == {c.customer_id for c in d.customers}
    for t in d.transactions:
        assert isinstance(t.amount_paise, int)
        assert t.amount_paise > 0


def test_hero_customer_profile() -> None:
    d = generate_dataset(seed=1, customer_count=20, as_of=AS_OF)
    hero = next(c for c in d.customers if c.customer_id == "CUST000001")
    assert hero.segment in (Segment.PRIORITY, Segment.WEALTH)
    assert hero.marketing_opt_in is True
    assert hero.do_not_disturb is False


def test_fd_maturing_this_month_signal_present() -> None:
    d = generate_dataset(seed=1, customer_count=20, as_of=AS_OF)
    maturing = [
        h for h in d.holdings if h.maturity_date and MONTH_START <= h.maturity_date <= MONTH_END
    ]
    assert maturing
    assert any(h.customer_id == "CUST000001" for h in maturing)


def test_loan_ending_soon_signal_present() -> None:
    d = generate_dataset(seed=1, customer_count=20, as_of=AS_OF)
    window_end = AS_OF + timedelta(days=30)
    ending = [h for h in d.holdings if h.loan_end_date and AS_OF <= h.loan_end_date <= window_end]
    assert any(h.customer_id == "CUST000001" for h in ending)


def test_suppression_and_ineligible_customers_exist() -> None:
    d = generate_dataset(seed=1, customer_count=20, as_of=AS_OF)
    assert any(c.do_not_disturb for c in d.customers)
    assert any(c.kyc_status == KycStatus.PENDING for c in d.customers)


def test_hero_has_low_utilization_card() -> None:
    d = generate_dataset(seed=1, customer_count=20, as_of=AS_OF)
    cards = [
        h
        for h in d.holdings
        if h.customer_id == "CUST000001" and h.product_id == "PROD_CREDIT_CARD"
    ]
    assert cards
    card = cards[0]
    assert card.credit_limit_paise and card.current_outstanding_paise is not None
    utilization = card.current_outstanding_paise / card.credit_limit_paise
    assert utilization < 0.20


def test_personal_loan_in_catalog() -> None:
    d = generate_dataset(seed=1, customer_count=5, as_of=AS_OF)
    types = {p.product_type for p in d.products}
    assert ProductType.PERSONAL_LOAN in types
