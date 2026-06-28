"""Temporal trigger detection — the 'why this month' engine (data-model §6.3).

Detects time-bound events from holdings/transactions that raise conversion
propensity in the current window. Pure: domain objects in, Trigger objects out.
"""

from datetime import date, datetime, timedelta

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.assessment import Trigger
from rm_copilot.domain.entities import ProductHolding, Transaction
from rm_copilot.domain.enums import HoldingStatus, TxnCategory, TxnDirection
from rm_copilot.domain.money import format_inr

_HIKE_LOOKBACK = 6


def detect_triggers(
    holdings: list[ProductHolding],
    transactions: list[Transaction],
    monthly_income_paise: int,
    config: ScoringConfig,
    as_of: date,
) -> tuple[Trigger, ...]:
    """Return the triggers currently firing for a customer."""
    boosts = config.propensity.trigger_boosts
    window_end = as_of + timedelta(days=config.triggers.window_days)
    active = [h for h in holdings if h.status == HoldingStatus.ACTIVE]
    found: list[Trigger] = []

    # FD/RD maturing within the window (only deposits carry maturity_date).
    fd = next(
        (h for h in active if h.maturity_date and as_of <= h.maturity_date <= window_end), None
    )
    if fd is not None:
        found.append(
            Trigger(
                key="fd_maturing",
                detail=f"{format_inr(fd.principal_paise or 0)} matures {fd.maturity_date}",
                boost=boosts.get("fd_maturing", 0),
                reason=(
                    f"Deposit of {format_inr(fd.principal_paise or 0)} matures on "
                    f"{fd.maturity_date} — funds freeing up"
                ),
            )
        )

    # Loan whose final EMI falls within the window (only loans carry loan_end_date).
    loan = next(
        (h for h in active if h.loan_end_date and as_of <= h.loan_end_date <= window_end), None
    )
    if loan is not None:
        emi = format_inr(loan.emi_amount_paise or 0)
        found.append(
            Trigger(
                key="emi_ending",
                detail=f"loan ends {loan.loan_end_date}",
                boost=boosts.get("emi_ending", 0),
                reason=f"Loan EMI ends {loan.loan_end_date} → ~{emi}/mo repayment capacity frees up",
            )
        )

    # Recent large outflow (liquidity need).
    if monthly_income_paise > 0:
        threshold = int(monthly_income_paise * config.triggers.large_outflow_multiple)
        cutoff = datetime.combine(
            as_of - timedelta(days=config.triggers.window_days), datetime.min.time()
        )
        large = next(
            (
                t
                for t in transactions
                if t.direction == TxnDirection.DEBIT
                and t.amount_paise >= threshold
                and t.txn_ts >= cutoff
            ),
            None,
        )
        if large is not None:
            found.append(
                Trigger(
                    key="large_outflow",
                    detail=f"{format_inr(large.amount_paise)} on {large.txn_ts.date()}",
                    boost=boosts.get("large_outflow", 0),
                    reason=f"Recent large outflow of {format_inr(large.amount_paise)} — possible liquidity need",
                )
            )

    # Salary hike (higher repayment capacity).
    if _has_salary_hike(transactions, config, as_of):
        found.append(
            Trigger(
                key="salary_hike",
                detail=f"latest salary up >= {config.triggers.salary_hike_pct:.0f}%",
                boost=boosts.get("salary_hike", 0),
                reason=f"Salary increased ~{config.triggers.salary_hike_pct:.0f}% recently — higher capacity",
            )
        )

    # Festival window (seasonal demand).
    if as_of.month in config.triggers.festival_months:
        found.append(
            Trigger(
                key="festival_window",
                detail=f"month {as_of.month}",
                boost=boosts.get("festival_window", 0),
                reason="Festival season — seasonal credit demand",
            )
        )

    return tuple(found)


def _has_salary_hike(transactions: list[Transaction], config: ScoringConfig, as_of: date) -> bool:
    salaries = sorted(
        (
            t
            for t in transactions
            if t.category == TxnCategory.SALARY and t.direction == TxnDirection.CREDIT
        ),
        key=lambda t: t.txn_ts,
    )
    if len(salaries) < 3:
        return False
    latest = salaries[-1].amount_paise
    prior = [s.amount_paise for s in salaries[:-1]][-_HIKE_LOOKBACK:]
    if not prior:
        return False
    median_prior = sorted(prior)[len(prior) // 2]
    if median_prior <= 0:
        return False
    return latest >= median_prior * (1 + config.triggers.salary_hike_pct / 100)
