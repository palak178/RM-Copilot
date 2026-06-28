"""Groundedness check — every concrete figure in a message must trace to the facts
passed to the generator (data-model §9.4). Deterministic; no LLM.

Anti-hallucination guardrail: extracts monetary amounts and percentages from the
drafted message and verifies each appears in the supplied facts. Implemented now
(M2); consumed by the generation tool in M4 (regenerate on failure).
"""

import re

from rm_copilot.domain.assessment import GroundednessResult

# ₹-amounts (e.g. ₹12,400 / ₹8.20L / ₹1.5Cr) and bare percentages (e.g. 11.5%).
_AMOUNT_RE = re.compile(r"₹\s?[\d][\d,\.]*\s?(?:Cr|L|K|Lakh|Crore)?", re.IGNORECASE)
_PERCENT_RE = re.compile(r"\d[\d,\.]*\s?%")


def _digits(token: str) -> str:
    return re.sub(r"[^\d]", "", token)


def check_groundedness(message: str, facts: list[str]) -> GroundednessResult:
    """Verify every monetary/percentage figure in the message is supported by facts."""
    facts_blob = " ".join(facts)
    fact_digit_strings = {_digits(tok) for tok in _AMOUNT_RE.findall(facts_blob)}
    fact_digit_strings |= {_digits(tok) for tok in _PERCENT_RE.findall(facts_blob)}
    fact_digit_strings.discard("")

    claims = _AMOUNT_RE.findall(message) + _PERCENT_RE.findall(message)
    unsupported = [
        claim.strip()
        for claim in claims
        if _digits(claim) and _digits(claim) not in fact_digit_strings
    ]
    return GroundednessResult(grounded=not unsupported, unsupported_claims=tuple(unsupported))
