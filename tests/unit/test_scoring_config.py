"""The scoring config loads and is internally consistent."""

import math

from rm_copilot.config.scoring import ScoringConfig, load_scoring_config


def test_loads_default_config() -> None:
    cfg = load_scoring_config()
    assert isinstance(cfg, ScoringConfig)


def test_weights_sum_to_one() -> None:
    cfg = load_scoring_config()
    assert math.isclose(sum(cfg.value.weights.values()), 1.0, abs_tol=1e-6)
    assert math.isclose(sum(cfg.propensity.weights.values()), 1.0, abs_tol=1e-6)
    assert math.isclose(cfg.ranking.value_weight + cfg.ranking.propensity_weight, 1.0, abs_tol=1e-6)


def test_trigger_boosts_present() -> None:
    cfg = load_scoring_config()
    for key in ("emi_ending", "fd_maturing", "large_outflow", "salary_hike", "festival_window"):
        assert key in cfg.propensity.trigger_boosts
