"""RM Copilot — agentic AI assistant for a bank Relationship Manager.

Turns a natural-language RM request into an explainable workflow:
retrieve -> identify high-value -> estimate conversion propensity (incl. temporal
triggers) -> recommend product -> generate compliant, grounded outreach.

Authoritative design: ../../assessment-plan.md and ../../docs/data-model.md.

Layering (dependencies point inward toward `domain`):

    ui (outside pkg) -> agent -> tools -> services -> domain
                                  tools -> data    -> domain
    config feeds all layers; observability is a cross-cutting sink.

The LLM orchestrates and writes prose; deterministic services compute every
score, eligibility, recommendation, and guardrail decision. The model never
computes a score or invents a fact.
"""

__version__ = "0.0.0"
