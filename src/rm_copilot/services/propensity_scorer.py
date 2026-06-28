"""Propensity score — likelihood to convert on this product now (data-model §6.2/§6.3).

Static fit (affordability, debt burden, utilization, delinquency, life-stage) as a
weighted sum, plus additive boosts for detected temporal triggers ('this month').
Pure and config-driven; every factor and trigger is reason-coded.
"""

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.assessment import FactorContribution, Score, Trigger
from rm_copilot.domain.entities import Product
from rm_copilot.services.features import CustomerFeatures


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_propensity(
    features: CustomerFeatures,
    triggers: tuple[Trigger, ...],
    product: Product,
    config: ScoringConfig,
) -> Score:
    """Compute the Propensity score (0..100) with reason-coded factors + triggers."""
    cfg = config.propensity
    w = cfg.weights
    income = features.monthly_income_paise

    affordability = _affordability(features, product, cfg.income_headroom_multiple)
    foir = (features.existing_emi_paise / income) if income > 0 else 1.0
    debt_burden = _clamp01(1 - foir / cfg.max_foir)
    utilization = _clamp01(1 - features.card_utilization / cfg.utilization_cap)
    delinquency = 1.0 if features.max_dpd == 0 else 0.0
    life_stage = _life_stage_fit(features.age, product, cfg.life_stage)

    factors = (
        _factor(
            "affordability",
            w["affordability"],
            affordability,
            "Income comfortably supports the product"
            if affordability > 0.6
            else "Limited affordability headroom",
        ),
        _factor(
            "debt_burden",
            w["debt_burden"],
            debt_burden,
            f"Existing EMI burden {foir * 100:.0f}% of income",
        ),
        _factor(
            "utilization",
            w["utilization"],
            utilization,
            f"Card utilization {features.card_utilization * 100:.0f}%",
        ),
        _factor(
            "delinquency",
            w["delinquency"],
            delinquency,
            "No delinquency (DPD 0)"
            if features.max_dpd == 0
            else f"Delinquency present (DPD {features.max_dpd})",
        ),
        _factor(
            "life_stage",
            w["life_stage"],
            life_stage,
            f"Life-stage fit for {product.product_type.value.lower().replace('_', ' ')}",
        ),
    )

    base = sum(f.contribution for f in factors)
    boost = sum(t.boost for t in triggers)
    score = max(0, min(100, round(base + boost)))
    return Score(score=score, confidence=features.confidence, factors=factors, triggers=triggers)


def _affordability(features: CustomerFeatures, product: Product, headroom: float) -> float:
    if product.min_monthly_income_paise <= 0:
        return 1.0
    disposable = features.monthly_income_paise - features.existing_emi_paise
    return _clamp01(disposable / (headroom * product.min_monthly_income_paise))


def _life_stage_fit(age: int, product: Product, life_stage: dict[str, list[int]]) -> float:
    band = life_stage.get(product.product_type.value)
    if not band:
        return 0.5
    return 1.0 if band[0] <= age <= band[1] else 0.5


def _factor(key: str, weight: float, normalized: float, reason: str) -> FactorContribution:
    return FactorContribution(
        key=key,
        detail=reason,
        weight=weight,
        normalized=normalized,
        contribution=weight * normalized * 100,
        reason=reason,
    )
