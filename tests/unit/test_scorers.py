"""Value and propensity scorers."""

from rm_copilot.domain.assessment import Trigger
from rm_copilot.domain.money import to_paise
from rm_copilot.services.propensity_scorer import score_propensity
from rm_copilot.services.value_scorer import score_value


def test_value_score_high_for_strong_relationship(make_features, scoring_config) -> None:
    score = score_value(make_features(), scoring_config)
    assert score.score > 50
    assert len(score.factors) == 4
    assert all(f.reason for f in score.factors)
    assert score.reasons  # reason codes present


def test_value_score_low_for_thin_relationship(make_features, scoring_config) -> None:
    weak = make_features(
        aum_paise=0, product_depth=1, tenure_months=1, monthly_income_paise=to_paise(20_000)
    )
    assert score_value(weak, scoring_config).score < 25


def test_propensity_triggers_boost_score(make_features, products, scoring_config) -> None:
    product = products["PROD_PERSONAL_LOAN"]
    features = make_features()
    without = score_propensity(features, (), product, scoring_config)
    trigger = Trigger(key="emi_ending", detail="x", boost=12, reason="EMI ending soon")
    with_trigger = score_propensity(features, (trigger,), product, scoring_config)
    assert with_trigger.score > without.score
    assert with_trigger.triggers == (trigger,)


def test_propensity_penalizes_delinquency(make_features, products, scoring_config) -> None:
    product = products["PROD_PERSONAL_LOAN"]
    clean = score_propensity(make_features(max_dpd=0), (), product, scoring_config)
    delinquent = score_propensity(make_features(max_dpd=60), (), product, scoring_config)
    assert delinquent.score < clean.score
    delinquency_factor = next(f for f in delinquent.factors if f.key == "delinquency")
    assert delinquency_factor.contribution == 0


def test_propensity_score_bounded(make_features, products, scoring_config) -> None:
    product = products["PROD_PERSONAL_LOAN"]
    many = tuple(Trigger(key=k, detail="x", boost=12, reason=k) for k in ("a", "b", "c", "d", "e"))
    score = score_propensity(make_features(), many, product, scoring_config)
    assert 0 <= score.score <= 100
