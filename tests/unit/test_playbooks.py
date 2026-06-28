"""Product playbooks: loading, validation, and catalog construction."""

from datetime import datetime

from rm_copilot.config.playbooks import load_playbooks
from rm_copilot.data.catalog import product_catalog
from rm_copilot.domain.enums import ProductType
from rm_copilot.domain.money import to_paise

NOW = datetime(2026, 6, 15, 0, 0, 0)


def test_playbooks_load() -> None:
    playbooks = load_playbooks()
    ids = {p.product_id for p in playbooks}
    assert "PROD_PERSONAL_LOAN" in ids
    assert len(playbooks) >= 8


def test_catalog_built_from_playbooks() -> None:
    catalog = product_catalog(NOW)
    by_id = {p.product_id: p for p in catalog}
    assert len(catalog) == len(by_id)  # unique
    types = {p.product_type for p in catalog}
    assert ProductType.PERSONAL_LOAN in types

    loan = by_id["PROD_PERSONAL_LOAN"]
    assert loan.min_monthly_income_paise == to_paise(25_000)  # rupees → paise
    assert loan.max_active_unsecured_loans == 2
    assert loan.indicative_interest_rate_pct == 11.5
