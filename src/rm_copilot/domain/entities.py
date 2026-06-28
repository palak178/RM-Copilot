"""Durable domain entities (docs/data-model.md §2).

Pure, immutable value objects — no I/O, no SQL, no LLM. Money is integer paise;
dates use `date`/`datetime`. The data layer maps these to/from SQLite rows.

Only the five entities seeded and queried in milestone M1 are modeled here.
OutreachLog and ConversationSession (also durable, per §2.6/§2.7) are added in the
milestones that write them (M4/M5); their tables already exist in the schema.
"""

from dataclasses import dataclass
from datetime import date, datetime

from rm_copilot.domain.enums import (
    EmploymentType,
    Gender,
    HoldingStatus,
    InteractionChannel,
    InteractionDirection,
    InteractionOutcome,
    KycStatus,
    Language,
    OutreachStatus,
    ProductClass,
    ProductType,
    RiskBand,
    Segment,
    TxnCategory,
    TxnChannel,
    TxnDirection,
)


@dataclass(frozen=True, slots=True)
class Customer:
    """Master record of a banking relationship."""

    customer_id: str
    full_name: str
    first_name: str
    dob: date
    age: int
    gender: Gender
    employment_type: EmploymentType
    segment: Segment
    kyc_status: KycStatus
    internal_risk_band: RiskBand
    city: str
    state: str
    city_tier: int
    relationship_start_date: date
    marketing_opt_in: bool
    do_not_disturb: bool
    preferred_language: Language
    created_at: datetime
    updated_at: datetime
    masked_pan: str | None = None
    occupation: str | None = None
    declared_annual_income_paise: int | None = None
    fraud_flag: bool = False
    last_default_date: date | None = None  # most recent loan/card default, if any


@dataclass(frozen=True, slots=True)
class Product:
    """Catalog item + eligibility parameters (data-model §4.2)."""

    product_id: str
    name: str
    product_type: ProductType
    product_class: ProductClass
    is_active: bool
    min_age: int
    max_age: int
    min_monthly_income_paise: int
    requires_kyc: bool
    created_at: datetime
    max_active_unsecured_loans: int | None = None
    typical_ticket_size_paise: int | None = None
    indicative_interest_rate_pct: float | None = None


@dataclass(frozen=True, slots=True)
class ProductHolding:
    """A product a customer holds — deposit, FD/RD, loan, or card.

    Type-specific fields are populated by product class (deposits carry balances,
    FD/RD a maturity, loans an EMI + end date, cards a limit). The richest source
    of value and trigger signals.
    """

    holding_id: str
    customer_id: str
    product_id: str
    status: HoldingStatus
    opened_date: date
    created_at: datetime
    updated_at: datetime
    closed_date: date | None = None
    # Deposit
    current_balance_paise: int | None = None
    avg_monthly_balance_paise: int | None = None
    # FD / RD
    principal_paise: int | None = None
    maturity_date: date | None = None
    interest_rate_pct: float | None = None
    # Loan
    sanctioned_amount_paise: int | None = None
    outstanding_principal_paise: int | None = None
    emi_amount_paise: int | None = None
    emi_day_of_month: int | None = None
    loan_end_date: date | None = None
    # Card
    credit_limit_paise: int | None = None
    current_outstanding_paise: int | None = None
    # Loan / card risk
    dpd: int | None = None


@dataclass(frozen=True, slots=True)
class Transaction:
    """An append-only money movement; substrate for behavioral features/triggers."""

    transaction_id: str
    customer_id: str
    txn_ts: datetime
    amount_paise: int  # always > 0; sign is expressed via `direction`
    direction: TxnDirection
    category: TxnCategory
    channel: TxnChannel
    created_at: datetime
    holding_id: str | None = None
    counterparty: str | None = None
    balance_after_paise: int | None = None


@dataclass(frozen=True, slots=True)
class OutreachLog:
    """Immutable record of an outreach decision — the dry-run 'send' + audit (§2.6)."""

    outreach_id: str
    customer_id: str
    product_id: str
    run_id: str
    status: OutreachStatus
    created_at: datetime
    recommended_product_id: str | None = None
    session_id: str | None = None
    value_score: int | None = None
    propensity_score: int | None = None
    confidence: str | None = None
    assessment_snapshot: str | None = None  # JSON
    message_text: str | None = None
    message_locale: str | None = None
    message_tone: str | None = None
    groundedness_passed: bool | None = None
    compliance_passed: bool | None = None
    regeneration_count: int | None = None
    suppressed_reason: str | None = None


@dataclass(frozen=True, slots=True)
class Interaction:
    """A prior RM <-> customer touchpoint (personalization + consent context)."""

    interaction_id: str
    customer_id: str
    interaction_ts: datetime
    channel: InteractionChannel
    direction: InteractionDirection
    outcome: InteractionOutcome
    created_at: datetime
    topic: str | None = None
    notes: str | None = None
