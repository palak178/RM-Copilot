"""Product catalog — built from YAML playbooks (config/playbooks/).

The catalog is no longer hardcoded: each product is a playbook file (data-model §4.2,
ADR-0006). Adding a product = adding a playbook YAML; no code change. Eligibility
parameters are product attributes carried here and remain distinct from scoring config.
"""

from datetime import datetime

from rm_copilot.config.playbooks import Playbook, load_playbooks
from rm_copilot.domain.entities import Product
from rm_copilot.domain.money import to_paise


def _to_product(playbook: Playbook, created_at: datetime) -> Product:
    return Product(
        product_id=playbook.product_id,
        name=playbook.name,
        product_type=playbook.product_type,
        product_class=playbook.product_class,
        is_active=playbook.is_active,
        min_age=playbook.min_age,
        max_age=playbook.max_age,
        min_monthly_income_paise=to_paise(playbook.min_monthly_income_rupees),
        requires_kyc=playbook.requires_kyc,
        max_active_unsecured_loans=playbook.max_active_unsecured_loans,
        typical_ticket_size_paise=(
            to_paise(playbook.typical_ticket_size_rupees)
            if playbook.typical_ticket_size_rupees is not None
            else None
        ),
        indicative_interest_rate_pct=playbook.indicative_interest_rate_pct,
        created_at=created_at,
    )


def product_catalog(created_at: datetime, playbooks: list[Playbook] | None = None) -> list[Product]:
    """Build the product catalog from playbooks (loaded from disk unless provided)."""
    resolved = playbooks if playbooks is not None else load_playbooks()
    return [_to_product(pb, created_at) for pb in resolved]
