"""get_customer_360 — drill-down read of one customer (assessment-plan.md §14).

Deterministic. Assembles profile + holdings + a transaction summary + recent
interactions for follow-ups ("why her?") and message grounding. PII-minimized.
"""

from pydantic import BaseModel

from rm_copilot.data.database import Database
from rm_copilot.services.assessment import CustomerNotFoundError
from rm_copilot.tools.base import Tool

_MAX_INTERACTIONS = 5


class Customer360Input(BaseModel):
    customer_id: str


class HoldingSummary(BaseModel):
    product_id: str
    status: str
    current_balance_paise: int | None = None
    principal_paise: int | None = None
    maturity_date: str | None = None
    emi_amount_paise: int | None = None
    loan_end_date: str | None = None
    credit_limit_paise: int | None = None
    current_outstanding_paise: int | None = None
    dpd: int | None = None


class InteractionSummary(BaseModel):
    interaction_ts: str
    channel: str
    outcome: str
    topic: str | None = None


class Customer360Output(BaseModel):
    customer_id: str
    first_name: str
    masked_pan: str | None
    age: int
    gender: str
    segment: str
    employment_type: str
    occupation: str | None
    city: str
    state: str
    city_tier: int
    kyc_status: str
    internal_risk_band: str
    marketing_opt_in: bool
    do_not_disturb: bool
    preferred_language: str
    relationship_start_date: str
    holdings: list[HoldingSummary]
    transaction_count: int
    recent_interactions: list[InteractionSummary]


class GetCustomer360Tool(Tool):
    name = "get_customer_360"
    description = (
        "Fetch a single customer's full profile: demographics, consent, product holdings "
        "(balances, EMIs, maturities), transaction count, and recent interactions."
    )
    input_model = Customer360Input

    def __init__(self, db: Database) -> None:
        self._db = db

    def execute(self, args: Customer360Input) -> Customer360Output:
        customer = self._db.customers.get(args.customer_id)
        if customer is None:
            raise CustomerNotFoundError(args.customer_id)

        holdings = [
            HoldingSummary(
                product_id=h.product_id,
                status=h.status.value,
                current_balance_paise=h.current_balance_paise,
                principal_paise=h.principal_paise,
                maturity_date=h.maturity_date.isoformat() if h.maturity_date else None,
                emi_amount_paise=h.emi_amount_paise,
                loan_end_date=h.loan_end_date.isoformat() if h.loan_end_date else None,
                credit_limit_paise=h.credit_limit_paise,
                current_outstanding_paise=h.current_outstanding_paise,
                dpd=h.dpd,
            )
            for h in self._db.holdings.list_for_customer(args.customer_id)
        ]
        interactions = self._db.interactions.list_for_customer(args.customer_id)
        recent = [
            InteractionSummary(
                interaction_ts=i.interaction_ts.isoformat(),
                channel=i.channel.value,
                outcome=i.outcome.value,
                topic=i.topic,
            )
            for i in interactions[-_MAX_INTERACTIONS:]
        ]
        txn_count = len(self._db.transactions.list_for_customer(args.customer_id))

        return Customer360Output(
            customer_id=customer.customer_id,
            first_name=customer.first_name,
            masked_pan=customer.masked_pan,
            age=customer.age,
            gender=customer.gender.value,
            segment=customer.segment.value,
            employment_type=customer.employment_type.value,
            occupation=customer.occupation,
            city=customer.city,
            state=customer.state,
            city_tier=customer.city_tier,
            kyc_status=customer.kyc_status.value,
            internal_risk_band=customer.internal_risk_band.value,
            marketing_opt_in=customer.marketing_opt_in,
            do_not_disturb=customer.do_not_disturb,
            preferred_language=customer.preferred_language.value,
            relationship_start_date=customer.relationship_start_date.isoformat(),
            holdings=holdings,
            transaction_count=txn_count,
            recent_interactions=recent,
        )
