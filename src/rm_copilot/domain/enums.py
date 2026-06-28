"""Domain enumerations.

Values mirror exactly the CHECK-constrained columns in docs/data-model.md §4.
`StrEnum` members compare/serialize as their string value, which is what the
data layer stores in SQLite.
"""

from enum import StrEnum


class Segment(StrEnum):
    STANDARD = "STANDARD"
    PREFERRED = "PREFERRED"
    PRIORITY = "PRIORITY"
    WEALTH = "WEALTH"


class EmploymentType(StrEnum):
    SALARIED = "SALARIED"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    BUSINESS = "BUSINESS"
    RETIRED = "RETIRED"
    STUDENT = "STUDENT"


class KycStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"


class RiskBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Confidence(StrEnum):
    """Confidence in a computed score, driven by data completeness."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Gender(StrEnum):
    M = "M"
    F = "F"
    OTHER = "OTHER"


class Language(StrEnum):
    EN_IN = "en_IN"
    HI_IN = "hi_IN"
    HI_EN = "hi_en"


class ProductType(StrEnum):
    SAVINGS = "SAVINGS"
    CURRENT = "CURRENT"
    FD = "FD"
    RD = "RD"
    PERSONAL_LOAN = "PERSONAL_LOAN"
    AUTO_LOAN = "AUTO_LOAN"
    HOME_LOAN = "HOME_LOAN"
    CREDIT_CARD = "CREDIT_CARD"


class ProductClass(StrEnum):
    DEPOSIT = "DEPOSIT"
    LENDING = "LENDING"
    CARD = "CARD"
    INVESTMENT = "INVESTMENT"


class HoldingStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    MATURED = "MATURED"
    DELINQUENT = "DELINQUENT"


class TxnDirection(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class TxnCategory(StrEnum):
    SALARY = "SALARY"
    EMI = "EMI"
    RENT = "RENT"
    UTILITIES = "UTILITIES"
    GROCERIES = "GROCERIES"
    DINING = "DINING"
    SHOPPING = "SHOPPING"
    FUEL = "FUEL"
    TRAVEL = "TRAVEL"
    INVESTMENT = "INVESTMENT"
    TRANSFER = "TRANSFER"
    ATM = "ATM"
    FEES = "FEES"
    INTEREST = "INTEREST"
    REFUND = "REFUND"
    OTHER = "OTHER"


class TxnChannel(StrEnum):
    UPI = "UPI"
    NEFT = "NEFT"
    IMPS = "IMPS"
    CARD = "CARD"
    ATM = "ATM"
    AUTO_DEBIT = "AUTO_DEBIT"
    CASH = "CASH"


class InteractionChannel(StrEnum):
    WHATSAPP = "WHATSAPP"
    CALL = "CALL"
    EMAIL = "EMAIL"
    BRANCH = "BRANCH"
    SMS = "SMS"


class InteractionDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class InteractionOutcome(StrEnum):
    CONTACTED = "CONTACTED"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    NO_RESPONSE = "NO_RESPONSE"
    CONVERTED = "CONVERTED"
    DO_NOT_DISTURB = "DO_NOT_DISTURB"


class OutreachStatus(StrEnum):
    """Lifecycle status of an outreach decision (data-model §4.6)."""

    DRAFTED = "DRAFTED"
    COMPLIANCE_FAILED = "COMPLIANCE_FAILED"
    READY = "READY"
    DRY_RUN_SENT = "DRY_RUN_SENT"
    SUPPRESSED = "SUPPRESSED"
