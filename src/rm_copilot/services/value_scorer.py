"""Value score — relationship worth, independent of product (data-model §6.1/§13.1).

A transparent weighted sum of normalized factors (AUM, product depth, tenure,
income proxy). Every factor emits a reason code. Pure and config-driven.
"""

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.assessment import FactorContribution, Score
from rm_copilot.domain.money import format_inr
from rm_copilot.services.features import CustomerFeatures

_AUM_BAND_LABELS = ("Low", "Mid", "High", "Top")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _aum_band(aum_paise: int, bands: list[int]) -> int:
    """Return the band index (0..len(bands)) for an AUM amount."""
    return sum(1 for threshold in bands if aum_paise >= threshold)


def score_value(features: CustomerFeatures, config: ScoringConfig) -> Score:
    """Compute the Value score (0..100) with reason-coded factors."""
    cfg = config.value
    w = cfg.weights

    band = _aum_band(features.aum_paise, cfg.aum_bands_paise)
    aum_norm = band / len(cfg.aum_bands_paise)
    depth_norm = _clamp01(features.product_depth / cfg.product_depth_cap)
    tenure_norm = _clamp01(features.tenure_months / cfg.tenure_cap_months)
    income_norm = _clamp01(features.monthly_income_paise / cfg.income_cap_paise)

    factors = (
        _factor(
            "aum",
            w["aum"],
            aum_norm,
            f"AUM {format_inr(features.aum_paise)} ({_AUM_BAND_LABELS[band]} band)",
        ),
        _factor(
            "product_depth",
            w["product_depth"],
            depth_norm,
            f"Holds {features.product_depth} product(s)",
        ),
        _factor(
            "tenure",
            w["tenure"],
            tenure_norm,
            f"{features.tenure_months // 12}-year relationship",
        ),
        _factor(
            "income",
            w["income"],
            income_norm,
            f"Income proxy ~{format_inr(features.monthly_income_paise)}/mo",
        ),
    )
    total = round(sum(f.contribution for f in factors))
    return Score(score=total, confidence=features.confidence, factors=factors)


def _factor(key: str, weight: float, normalized: float, reason: str) -> FactorContribution:
    return FactorContribution(
        key=key,
        detail=reason,
        weight=weight,
        normalized=normalized,
        contribution=weight * normalized * 100,
        reason=reason,
    )
