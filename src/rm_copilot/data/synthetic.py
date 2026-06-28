"""Deterministic synthetic dataset generator (docs/data-model.md §5).

Given a fixed (seed, customer_count, as_of) the output is reproducible. All
structural/numeric choices come from `random.Random(seed)`; Faker (seeded) is used
only for names. Dates are anchored to `as_of` (default today) so "this month"
signals stay genuinely current in a live demo while tests pin `as_of`.

Embedded ground-truth signals (so reason codes are visibly correct):
- A few **hero** customers (index 0..2) with aligned signals: high value, regular
  salary, an FD maturing this month, a loan EMI ending within ~2 weeks, a recent
  large outflow, a salary hike, and a low-utilization card — clearly eligible for a
  personal loan.
- A **suppression** customer (do_not_disturb) and an **ineligible** customer
  (KYC pending + a delinquent card) to exercise compliance and eligibility paths.
- Probabilistic signals scattered across the remaining population.
"""

import calendar
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from faker import Faker

from rm_copilot.data.catalog import product_catalog
from rm_copilot.domain.entities import (
    Customer,
    Interaction,
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
    RiskBand,
    Segment,
    TxnCategory,
    TxnChannel,
    TxnDirection,
)
from rm_copilot.domain.money import to_paise

# --- reference distributions -------------------------------------------------
CITIES: list[tuple[str, str, int]] = [
    ("Mumbai", "Maharashtra", 1),
    ("Bengaluru", "Karnataka", 1),
    ("Delhi", "Delhi", 1),
    ("Pune", "Maharashtra", 1),
    ("Chennai", "Tamil Nadu", 1),
    ("Hyderabad", "Telangana", 1),
    ("Jaipur", "Rajasthan", 2),
    ("Indore", "Madhya Pradesh", 2),
    ("Kochi", "Kerala", 2),
    ("Nagpur", "Maharashtra", 2),
    ("Surat", "Gujarat", 2),
    ("Bhopal", "Madhya Pradesh", 3),
    ("Guwahati", "Assam", 3),
    ("Raipur", "Chhattisgarh", 3),
]

OCCUPATIONS: dict[EmploymentType, list[str]] = {
    EmploymentType.SALARIED: [
        "Software Engineer",
        "Teacher",
        "Nurse",
        "Bank Officer",
        "Marketing Manager",
        "Accountant",
        "Civil Engineer",
    ],
    EmploymentType.SELF_EMPLOYED: ["Chartered Accountant", "Lawyer", "Doctor", "Consultant"],
    EmploymentType.BUSINESS: ["Shop Owner", "Trader", "Restaurateur", "Manufacturer"],
    EmploymentType.RETIRED: ["Retired Officer", "Retired Teacher", "Pensioner"],
    EmploymentType.STUDENT: ["Student"],
}

# monthly income range in rupees by segment
SEGMENT_INCOME: dict[Segment, tuple[int, int]] = {
    Segment.STANDARD: (25_000, 60_000),
    Segment.PREFERRED: (60_000, 120_000),
    Segment.PRIORITY: (120_000, 300_000),
    Segment.WEALTH: (300_000, 900_000),
}

# discretionary spend: (category, channel, low_frac, high_frac) of monthly income
SPEND_CATEGORIES: list[tuple[TxnCategory, TxnChannel, float, float]] = [
    (TxnCategory.GROCERIES, TxnChannel.UPI, 0.04, 0.10),
    (TxnCategory.DINING, TxnChannel.CARD, 0.02, 0.06),
    (TxnCategory.SHOPPING, TxnChannel.CARD, 0.03, 0.12),
    (TxnCategory.FUEL, TxnChannel.UPI, 0.02, 0.05),
    (TxnCategory.UTILITIES, TxnChannel.AUTO_DEBIT, 0.02, 0.05),
    (TxnCategory.TRAVEL, TxnChannel.CARD, 0.03, 0.09),
]

_MONTHS_HISTORY = 12


@dataclass(frozen=True, slots=True)
class Dataset:
    """An in-memory, ready-to-insert synthetic dataset."""

    products: list[Product]
    customers: list[Customer]
    holdings: list[ProductHolding]
    transactions: list[Transaction]
    interactions: list[Interaction]


# --- date helpers ------------------------------------------------------------
def _add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _day_in_month(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _last_day_of_month(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)


def generate_dataset(seed: int, customer_count: int, as_of: date | None = None) -> Dataset:
    """Build a reproducible dataset for the given seed/count/as_of."""
    return _Generator(seed, customer_count, as_of or date.today()).build()


class _Generator:
    def __init__(self, seed: int, customer_count: int, as_of: date) -> None:
        self.rng = random.Random(seed)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(seed)
        self.count = customer_count
        self.as_of = as_of
        self.now = datetime.combine(as_of, time(0, 0, 0))
        self._cust_n = 0
        self._hold_n = 0
        self._txn_n = 0
        self._intx_n = 0
        self.customers: list[Customer] = []
        self.holdings: list[ProductHolding] = []
        self.transactions: list[Transaction] = []
        self.interactions: list[Interaction] = []

    # -- id helpers --
    def _customer_id(self) -> str:
        self._cust_n += 1
        return f"CUST{self._cust_n:06d}"

    def _holding_id(self) -> str:
        self._hold_n += 1
        return f"HOLD{self._hold_n:08d}"

    def _transaction_id(self) -> str:
        self._txn_n += 1
        return f"TXN{self._txn_n:010d}"

    def _interaction_id(self) -> str:
        self._intx_n += 1
        return f"INTX{self._intx_n:08d}"

    def _role(self, i: int) -> str:
        if i < min(3, self.count):
            return "hero"
        if i == 3 and self.count > 3:
            return "suppression"
        if i == 4 and self.count > 4:
            return "ineligible"
        return "normal"

    def build(self) -> Dataset:
        products = product_catalog(self.now)
        for i in range(self.count):
            self._make_customer(i)
        return Dataset(
            products=products,
            customers=self.customers,
            holdings=self.holdings,
            transactions=self.transactions,
            interactions=self.interactions,
        )

    # -- customer --
    def _make_customer(self, i: int) -> None:
        role = self._role(i)
        rng = self.rng
        gender = rng.choices([Gender.M, Gender.F, Gender.OTHER], weights=[49, 49, 2])[0]
        first_name = self.fake.first_name()
        full_name = f"{first_name} {self.fake.last_name()}"

        if role == "hero":
            segment = rng.choice([Segment.PRIORITY, Segment.WEALTH])
            employment = EmploymentType.SALARIED
        else:
            segment = rng.choices(list(SEGMENT_INCOME), weights=[55, 30, 12, 3])[0]
            employment = rng.choices(list(EmploymentType), weights=[60, 18, 12, 7, 3])[0]

        age = self._age_for(employment, role)
        city, state, tier = rng.choice(CITIES)
        monthly_income = self._income_for(segment, employment, role)

        if role == "ineligible":
            kyc, risk = KycStatus.PENDING, RiskBand.HIGH
        elif role == "hero":
            # Heroes are deterministically clean so they are clearly eligible (data-model §5.2).
            kyc, risk = KycStatus.VERIFIED, RiskBand.LOW
        else:
            kyc = rng.choices(list(KycStatus), weights=[92, 5, 3])[0]
            risk = rng.choices(list(RiskBand), weights=[70, 22, 8])[0]

        marketing_opt_in = role != "suppression" and (role == "hero" or rng.random() < 0.85)
        do_not_disturb = role == "suppression" or (role == "normal" and rng.random() < 0.05)

        # Hard-exclusion signals (banking realism) — never on heroes, who must stay eligible.
        is_normal = role == "normal"
        fraud_flag = is_normal and rng.random() < 0.02
        last_default = (
            _add_days(self.as_of, -rng.randint(10, 170))
            if is_normal and not fraud_flag and rng.random() < 0.03
            else None
        )

        tenure_years = rng.uniform(5, 9) if role == "hero" else rng.uniform(0.5, 12)
        rel_start = _add_months(self.as_of, -int(tenure_years * 12))

        language = (
            Language.HI_EN
            if role == "hero" and i == 0
            else rng.choices(list(Language), weights=[60, 10, 30])[0]
        )

        customer = Customer(
            customer_id=self._customer_id(),
            full_name=full_name,
            first_name=first_name,
            masked_pan=self._masked_pan(),
            dob=_add_months(self.as_of, -age * 12),
            age=age,
            gender=gender,
            employment_type=employment,
            occupation=rng.choice(OCCUPATIONS[employment]),
            declared_annual_income_paise=to_paise(monthly_income * 12),
            segment=segment,
            kyc_status=kyc,
            internal_risk_band=risk,
            fraud_flag=fraud_flag,
            last_default_date=last_default,
            city=city,
            state=state,
            city_tier=tier,
            relationship_start_date=rel_start,
            marketing_opt_in=marketing_opt_in,
            do_not_disturb=do_not_disturb,
            preferred_language=language,
            created_at=self.now,
            updated_at=self.now,
        )
        self.customers.append(customer)

        holdings = self._make_holdings(customer, monthly_income, role)
        self.holdings.extend(holdings)
        self._make_transactions(customer, monthly_income, holdings, role)
        self._make_interactions(customer, role)

    def _age_for(self, employment: EmploymentType, role: str) -> int:
        rng = self.rng
        if role == "hero":
            return rng.randint(30, 45)
        if employment == EmploymentType.STUDENT:
            return rng.randint(18, 24)
        if employment == EmploymentType.RETIRED:
            return rng.randint(60, 78)
        return rng.randint(24, 58)

    def _income_for(self, segment: Segment, employment: EmploymentType, role: str) -> int:
        rng = self.rng
        if employment == EmploymentType.STUDENT:
            return rng.randint(8_000, 15_000)
        low, high = SEGMENT_INCOME[segment]
        income = rng.randint(low, high)
        if employment == EmploymentType.RETIRED:
            income = int(income * 0.4)
        if role == "hero":
            income = max(income, rng.randint(150_000, 250_000))
        return income

    def _masked_pan(self) -> str:
        letter = self.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
        return f"XXXXX{self.rng.randint(1000, 9999)}{letter}"

    # -- holdings --
    def _make_holdings(self, c: Customer, monthly_income: int, role: str) -> list[ProductHolding]:
        rng = self.rng
        holdings: list[ProductHolding] = []

        # Everyone has a savings account.
        balance = monthly_income * rng.uniform(1.5, 8.0)
        if role == "hero":
            balance = max(balance, monthly_income * rng.uniform(4.0, 9.0))
        holdings.append(
            self._holding(
                c,
                "PROD_SAVINGS",
                HoldingStatus.ACTIVE,
                c.relationship_start_date,
                current_balance_paise=to_paise(balance),
                avg_monthly_balance_paise=to_paise(balance * rng.uniform(0.7, 1.0)),
            )
        )

        # Fixed deposit (heroes always; ~30% otherwise).
        if role == "hero" or rng.random() < 0.30:
            principal = monthly_income * rng.uniform(3, 18)
            maturing_now = role == "hero" or rng.random() < 0.35
            maturity = (
                _last_day_of_month(self.as_of)
                if maturing_now
                else _add_months(self.as_of, rng.randint(2, 24))
            )
            holdings.append(
                self._holding(
                    c,
                    "PROD_FD",
                    HoldingStatus.ACTIVE,
                    _add_months(self.as_of, -rng.randint(6, 24)),
                    principal_paise=to_paise(principal),
                    maturity_date=maturity,
                    interest_rate_pct=round(rng.uniform(6.5, 7.5), 2),
                )
            )

        # A loan (heroes: auto loan ending soon; ~25% otherwise).
        if role == "hero" or rng.random() < 0.25:
            holdings.append(self._make_loan(c, monthly_income, role))

        # Credit card (heroes always; ~35% otherwise).
        if role == "hero" or rng.random() < 0.35:
            limit = max(monthly_income * rng.uniform(2, 6), 50_000)
            utilization = rng.uniform(0.05, 0.12) if role == "hero" else rng.uniform(0.05, 0.7)
            dpd = rng.choice([0, 0, 0, 35, 60]) if role == "ineligible" else 0
            status = HoldingStatus.DELINQUENT if dpd > 0 else HoldingStatus.ACTIVE
            holdings.append(
                self._holding(
                    c,
                    "PROD_CREDIT_CARD",
                    status,
                    _add_months(self.as_of, -rng.randint(6, 48)),
                    credit_limit_paise=to_paise(limit),
                    current_outstanding_paise=to_paise(limit * utilization),
                    dpd=dpd,
                )
            )

        return holdings

    def _make_loan(self, c: Customer, monthly_income: int, role: str) -> ProductHolding:
        rng = self.rng
        product_id, sanctioned = (
            ("PROD_AUTO_LOAN", monthly_income * rng.uniform(8, 14))
            if role == "hero"
            else rng.choice(
                [
                    ("PROD_PERSONAL_LOAN", monthly_income * rng.uniform(6, 18)),
                    ("PROD_AUTO_LOAN", monthly_income * rng.uniform(8, 16)),
                    ("PROD_HOME_LOAN", monthly_income * rng.uniform(40, 90)),
                ]
            )
        )
        ending_soon = role == "hero" or rng.random() < 0.35
        loan_end = (
            _add_days(self.as_of, rng.randint(8, 18))
            if ending_soon
            else _add_months(self.as_of, rng.randint(6, 60))
        )
        emi = sanctioned / rng.uniform(18, 60)
        outstanding = emi * (rng.randint(1, 3) if ending_soon else rng.randint(6, 40))
        dpd = 0
        return self._holding(
            c,
            product_id,
            HoldingStatus.ACTIVE,
            _add_months(self.as_of, -rng.randint(12, 60)),
            sanctioned_amount_paise=to_paise(sanctioned),
            outstanding_principal_paise=to_paise(outstanding),
            emi_amount_paise=to_paise(emi),
            emi_day_of_month=rng.randint(1, 28),
            loan_end_date=loan_end,
            dpd=dpd,
        )

    def _holding(
        self,
        c: Customer,
        product_id: str,
        status: HoldingStatus,
        opened: date,
        **fields: object,
    ) -> ProductHolding:
        return ProductHolding(
            holding_id=self._holding_id(),
            customer_id=c.customer_id,
            product_id=product_id,
            status=status,
            opened_date=opened,
            created_at=self.now,
            updated_at=self.now,
            **fields,  # type: ignore[arg-type]
        )

    # -- transactions --
    def _make_transactions(
        self, c: Customer, monthly_income: int, holdings: list[ProductHolding], role: str
    ) -> None:
        rng = self.rng
        loan = next(
            (
                h
                for h in holdings
                if h.emi_amount_paise is not None and h.status == HoldingStatus.ACTIVE
            ),
            None,
        )
        pays_rent = rng.random() < 0.6
        salary_hike = role == "hero" or (
            c.employment_type == EmploymentType.SALARIED and rng.random() < 0.2
        )
        large_outflow = role == "hero" or rng.random() < 0.25

        for k in range(_MONTHS_HISTORY - 1, -1, -1):
            month_date = _add_months(self.as_of, -k)
            recent = k <= 1
            self._salary_txns(c, monthly_income, month_date, salary_hike and recent)
            if loan is not None:
                self._emi_txn(c, loan, month_date)
            if pays_rent:
                self._spend_txn(
                    c,
                    TxnCategory.RENT,
                    TxnChannel.NEFT,
                    monthly_income * rng.uniform(0.20, 0.32),
                    _day_in_month(month_date.year, month_date.month, rng.randint(5, 7)),
                )
            for cat, chan, lo, hi in rng.sample(SPEND_CATEGORIES, k=rng.randint(3, 6)):
                self._spend_txn(
                    c,
                    cat,
                    chan,
                    monthly_income * rng.uniform(lo, hi),
                    _day_in_month(month_date.year, month_date.month, rng.randint(8, 27)),
                )

        if large_outflow:
            recent_month = self.as_of
            self._spend_txn(
                c,
                TxnCategory.TRANSFER,
                TxnChannel.IMPS,
                monthly_income * rng.uniform(1.5, 2.5),
                _day_in_month(recent_month.year, recent_month.month, max(1, self.as_of.day - 3)),
                counterparty="Large outflow",
            )

    def _salary_txns(self, c: Customer, income: int, month_date: date, hike: bool) -> None:
        rng = self.rng
        emp = c.employment_type
        if emp in (EmploymentType.SALARIED, EmploymentType.RETIRED):
            amount = income * (1.12 if hike else 1.0)
            day = _day_in_month(month_date.year, month_date.month, rng.randint(1, 3))
            self._credit_txn(c, TxnCategory.SALARY, TxnChannel.NEFT, amount, day)
        elif emp in (EmploymentType.SELF_EMPLOYED, EmploymentType.BUSINESS):
            for _ in range(rng.randint(1, 3)):
                day = _day_in_month(month_date.year, month_date.month, rng.randint(1, 27))
                self._credit_txn(
                    c, TxnCategory.TRANSFER, TxnChannel.IMPS, income * rng.uniform(0.3, 0.7), day
                )
        else:  # STUDENT
            day = _day_in_month(month_date.year, month_date.month, rng.randint(1, 5))
            self._credit_txn(c, TxnCategory.TRANSFER, TxnChannel.UPI, income, day)

    def _emi_txn(self, c: Customer, loan: ProductHolding, month_date: date) -> None:
        day = _day_in_month(month_date.year, month_date.month, loan.emi_day_of_month or 5)
        ts = datetime.combine(day, time(self.rng.randint(0, 23), self.rng.randint(0, 59)))
        self.transactions.append(
            Transaction(
                transaction_id=self._transaction_id(),
                customer_id=c.customer_id,
                holding_id=loan.holding_id,
                txn_ts=ts,
                amount_paise=loan.emi_amount_paise or 0,
                direction=TxnDirection.DEBIT,
                category=TxnCategory.EMI,
                channel=TxnChannel.AUTO_DEBIT,
                created_at=self.now,
            )
        )

    def _credit_txn(
        self, c: Customer, cat: TxnCategory, chan: TxnChannel, rupees: float, day: date
    ) -> None:
        ts = datetime.combine(day, time(self.rng.randint(0, 23), self.rng.randint(0, 59)))
        self.transactions.append(
            Transaction(
                transaction_id=self._transaction_id(),
                customer_id=c.customer_id,
                txn_ts=ts,
                amount_paise=to_paise(rupees),
                direction=TxnDirection.CREDIT,
                category=cat,
                channel=chan,
                created_at=self.now,
            )
        )

    def _spend_txn(
        self,
        c: Customer,
        cat: TxnCategory,
        chan: TxnChannel,
        rupees: float,
        day: date,
        counterparty: str | None = None,
    ) -> None:
        ts = datetime.combine(day, time(self.rng.randint(0, 23), self.rng.randint(0, 59)))
        self.transactions.append(
            Transaction(
                transaction_id=self._transaction_id(),
                customer_id=c.customer_id,
                txn_ts=ts,
                amount_paise=to_paise(rupees),
                direction=TxnDirection.DEBIT,
                category=cat,
                channel=chan,
                counterparty=counterparty,
                created_at=self.now,
            )
        )

    # -- interactions --
    def _make_interactions(self, c: Customer, role: str) -> None:
        rng = self.rng
        if role == "suppression":
            self._interaction(c, InteractionOutcome.DO_NOT_DISTURB, -rng.randint(5, 60))
            return
        if role == "normal" and rng.random() >= 0.4:
            return
        for _ in range(rng.randint(1, 3)):
            outcome = rng.choices(
                list(InteractionOutcome),
                weights=[30, 20, 15, 20, 5, 10],
            )[0]
            self._interaction(c, outcome, -rng.randint(5, 300))

    def _interaction(self, c: Customer, outcome: InteractionOutcome, days_ago: int) -> None:
        rng = self.rng
        ts = datetime.combine(_add_days(self.as_of, days_ago), time(rng.randint(9, 18), 0))
        self.interactions.append(
            Interaction(
                interaction_id=self._interaction_id(),
                customer_id=c.customer_id,
                interaction_ts=ts,
                channel=rng.choice(list(InteractionChannel)),
                direction=rng.choice(list(InteractionDirection)),
                outcome=outcome,
                topic=rng.choice(["personal_loan", "credit_card", "fd_renewal", "general"]),
                created_at=self.now,
            )
        )
