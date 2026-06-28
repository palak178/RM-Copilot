"""Shared pytest fixtures for RM Copilot.

Testing philosophy (assessment-plan.md §22):
- Deterministic services are unit-tested directly (fixed seed -> stable scores).
- The orchestrator is tested with a MOCKED LLMClient (no token spend, no network).
- One golden-path integration test runs end-to-end on a real SQLite DB.

The LLM is never called in tests.
"""

from collections.abc import Callable, Iterator
from datetime import date, datetime

import pytest

from rm_copilot.config.scoring import ScoringConfig, load_scoring_config
from rm_copilot.data.catalog import product_catalog
from rm_copilot.data.database import Database
from rm_copilot.data.seed import seed_database
from rm_copilot.domain.entities import Customer, Product, ProductHolding, Transaction
from rm_copilot.domain.enums import (
    Confidence,
    EmploymentType,
    Gender,
    HoldingStatus,
    KycStatus,
    Language,
    RiskBand,
    Segment,
    TxnCategory,
    TxnChannel,
    TxnDirection,
)
from rm_copilot.domain.money import to_paise
from rm_copilot.services.features import CustomerFeatures

# Fixed reference date so synthetic data (and "this month" signals) are deterministic.
AS_OF = date(2026, 6, 15)
NOW = datetime(2026, 6, 15, 0, 0, 0)


@pytest.fixture
def seeded_db() -> Iterator[Database]:
    """A small, deterministic in-memory database seeded for repository/service tests."""
    db = Database.connect(":memory:")
    seed_database(db, seed=7, customer_count=20, as_of=AS_OF)
    yield db
    db.close()


@pytest.fixture(scope="session")
def scoring_config() -> ScoringConfig:
    return load_scoring_config()


@pytest.fixture
def products() -> dict[str, Product]:
    return {p.product_id: p for p in product_catalog(NOW)}


@pytest.fixture
def make_features() -> Callable[..., CustomerFeatures]:
    def _make(**overrides: object) -> CustomerFeatures:
        defaults: dict[str, object] = {
            "customer_id": "CUST000001",
            "age": 34,
            "aum_paise": to_paise(800_000),
            "product_depth": 4,
            "tenure_months": 72,
            "monthly_income_paise": to_paise(150_000),
            "existing_emi_paise": to_paise(12_000),
            "card_utilization": 0.10,
            "max_dpd": 0,
            "active_unsecured_count": 1,
            "has_salary_signal": True,
            "transaction_count": 84,
            "held_product_ids": frozenset(
                {"PROD_SAVINGS", "PROD_AUTO_LOAN", "PROD_CREDIT_CARD", "PROD_FD"}
            ),
            "confidence": Confidence.HIGH,
            "fraud_flag": False,
            "has_recent_default": False,
        }
        defaults.update(overrides)
        return CustomerFeatures(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_customer() -> Callable[..., Customer]:
    def _make(**overrides: object) -> Customer:
        defaults: dict[str, object] = {
            "customer_id": "CUST000001",
            "full_name": "Priya Sharma",
            "first_name": "Priya",
            "dob": date(1992, 1, 1),
            "age": 34,
            "gender": Gender.F,
            "employment_type": EmploymentType.SALARIED,
            "segment": Segment.PRIORITY,
            "kyc_status": KycStatus.VERIFIED,
            "internal_risk_band": RiskBand.LOW,
            "city": "Pune",
            "state": "Maharashtra",
            "city_tier": 1,
            "relationship_start_date": date(2019, 3, 10),
            "marketing_opt_in": True,
            "do_not_disturb": False,
            "preferred_language": Language.HI_EN,
            "created_at": NOW,
            "updated_at": NOW,
        }
        defaults.update(overrides)
        return Customer(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_holding() -> Callable[..., ProductHolding]:
    def _make(**overrides: object) -> ProductHolding:
        defaults: dict[str, object] = {
            "holding_id": "HOLD00000001",
            "customer_id": "CUST000001",
            "product_id": "PROD_SAVINGS",
            "status": HoldingStatus.ACTIVE,
            "opened_date": date(2020, 1, 1),
            "created_at": NOW,
            "updated_at": NOW,
        }
        defaults.update(overrides)
        return ProductHolding(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_txn() -> Callable[..., Transaction]:
    def _make(**overrides: object) -> Transaction:
        defaults: dict[str, object] = {
            "transaction_id": "TXN0000000001",
            "customer_id": "CUST000001",
            "txn_ts": NOW,
            "amount_paise": to_paise(1_000),
            "direction": TxnDirection.DEBIT,
            "category": TxnCategory.OTHER,
            "channel": TxnChannel.UPI,
            "created_at": NOW,
        }
        defaults.update(overrides)
        return Transaction(**defaults)  # type: ignore[arg-type]

    return _make
