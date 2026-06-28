"""Compliance and groundedness guardrails."""

from rm_copilot.services.compliance import check_compliance
from rm_copilot.services.groundedness import check_groundedness

GOOD_MESSAGE = (
    "Hi Priya, your auto-loan EMI ends soon, freeing up ~₹12,400/mo. You may be "
    "eligible for a Personal Loan (indicative, subject to eligibility). "
    "Reply STOP to opt out."
)


def test_compliant_message_passes(scoring_config) -> None:
    assert check_compliance(GOOD_MESSAGE, scoring_config).passed


def test_banned_phrase_fails(scoring_config) -> None:
    msg = "You are pre-approved for a guaranteed loan! Reply STOP to opt out."
    result = check_compliance(msg, scoring_config)
    assert not result.passed
    assert any("banned phrase" in v for v in result.violations)


def test_missing_opt_out_fails(scoring_config) -> None:
    msg = "Hi Priya, you may be eligible for a Personal Loan."
    result = check_compliance(msg, scoring_config)
    assert not result.passed
    assert any("opt-out" in v for v in result.violations)


def test_full_pan_fails(scoring_config) -> None:
    msg = "Hi, your PAN ABCDE1234F qualifies. Reply STOP to opt out."
    result = check_compliance(msg, scoring_config)
    assert not result.passed
    assert any("PAN" in v for v in result.violations)


def test_too_long_fails(scoring_config) -> None:
    msg = "STOP " + "x" * 800
    result = check_compliance(msg, scoring_config)
    assert not result.passed
    assert any("too long" in v for v in result.violations)


def test_grounded_message_passes() -> None:
    facts = ["Loan EMI ends 2026-07-10 → ~₹12,400/mo freed", "indicative rate 11.5%"]
    msg = "Your EMI of ₹12,400/mo frees up; indicative rate 11.5%."
    result = check_groundedness(msg, facts)
    assert result.grounded
    assert result.unsupported_claims == ()


def test_ungrounded_number_fails() -> None:
    facts = ["EMI ~₹12,400/mo freed"]
    msg = "You can borrow ₹9,99,999 today."
    result = check_groundedness(msg, facts)
    assert not result.grounded
    assert result.unsupported_claims
