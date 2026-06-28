"""Tools layer — the agent's typed action space + registry (the "tools" the rubric names).

Thin, schema-validated wrappers over services/repositories. Per assessment-plan.md
§14 the agent-facing surface is intentionally small (5 tools):
  find_and_rank_prospects, get_customer_360, explain_assessment,
  generate_outreach_message, log_outreach.

Rules:
- Pydantic-typed inputs/outputs; JSON schemas exposed via the registry.
- Tool errors return structured `is_error` results so the model can self-correct.
- Adding a tool = new class + one registry entry; the orchestrator does not change.
- All tools deterministic EXCEPT generate_outreach_message (LLM), which wraps
  groundedness + compliance guardrails internally so they cannot be skipped.

Implemented (M3): base Tool contract + ToolError, the five tools, and the
ToolRegistry / build_registry. The generation tool's LLM drafter is injected
(MessageDrafter protocol); the real LLM implementation arrives in M4.
"""
