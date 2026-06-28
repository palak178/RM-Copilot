"""Domain entities and enums."""

import dataclasses
from datetime import date, datetime

import pytest

from rm_copilot.domain.entities import Customer
from rm_copilot.domain.enums import (
    EmploymentType,
    Gender,
    KycStatus,
    Language,
    RiskBand,
    Segment,
    TxnDirection,
)
from rm_copilot.domain.money import to_paise


def _customer() -> Customer:
    now = datetime(2026, 6, 15, 0, 0, 0)
    return Customer(
        customer_id="CUST000001",
        full_name="Priya Sharma",
        first_name="Priya",
        dob=date(1992, 1, 1),
        age=34,
        gender=Gender.F,
        employment_type=EmploymentType.SALARIED,
        segment=Segment.PRIORITY,
        kyc_status=KycStatus.VERIFIED,
        internal_risk_band=RiskBand.LOW,
        city="Pune",
        state="Maharashtra",
        city_tier=1,
        relationship_start_date=date(2019, 3, 10),
        marketing_opt_in=True,
        do_not_disturb=False,
        preferred_language=Language.HI_EN,
        created_at=now,
        updated_at=now,
    )


def test_strenum_values_match_storage() -> None:
    assert Segment.PRIORITY == "PRIORITY"
    assert TxnDirection.CREDIT.value == "CREDIT"
    assert Language.HI_EN.value == "hi_en"


def test_entities_are_immutable() -> None:
    customer = _customer()
    with pytest.raises(dataclasses.FrozenInstanceError):
        customer.age = 99  # type: ignore[misc]


def test_to_paise_rounds_to_nearest_paisa() -> None:
    assert to_paise(150_000) == 15_000_000
    assert to_paise(12.345) == 1234
