"""Product playbooks — per-product config as data (no-code extensibility).

Each `config/playbooks/<product>.yaml` defines a product's identity, eligibility gates,
recommendation metadata, and outreach talking points. The product catalog is built from
these (see data.catalog), so adding a product is a new YAML file — no code change.
Validated at load time; a malformed playbook fails fast.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel

from rm_copilot.domain.enums import ProductClass, ProductType

DEFAULT_PLAYBOOKS_DIR = Path("config/playbooks")


class Playbook(BaseModel):
    product_id: str
    name: str
    product_type: ProductType
    product_class: ProductClass
    is_active: bool = True
    # Eligibility (monetary thresholds in rupees for readability; converted to paise downstream)
    min_age: int
    max_age: int
    min_monthly_income_rupees: int = 0
    requires_kyc: bool = True
    max_active_unsecured_loans: int | None = None
    # Recommendation / outreach metadata
    typical_ticket_size_rupees: int | None = None
    indicative_interest_rate_pct: float | None = None
    talking_points: list[str] = []


def load_playbooks(directory: str | Path | None = None) -> list[Playbook]:
    """Load and validate every playbook in the directory (sorted for deterministic order)."""
    path = Path(directory) if directory is not None else DEFAULT_PLAYBOOKS_DIR
    playbooks = [
        Playbook.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))
        for f in sorted(path.glob("*.yaml"))
    ]
    if not playbooks:
        raise FileNotFoundError(f"no product playbooks found in {path}")
    return playbooks
