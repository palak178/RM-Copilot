"""Presentation helpers — format the agent's trace and results for display.

Pure functions (no UI framework, no I/O) so the CLI, the Streamlit app, and tests all
share one rendering. This is the observability layer's "timeline/trace formatting" role.
"""

from rm_copilot.agent.models import AgentResult, ProspectCard
from rm_copilot.agent.trace import TraceStep
from rm_copilot.domain.money import format_inr

_STAGE_GLYPH = {
    "perceive": "👁",
    "plan": "🧭",
    "act": "⚙",
    "tool": "🔧",
    "observe": "🔍",
    "reflect": "↻",
    "respond": "🗣",
}

# --- Agent Console helpers (used by the Streamlit "Agent Console" UI) -----------------
# The six stages of the cognitive loop, in canonical order (ADR-0005). Tool calls are
# emitted during the Act phase, so the "tool" trace stage maps onto "act".
COGNITIVE_LOOP: tuple[str, ...] = ("perceive", "plan", "act", "observe", "reflect", "respond")
_TRACE_TO_LOOP = {"tool": "act"}

# One-line "why this tool ran" labels, keyed by tool name (presentation only).
TOOL_PURPOSE: dict[str, str] = {
    "find_and_rank_prospects": "Retrieve, score (value + propensity) & rank candidates",
    "get_customer_360": "Pull the full customer profile & history",
    "explain_assessment": "Break down the assessment into reason codes",
    "generate_outreach_message": "Draft a grounded, compliance-checked message",
    "log_outreach": "Record the decision (simulated WhatsApp send) in the audit log",
}


def loop_stage(trace_stage: str) -> str:
    """Map a trace stage onto its cognitive-loop phase (e.g. ``tool`` → ``act``)."""
    return _TRACE_TO_LOOP.get(trace_stage, trace_stage)


def loop_state(trace: list[TraceStep], *, final: bool) -> dict[str, str]:
    """Per-stage status for the loop bar: ``done`` | ``active`` | ``pending``.

    A stage is ``done`` once it has appeared in the trace; the most recent stage is
    ``active`` while the turn runs (``final=False``) and ``done`` once it completes.
    Stages that never ran (e.g. Reflect on a clean turn) stay ``pending`` — which is
    truthful: the loop only reflects when an observation warrants it.
    """
    seen = [loop_stage(s.stage) for s in trace]
    current = seen[-1] if seen else None
    state: dict[str, str] = {}
    for stage in COGNITIVE_LOOP:
        if stage == current and not final:
            state[stage] = "active"
        elif stage in seen:
            state[stage] = "done"
        else:
            state[stage] = "pending"
    return state


def step_durations(trace: list[TraceStep], total_ms: int | None = None) -> list[int]:
    """Per-step durations in ms, derived from ``at_ms`` offsets (gap to previous step)."""
    durations: list[int] = []
    prev = 0
    for step in trace:
        durations.append(max(step.at_ms - prev, 0))
        prev = step.at_ms
    if durations and total_ms is not None and total_ms > prev:
        durations[-1] += total_ms - prev  # attribute the tail (e.g. synthesis) to the last step
    return durations


def tool_status(result_summary: dict) -> tuple[str, str]:
    """A (glyph, label) status for a tool result summary (from the trace's ``result``)."""
    if result_summary.get("is_error"):
        return "❌", "error"
    status = result_summary.get("status")
    if status in ("COMPLIANCE_FAILED", "GROUNDEDNESS_FAILED"):
        return "⚠️", status
    if status == "SUPPRESSED":
        return "🚫", "suppressed"
    return "✅", str(status or "ok")


def console_metrics(result: AgentResult, conversation_turns: int) -> dict[str, object]:
    """Runtime metrics for the Agent Console, derived from the result + trace.

    Token/cost metering is not yet plumbed through the provider clients, so it is
    reported as unavailable rather than estimated.
    """
    trace = result.trace
    reflection_cycles = sum(1 for s in trace if s.stage == "reflect")
    tool_calls = result.metrics.get("tool_calls", sum(1 for s in trace if s.stage == "tool"))
    # Distinct LLM cognition stages: planning, each reflection, and (when answered) synthesis.
    cognition_steps = sum(1 for s in trace if s.stage in ("plan", "reflect"))
    if result.kind == "answer":
        cognition_steps += 1
    return {
        "elapsed_ms": result.metrics.get("elapsed_ms"),
        "tool_calls": tool_calls,
        "reflection_cycles": reflection_cycles,
        "cognition_steps": cognition_steps,
        "conversation_turns": conversation_turns,
        "tokens": None,  # not tracked yet (see roadmap)
    }


def render_trace_lines(trace: list[TraceStep]) -> list[str]:
    """One readable line per reasoning step (for the CLI / a plain timeline)."""
    lines: list[str] = []
    for step in trace:
        glyph = _STAGE_GLYPH.get(step.stage, "•")
        extra = f"  {step.data}" if step.data else ""
        lines.append(f"{glyph} [{step.seq}] {step.stage}: {step.summary}{extra}")
    return lines


def prospect_headline(card: ProspectCard) -> str:
    """A one-line summary of a prospect card."""
    return (
        f"{card.first_name} ({card.customer_id}) — value {card.value_score}, "
        f"propensity {card.propensity_score}, {card.confidence} confidence "
        f"→ {card.recommended_product_id or 'no recommendation'} [{card.message_status}]"
    )


def render_result_text(result: AgentResult) -> str:
    """A plain-text rendering of a full turn (reply + trace) for the CLI."""
    blocks = [result.reply.strip(), "", "── reasoning trace ──", *render_trace_lines(result.trace)]
    return "\n".join(blocks)


def amount(paise: int | None) -> str:
    """Convenience ₹ formatter for UIs (None-safe)."""
    return format_inr(paise) if paise is not None else "—"
