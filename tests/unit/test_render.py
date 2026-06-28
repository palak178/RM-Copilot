"""Presentation/render helpers (shared by CLI + Streamlit)."""

from rm_copilot.agent.models import AgentResult, Intent, Plan, ProspectCard
from rm_copilot.agent.trace import TraceStep
from rm_copilot.observability.render import (
    COGNITIVE_LOOP,
    amount,
    console_metrics,
    loop_stage,
    loop_state,
    prospect_headline,
    render_result_text,
    render_trace_lines,
    step_durations,
    tool_status,
)


def test_render_trace_lines_ordered_and_detailed() -> None:
    trace = [
        TraceStep(seq=1, stage="plan", summary="intent=prospect_and_outreach"),
        TraceStep(seq=2, stage="tool", summary="find_and_rank_prospects", data={"count": 5}),
    ]
    lines = render_trace_lines(trace)
    assert len(lines) == 2
    assert "plan" in lines[0]
    assert "find_and_rank_prospects" in lines[1] and "count" in lines[1]


def test_amount_is_none_safe() -> None:
    assert amount(None) == "—"
    assert amount(82_00_000_00).startswith("₹")  # ₹82L


def test_render_result_text_includes_reply_and_trace() -> None:
    result = AgentResult(
        kind="answer",
        reply="# Recommendations",
        intent="prospect_and_outreach",
        plan=Plan(intent=Intent.PROSPECT),
        trace=[TraceStep(seq=1, stage="respond", summary="grounded synthesis")],
    )
    text = render_result_text(result)
    assert "# Recommendations" in text
    assert "reasoning trace" in text
    assert "respond" in text


def test_prospect_headline() -> None:
    card = ProspectCard(
        customer_id="CUST000001",
        first_name="Priya",
        value_score=80,
        propensity_score=90,
        rank_score=86.0,
        confidence="HIGH",
        recommended_product_id="PROD_PERSONAL_LOAN",
        triggers=[],
        reason_codes=[],
        message_status="READY",
    )
    headline = prospect_headline(card)
    assert "Priya" in headline and "CUST000001" in headline and "READY" in headline


# --- Agent Console helpers ------------------------------------------------------------
def test_loop_stage_maps_tool_to_act() -> None:
    assert loop_stage("tool") == "act"
    assert loop_stage("plan") == "plan"


def test_loop_state_active_done_pending() -> None:
    trace = [
        TraceStep(seq=1, stage="perceive", summary="", at_ms=0),
        TraceStep(seq=2, stage="plan", summary="", at_ms=10),
        TraceStep(seq=3, stage="tool", summary="find_and_rank_prospects", at_ms=130),
    ]
    live = loop_state(trace, final=False)
    assert live["perceive"] == "done"
    assert live["plan"] == "done"
    assert live["act"] == "active"  # last step is a tool → Act phase, still running
    assert live["observe"] == "pending"
    assert live["reflect"] == "pending"  # never ran → not falsely shown as done
    done = loop_state(trace, final=True)
    assert done["act"] == "done"


def test_step_durations_from_offsets_and_tail() -> None:
    trace = [
        TraceStep(seq=1, stage="perceive", summary="", at_ms=0),
        TraceStep(seq=2, stage="plan", summary="", at_ms=200),
        TraceStep(seq=3, stage="tool", summary="x", at_ms=500),
    ]
    durs = step_durations(trace, total_ms=900)
    assert durs[0] == 0
    assert durs[1] == 200
    assert durs[2] == 700  # 300ms gap (500-200) + 400ms tail (900-500) attributed to last step


def test_tool_status_outcomes() -> None:
    assert tool_status({"is_error": True})[0] == "❌"
    assert tool_status({"status": "READY"})[0] == "✅"
    assert tool_status({"status": "COMPLIANCE_FAILED"})[0] == "⚠️"
    assert tool_status({"status": "SUPPRESSED"})[0] == "🚫"


def test_console_metrics_derived_from_trace() -> None:
    result = AgentResult(
        kind="answer",
        reply="ok",
        intent="prospect_and_outreach",
        plan=Plan(intent=Intent.PROSPECT),
        trace=[
            TraceStep(seq=1, stage="plan", summary=""),
            TraceStep(seq=2, stage="tool", summary="find_and_rank_prospects"),
            TraceStep(seq=3, stage="reflect", summary=""),
            TraceStep(seq=4, stage="respond", summary=""),
        ],
        metrics={"elapsed_ms": 1234, "tool_calls": 1},
    )
    m = console_metrics(result, conversation_turns=2)
    assert m["tool_calls"] == 1
    assert m["reflection_cycles"] == 1
    assert m["cognition_steps"] == 3  # plan + reflect + synthesis (answer)
    assert m["conversation_turns"] == 2
    assert m["tokens"] is None


def test_cognitive_loop_has_six_stages() -> None:
    assert COGNITIVE_LOOP == ("perceive", "plan", "act", "observe", "reflect", "respond")
