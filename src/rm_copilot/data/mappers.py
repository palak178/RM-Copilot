"""Row <-> entity mapping — the SQLite/domain boundary.

The only place that converts between SQLite storage types (TEXT/INTEGER) and rich
domain types (date/datetime/enum/bool/int paise). Keeps the domain pure and the
repositories free of conversion noise.
"""

import sqlite3
from datetime import date, datetime

from rm_copilot.domain.entities import (
    Customer,
    Interaction,
    OutreachLog,
    Product,
    ProductHolding,
    Transaction,
)
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


# --- primitive helpers -------------------------------------------------------
def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _bool(value: int) -> bool:
    return bool(value)


def _ibool(value: bool) -> int:
    return int(value)


# --- Customer ----------------------------------------------------------------
def customer_to_params(c: Customer) -> dict[str, object]:
    return {
        "customer_id": c.customer_id,
        "full_name": c.full_name,
        "first_name": c.first_name,
        "masked_pan": c.masked_pan,
        "dob": c.dob.isoformat(),
        "age": c.age,
        "gender": c.gender.value,
        "employment_type": c.employment_type.value,
        "occupation": c.occupation,
        "declared_annual_income_paise": c.declared_annual_income_paise,
        "segment": c.segment.value,
        "kyc_status": c.kyc_status.value,
        "internal_risk_band": c.internal_risk_band.value,
        "fraud_flag": _ibool(c.fraud_flag),
        "last_default_date": c.last_default_date.isoformat() if c.last_default_date else None,
        "city": c.city,
        "state": c.state,
        "city_tier": c.city_tier,
        "relationship_start_date": c.relationship_start_date.isoformat(),
        "marketing_opt_in": _ibool(c.marketing_opt_in),
        "do_not_disturb": _ibool(c.do_not_disturb),
        "preferred_language": c.preferred_language.value,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def row_to_customer(r: sqlite3.Row) -> Customer:
    return Customer(
        customer_id=r["customer_id"],
        full_name=r["full_name"],
        first_name=r["first_name"],
        masked_pan=r["masked_pan"],
        dob=date.fromisoformat(r["dob"]),
        age=r["age"],
        gender=Gender(r["gender"]),
        employment_type=EmploymentType(r["employment_type"]),
        occupation=r["occupation"],
        declared_annual_income_paise=r["declared_annual_income_paise"],
        segment=Segment(r["segment"]),
        kyc_status=KycStatus(r["kyc_status"]),
        internal_risk_band=RiskBand(r["internal_risk_band"]),
        fraud_flag=_bool(r["fraud_flag"]),
        last_default_date=_date(r["last_default_date"]),
        city=r["city"],
        state=r["state"],
        city_tier=r["city_tier"],
        relationship_start_date=date.fromisoformat(r["relationship_start_date"]),
        marketing_opt_in=_bool(r["marketing_opt_in"]),
        do_not_disturb=_bool(r["do_not_disturb"]),
        preferred_language=Language(r["preferred_language"]),
        created_at=_dt(r["created_at"]),
        updated_at=_dt(r["updated_at"]),
    )


# --- Product -----------------------------------------------------------------
def product_to_params(p: Product) -> dict[str, object]:
    return {
        "product_id": p.product_id,
        "name": p.name,
        "product_type": p.product_type.value,
        "product_class": p.product_class.value,
        "is_active": _ibool(p.is_active),
        "min_age": p.min_age,
        "max_age": p.max_age,
        "min_monthly_income_paise": p.min_monthly_income_paise,
        "requires_kyc": _ibool(p.requires_kyc),
        "max_active_unsecured_loans": p.max_active_unsecured_loans,
        "typical_ticket_size_paise": p.typical_ticket_size_paise,
        "indicative_interest_rate_pct": p.indicative_interest_rate_pct,
        "created_at": p.created_at.isoformat(),
    }


def row_to_product(r: sqlite3.Row) -> Product:
    return Product(
        product_id=r["product_id"],
        name=r["name"],
        product_type=ProductType(r["product_type"]),
        product_class=ProductClass(r["product_class"]),
        is_active=_bool(r["is_active"]),
        min_age=r["min_age"],
        max_age=r["max_age"],
        min_monthly_income_paise=r["min_monthly_income_paise"],
        requires_kyc=_bool(r["requires_kyc"]),
        max_active_unsecured_loans=r["max_active_unsecured_loans"],
        typical_ticket_size_paise=r["typical_ticket_size_paise"],
        indicative_interest_rate_pct=r["indicative_interest_rate_pct"],
        created_at=_dt(r["created_at"]),
    )


# --- ProductHolding ----------------------------------------------------------
def holding_to_params(h: ProductHolding) -> dict[str, object]:
    return {
        "holding_id": h.holding_id,
        "customer_id": h.customer_id,
        "product_id": h.product_id,
        "status": h.status.value,
        "opened_date": h.opened_date.isoformat(),
        "closed_date": h.closed_date.isoformat() if h.closed_date else None,
        "current_balance_paise": h.current_balance_paise,
        "avg_monthly_balance_paise": h.avg_monthly_balance_paise,
        "principal_paise": h.principal_paise,
        "maturity_date": h.maturity_date.isoformat() if h.maturity_date else None,
        "interest_rate_pct": h.interest_rate_pct,
        "sanctioned_amount_paise": h.sanctioned_amount_paise,
        "outstanding_principal_paise": h.outstanding_principal_paise,
        "emi_amount_paise": h.emi_amount_paise,
        "emi_day_of_month": h.emi_day_of_month,
        "loan_end_date": h.loan_end_date.isoformat() if h.loan_end_date else None,
        "credit_limit_paise": h.credit_limit_paise,
        "current_outstanding_paise": h.current_outstanding_paise,
        "dpd": h.dpd,
        "created_at": h.created_at.isoformat(),
        "updated_at": h.updated_at.isoformat(),
    }


def row_to_holding(r: sqlite3.Row) -> ProductHolding:
    return ProductHolding(
        holding_id=r["holding_id"],
        customer_id=r["customer_id"],
        product_id=r["product_id"],
        status=HoldingStatus(r["status"]),
        opened_date=date.fromisoformat(r["opened_date"]),
        closed_date=_date(r["closed_date"]),
        current_balance_paise=r["current_balance_paise"],
        avg_monthly_balance_paise=r["avg_monthly_balance_paise"],
        principal_paise=r["principal_paise"],
        maturity_date=_date(r["maturity_date"]),
        interest_rate_pct=r["interest_rate_pct"],
        sanctioned_amount_paise=r["sanctioned_amount_paise"],
        outstanding_principal_paise=r["outstanding_principal_paise"],
        emi_amount_paise=r["emi_amount_paise"],
        emi_day_of_month=r["emi_day_of_month"],
        loan_end_date=_date(r["loan_end_date"]),
        credit_limit_paise=r["credit_limit_paise"],
        current_outstanding_paise=r["current_outstanding_paise"],
        dpd=r["dpd"],
        created_at=_dt(r["created_at"]),
        updated_at=_dt(r["updated_at"]),
    )


# --- Transaction -------------------------------------------------------------
def transaction_to_params(t: Transaction) -> dict[str, object]:
    return {
        "transaction_id": t.transaction_id,
        "customer_id": t.customer_id,
        "holding_id": t.holding_id,
        "txn_ts": t.txn_ts.isoformat(),
        "amount_paise": t.amount_paise,
        "direction": t.direction.value,
        "category": t.category.value,
        "channel": t.channel.value,
        "counterparty": t.counterparty,
        "balance_after_paise": t.balance_after_paise,
        "created_at": t.created_at.isoformat(),
    }


def row_to_transaction(r: sqlite3.Row) -> Transaction:
    return Transaction(
        transaction_id=r["transaction_id"],
        customer_id=r["customer_id"],
        holding_id=r["holding_id"],
        txn_ts=_dt(r["txn_ts"]),
        amount_paise=r["amount_paise"],
        direction=TxnDirection(r["direction"]),
        category=TxnCategory(r["category"]),
        channel=TxnChannel(r["channel"]),
        counterparty=r["counterparty"],
        balance_after_paise=r["balance_after_paise"],
        created_at=_dt(r["created_at"]),
    )


# --- Interaction -------------------------------------------------------------
def interaction_to_params(i: Interaction) -> dict[str, object]:
    return {
        "interaction_id": i.interaction_id,
        "customer_id": i.customer_id,
        "interaction_ts": i.interaction_ts.isoformat(),
        "channel": i.channel.value,
        "direction": i.direction.value,
        "topic": i.topic,
        "outcome": i.outcome.value,
        "notes": i.notes,
        "created_at": i.created_at.isoformat(),
    }


def outreach_to_params(o: OutreachLog) -> dict[str, object]:
    return {
        "outreach_id": o.outreach_id,
        "customer_id": o.customer_id,
        "product_id": o.product_id,
        "recommended_product_id": o.recommended_product_id,
        "session_id": o.session_id,
        "run_id": o.run_id,
        "value_score": o.value_score,
        "propensity_score": o.propensity_score,
        "confidence": o.confidence,
        "assessment_snapshot": o.assessment_snapshot,
        "message_text": o.message_text,
        "message_locale": o.message_locale,
        "message_tone": o.message_tone,
        "groundedness_passed": None
        if o.groundedness_passed is None
        else _ibool(o.groundedness_passed),
        "compliance_passed": None if o.compliance_passed is None else _ibool(o.compliance_passed),
        "regeneration_count": o.regeneration_count,
        "status": o.status.value,
        "suppressed_reason": o.suppressed_reason,
        "created_at": o.created_at.isoformat(),
    }


def row_to_outreach(r: sqlite3.Row) -> OutreachLog:
    return OutreachLog(
        outreach_id=r["outreach_id"],
        customer_id=r["customer_id"],
        product_id=r["product_id"],
        recommended_product_id=r["recommended_product_id"],
        session_id=r["session_id"],
        run_id=r["run_id"],
        value_score=r["value_score"],
        propensity_score=r["propensity_score"],
        confidence=r["confidence"],
        assessment_snapshot=r["assessment_snapshot"],
        message_text=r["message_text"],
        message_locale=r["message_locale"],
        message_tone=r["message_tone"],
        groundedness_passed=None
        if r["groundedness_passed"] is None
        else _bool(r["groundedness_passed"]),
        compliance_passed=None if r["compliance_passed"] is None else _bool(r["compliance_passed"]),
        regeneration_count=r["regeneration_count"],
        status=OutreachStatus(r["status"]),
        suppressed_reason=r["suppressed_reason"],
        created_at=_dt(r["created_at"]),
    )


def row_to_interaction(r: sqlite3.Row) -> Interaction:
    return Interaction(
        interaction_id=r["interaction_id"],
        customer_id=r["customer_id"],
        interaction_ts=_dt(r["interaction_ts"]),
        channel=InteractionChannel(r["channel"]),
        direction=InteractionDirection(r["direction"]),
        outcome=InteractionOutcome(r["outcome"]),
        topic=r["topic"],
        notes=r["notes"],
        created_at=_dt(r["created_at"]),
    )
