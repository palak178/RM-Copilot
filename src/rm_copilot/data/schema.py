"""SQLite schema — the durable data foundation (docs/data-model.md §4).

Design conventions:
- TEXT surrogate keys; money as INTEGER paise; dates/timestamps as ISO-8601 TEXT;
  booleans as INTEGER 0/1; enums as TEXT with CHECK constraints.
- Foreign keys enforced (see connection.connect).

All seven durable tables are created (complete foundation). Milestone M1 populates
customers, products, product_holdings, transactions, and interactions; outreach_log
and conversation_sessions are created empty and written by M4/M5.
"""

import sqlite3

# Order matters for creation (parents before children) and deletion (reverse).
TABLE_ORDER = (
    "products",
    "customers",
    "product_holdings",
    "transactions",
    "interactions",
    "outreach_log",
    "conversation_sessions",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id                  TEXT PRIMARY KEY,
    name                        TEXT NOT NULL,
    product_type                TEXT NOT NULL CHECK (product_type IN
        ('SAVINGS','CURRENT','FD','RD','PERSONAL_LOAN','AUTO_LOAN','HOME_LOAN','CREDIT_CARD')),
    product_class               TEXT NOT NULL CHECK (product_class IN
        ('DEPOSIT','LENDING','CARD','INVESTMENT')),
    is_active                   INTEGER NOT NULL CHECK (is_active IN (0,1)),
    min_age                     INTEGER NOT NULL,
    max_age                     INTEGER NOT NULL,
    min_monthly_income_paise    INTEGER NOT NULL,
    requires_kyc                INTEGER NOT NULL CHECK (requires_kyc IN (0,1)),
    max_active_unsecured_loans  INTEGER,
    typical_ticket_size_paise   INTEGER,
    indicative_interest_rate_pct REAL,
    created_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_class ON products(product_class, is_active);

CREATE TABLE IF NOT EXISTS customers (
    customer_id                 TEXT PRIMARY KEY,
    full_name                   TEXT NOT NULL,
    first_name                  TEXT NOT NULL,
    masked_pan                  TEXT,
    dob                         TEXT NOT NULL,
    age                         INTEGER NOT NULL,
    gender                      TEXT NOT NULL CHECK (gender IN ('M','F','OTHER')),
    employment_type             TEXT NOT NULL CHECK (employment_type IN
        ('SALARIED','SELF_EMPLOYED','BUSINESS','RETIRED','STUDENT')),
    occupation                  TEXT,
    declared_annual_income_paise INTEGER,
    segment                     TEXT NOT NULL CHECK (segment IN
        ('STANDARD','PREFERRED','PRIORITY','WEALTH')),
    kyc_status                  TEXT NOT NULL CHECK (kyc_status IN ('VERIFIED','PENDING','EXPIRED')),
    internal_risk_band          TEXT NOT NULL CHECK (internal_risk_band IN ('LOW','MEDIUM','HIGH')),
    fraud_flag                  INTEGER NOT NULL DEFAULT 0 CHECK (fraud_flag IN (0,1)),
    last_default_date           TEXT,
    city                        TEXT NOT NULL,
    state                       TEXT NOT NULL,
    city_tier                   INTEGER NOT NULL CHECK (city_tier IN (1,2,3)),
    relationship_start_date     TEXT NOT NULL,
    marketing_opt_in            INTEGER NOT NULL CHECK (marketing_opt_in IN (0,1)),
    do_not_disturb              INTEGER NOT NULL CHECK (do_not_disturb IN (0,1)),
    preferred_language          TEXT NOT NULL CHECK (preferred_language IN ('en_IN','hi_IN','hi_en')),
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city, city_tier);
CREATE INDEX IF NOT EXISTS idx_customers_kyc ON customers(kyc_status);

CREATE TABLE IF NOT EXISTS product_holdings (
    holding_id                  TEXT PRIMARY KEY,
    customer_id                 TEXT NOT NULL,
    product_id                  TEXT NOT NULL,
    status                      TEXT NOT NULL CHECK (status IN
        ('ACTIVE','CLOSED','MATURED','DELINQUENT')),
    opened_date                 TEXT NOT NULL,
    closed_date                 TEXT,
    current_balance_paise       INTEGER,
    avg_monthly_balance_paise   INTEGER,
    principal_paise             INTEGER,
    maturity_date               TEXT,
    interest_rate_pct           REAL,
    sanctioned_amount_paise     INTEGER,
    outstanding_principal_paise INTEGER,
    emi_amount_paise            INTEGER,
    emi_day_of_month            INTEGER,
    loan_end_date               TEXT,
    credit_limit_paise          INTEGER,
    current_outstanding_paise   INTEGER,
    dpd                         INTEGER,
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE INDEX IF NOT EXISTS idx_holdings_customer ON product_holdings(customer_id);
CREATE INDEX IF NOT EXISTS idx_holdings_product ON product_holdings(product_id);
CREATE INDEX IF NOT EXISTS idx_holdings_maturity ON product_holdings(maturity_date);
CREATE INDEX IF NOT EXISTS idx_holdings_loanend ON product_holdings(loan_end_date);
CREATE INDEX IF NOT EXISTS idx_holdings_status ON product_holdings(status);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id              TEXT PRIMARY KEY,
    customer_id                 TEXT NOT NULL,
    holding_id                  TEXT,
    txn_ts                      TEXT NOT NULL,
    amount_paise                INTEGER NOT NULL CHECK (amount_paise > 0),
    direction                   TEXT NOT NULL CHECK (direction IN ('CREDIT','DEBIT')),
    category                    TEXT NOT NULL CHECK (category IN
        ('SALARY','EMI','RENT','UTILITIES','GROCERIES','DINING','SHOPPING','FUEL','TRAVEL',
         'INVESTMENT','TRANSFER','ATM','FEES','INTEREST','REFUND','OTHER')),
    channel                     TEXT NOT NULL CHECK (channel IN
        ('UPI','NEFT','IMPS','CARD','ATM','AUTO_DEBIT','CASH')),
    counterparty                TEXT,
    balance_after_paise         INTEGER,
    created_at                  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (holding_id) REFERENCES product_holdings(holding_id)
);
CREATE INDEX IF NOT EXISTS idx_txn_customer_ts ON transactions(customer_id, txn_ts);
CREATE INDEX IF NOT EXISTS idx_txn_customer_cat ON transactions(customer_id, category);
CREATE INDEX IF NOT EXISTS idx_txn_cat_ts ON transactions(category, txn_ts);

CREATE TABLE IF NOT EXISTS interactions (
    interaction_id              TEXT PRIMARY KEY,
    customer_id                 TEXT NOT NULL,
    interaction_ts              TEXT NOT NULL,
    channel                     TEXT NOT NULL CHECK (channel IN
        ('WHATSAPP','CALL','EMAIL','BRANCH','SMS')),
    direction                   TEXT NOT NULL CHECK (direction IN ('INBOUND','OUTBOUND')),
    topic                       TEXT,
    outcome                     TEXT NOT NULL CHECK (outcome IN
        ('CONTACTED','INTERESTED','NOT_INTERESTED','NO_RESPONSE','CONVERTED','DO_NOT_DISTURB')),
    notes                       TEXT,
    created_at                  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
CREATE INDEX IF NOT EXISTS idx_interactions_customer ON interactions(customer_id, interaction_ts);

-- Written by M4/M5; created empty here for a complete foundation (data-model §4.6/§4.7).
CREATE TABLE IF NOT EXISTS outreach_log (
    outreach_id                 TEXT PRIMARY KEY,
    customer_id                 TEXT NOT NULL,
    product_id                  TEXT NOT NULL,
    recommended_product_id      TEXT,
    session_id                  TEXT,
    run_id                      TEXT NOT NULL,
    value_score                 INTEGER,
    propensity_score            INTEGER,
    confidence                  TEXT,
    assessment_snapshot         TEXT,
    message_text                TEXT,
    message_locale              TEXT,
    message_tone                TEXT,
    groundedness_passed         INTEGER,
    compliance_passed           INTEGER,
    regeneration_count          INTEGER,
    status                      TEXT NOT NULL CHECK (status IN
        ('DRAFTED','COMPLIANCE_FAILED','READY','DRY_RUN_SENT','SUPPRESSED')),
    suppressed_reason           TEXT,
    created_at                  TEXT NOT NULL,
    UNIQUE (customer_id, product_id, session_id, run_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE INDEX IF NOT EXISTS idx_outreach_customer ON outreach_log(customer_id, created_at);

CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id                  TEXT PRIMARY KEY,
    started_at                  TEXT NOT NULL,
    last_active_at              TEXT NOT NULL,
    rm_identifier               TEXT,
    locale_default              TEXT,
    message_history             TEXT,
    last_result_set             TEXT
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes (idempotent)."""
    conn.executescript(_SCHEMA)


def clear_all(conn: sqlite3.Connection) -> None:
    """Delete all rows, children before parents (idempotent re-seed)."""
    for table in reversed(TABLE_ORDER):
        conn.execute(f"DELETE FROM {table}")
