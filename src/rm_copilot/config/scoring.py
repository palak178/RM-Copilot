"""Typed scoring configuration (parses config/scoring.yaml).

The config is validated at load time so a malformed YAML fails fast rather than
producing silently-wrong scores.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_SCORING_PATH = Path("config/scoring.yaml")


class ValueConfig(BaseModel):
    weights: dict[str, float]
    aum_bands_paise: list[int]
    product_depth_cap: int
    tenure_cap_months: int
    income_cap_paise: int


class PropensityConfig(BaseModel):
    weights: dict[str, float]
    max_foir: float
    utilization_cap: float
    income_headroom_multiple: float
    life_stage: dict[str, list[int]]
    trigger_boosts: dict[str, int]


class TriggerConfig(BaseModel):
    window_days: int
    large_outflow_multiple: float
    salary_hike_pct: float
    festival_months: list[int]


class RankingConfig(BaseModel):
    value_weight: float
    propensity_weight: float


class ConfidenceConfig(BaseModel):
    high_min_transactions: int
    medium_min_transactions: int


class ComplianceConfig(BaseModel):
    banned_phrases: list[str]
    require_opt_out: bool
    opt_out_markers: list[str]
    max_chars: int


class ScoringConfig(BaseModel):
    value: ValueConfig
    propensity: PropensityConfig
    triggers: TriggerConfig
    ranking: RankingConfig
    confidence: ConfidenceConfig
    compliance: ComplianceConfig


def load_scoring_config(path: str | Path | None = None) -> ScoringConfig:
    """Load and validate scoring config from YAML (defaults to config/scoring.yaml)."""
    resolved = Path(path) if path is not None else DEFAULT_SCORING_PATH
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    return ScoringConfig.model_validate(data)
