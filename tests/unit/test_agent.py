"""Agent cognitive-loop trajectories — asserted with a scripted MockClient (no LLM).

Verifies the agent's plan, tool sequence, clarification, multi-turn memory, redraft,
and bounded reflect/adapt behavior — deterministically, with no network/token spend.
"""

from datetime import date

from rm_copilot.agent.drafter import LlmMessageDrafter
from rm_copilot.agent.llm.mock import MockClient
from rm_copilot.agent.memory import SessionMemory
from rm_copilot.agent.models import Intent, Plan, ReflectDecision
from rm_copilot.agent.orchestrator import Orchestrator
from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.data.database import Database
from rm_copilot.tools.registry import build_registry

AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"
# Compliant + grounded (no numeric claims) — the mock "LLM" returns this for drafts/synthesis.
COMPLIANT = "Hi there, you may be eligible (subject to eligibility). Reply STOP to opt out."


def _build(db: Database, plans, *, max_messages: int = 2) -> tuple[Orchestrator, MockClient]:
    client = MockClient(complete_text=COMPLIANT, structured_responses=plans)
    drafter = LlmMessageDrafter(client)
    registry = build_registry(db, load_scoring_config(), drafter, as_of=AS_OF)
    product_ids = [p.product_id for p in db.products.list_active()]
    return Orchestrator(registry, client, product_ids, max_message_count=max_messages), client


def _stages(result) -> list[str]:
    return [s.stage for s in result.trace]


def _tool_calls(result) -> list[str]:
    return [s.summary for s in result.trace if s.stage == "tool"]


def test_headline_prospect_and_outreach(seeded_db: Database) -> None:
    plan = Plan(
        intent=Intent.PROSPECT,
        product_id=PERSONAL_LOAN,
        top_n=5,
        generate_messages=True,
        message_count=2,
    )
    orch, _ = _build(seeded_db, [plan])
    result = orch.handle_turn(
        "Find high-value personal-loan prospects this month and message them", SessionMemory()
    )

    assert result.kind == "answer"
    # Full ranked list is surfaced (up to top_n); only the top `message_count` are drafted.
    assert 1 <= len(result.prospects) <= 5
    attempted = [p for p in result.prospects if p.message_status != "NOT_DRAFTED"]
    assert 1 <= len(attempted) <= 2  # drafting bounded to message_count
    assert any(p.message for p in attempted)  # at least one outreach drafted
    assert "find_and_rank_prospects" in _tool_calls(result)
    assert "generate_outreach_message" in _tool_calls(result)
    assert "log_outreach" in _tool_calls(result)
    assert "plan" in _stages(result) and "respond" in _stages(result)
    assert "reflect" not in _stages(result)  # no adaptation needed on a healthy result
    assert "elapsed_ms" in result.metrics and result.metrics["tool_calls"] >= 1  # per-turn metrics


def test_list_only_does_not_generate_messages(seeded_db: Database) -> None:
    # "List the top N" with no outreach request → ranked list, NO drafting (planner-owned).
    plan = Plan(intent=Intent.PROSPECT, product_id=PERSONAL_LOAN, top_n=5, generate_messages=False)
    orch, _ = _build(seeded_db, [plan])
    result = orch.handle_turn("List the top personal-loan customers", SessionMemory())

    assert result.kind == "answer"
    assert result.prospects  # full ranked list is surfaced
    assert all(p.message_status == "NOT_DRAFTED" for p in result.prospects)
    assert all(p.message is None for p in result.prospects)
    assert "generate_outreach_message" not in _tool_calls(result)  # no outreach this turn
    assert "log_outreach" not in _tool_calls(result)


def test_filter_narrows_current_set_without_reranking(seeded_db: Database) -> None:
    # List prospects (populates memory), then filter by a city — no re-rank, no regenerate.
    memory = SessionMemory()
    orch, _ = _build(seeded_db, [Plan(intent=Intent.PROSPECT, product_id=PERSONAL_LOAN, top_n=10)])
    first = orch.handle_turn("list personal-loan prospects", memory)
    assert first.prospects
    target_city = first.prospects[0].city
    assert target_city

    orch2, _ = _build(seeded_db, [Plan(intent=Intent.FILTER, city=target_city)])
    result = orch2.handle_turn(f"show only the ones from {target_city}", memory)

    assert result.kind == "answer"
    assert result.prospects  # the top prospect matches its own city
    assert all((c.city or "").casefold() == target_city.casefold() for c in result.prospects)
    assert "find_and_rank_prospects" not in _tool_calls(result)  # filtered in place, no re-ranking
    assert "generate_outreach_message" not in _tool_calls(result)  # no regeneration


def test_clarification_on_ambiguous_request(seeded_db: Database) -> None:
    plan = Plan(intent=Intent.CLARIFY, clarification_question="Which product should I target?")
    orch, _ = _build(seeded_db, [plan])
    result = orch.handle_turn("find me some good customers", SessionMemory())

    assert result.kind == "clarification"
    assert result.reply == "Which product should I target?"
    assert "tool" not in _stages(result)  # asked before acting — no tools invoked


def test_unsupported_request_is_declined(seeded_db: Database) -> None:
    orch, _ = _build(seeded_db, [Plan(intent=Intent.UNSUPPORTED)])
    result = orch.handle_turn("delete customer CUST000001", SessionMemory())
    assert result.kind == "declined"
    assert "tool" not in _stages(result)


def test_multi_turn_explain_uses_memory(seeded_db: Database) -> None:
    plans = [
        Plan(intent=Intent.PROSPECT, product_id=PERSONAL_LOAN, top_n=5, message_count=2),
        Plan(intent=Intent.EXPLAIN, customer_id="CUST000001", product_id=PERSONAL_LOAN),
    ]
    orch, _ = _build(seeded_db, plans)
    memory = SessionMemory()
    orch.handle_turn("find personal-loan prospects", memory)  # populates memory
    result = orch.handle_turn("why CUST000001?", memory)

    assert result.kind == "answer"
    assert result.explanation is not None
    assert "explain_assessment" in _tool_calls(result)


def test_redraft_in_hindi(seeded_db: Database) -> None:
    plan = Plan(
        intent=Intent.REDRAFT, customer_id="CUST000001", product_id=PERSONAL_LOAN, locale="hi_IN"
    )
    orch, _ = _build(seeded_db, [plan])
    result = orch.handle_turn("redo CUST000001's message in Hindi", SessionMemory())

    assert result.kind == "answer"
    assert "generate_outreach_message" in _tool_calls(result)


def test_reflect_and_adapt_on_empty_result(seeded_db: Database) -> None:
    # Everyone already holds SAVINGS → eligible set is empty → the agent must reflect + adapt.
    plan = Plan(intent=Intent.PROSPECT, product_id="PROD_SAVINGS", top_n=5, message_count=2)
    decision = ReflectDecision(
        should_retry=True, adjusted_eligible_only=False, note="surface near-misses"
    )
    orch, _ = _build(seeded_db, [plan, decision])
    result = orch.handle_turn("find savings prospects this month", SessionMemory())

    reflect_steps = [s for s in result.trace if s.stage == "reflect"]
    assert len(reflect_steps) == 1  # bounded — exactly one re-plan
    assert result.prospects  # adaptation (eligible_only=False) surfaced candidates
