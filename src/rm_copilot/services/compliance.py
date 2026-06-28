"""Compliance guardrail — validate an outreach message against banking rules
(data-model §9.3). Deterministic; no LLM.

Implemented now (M2); consumed by the generation tool in M4, which regenerates on
failure. Operates purely on a message string + customer + config.
"""

import re

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.domain.assessment import ComplianceResult

# PAN format: 5 letters, 4 digits, 1 letter (full PAN must never appear in a message).
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")


def check_compliance(message: str, config: ScoringConfig) -> ComplianceResult:
    """Check a drafted message for compliance violations."""
    cfg = config.compliance
    lower = message.lower()
    violations: list[str] = []

    for phrase in cfg.banned_phrases:
        if phrase.lower() in lower:
            violations.append(f"banned phrase: '{phrase}'")

    if cfg.require_opt_out and not any(m.lower() in lower for m in cfg.opt_out_markers):
        violations.append("missing opt-out instruction")

    if len(message) > cfg.max_chars:
        violations.append(f"message too long ({len(message)} > {cfg.max_chars} chars)")

    if _PAN_RE.search(message):
        violations.append("contains a full PAN (PII leak)")

    return ComplianceResult(passed=not violations, violations=tuple(violations))
