"""Executor — the Act + Observe steps (deterministic interpreter of the Plan).

Realizes the planner's decisions over the deterministic tool registry and collects a
typed `Observation`. It imposes **no fixed pipeline**: whether outreach is generated,
how many, and whether retrieval or a current-set filter is used are all decisions the
Planner already made (`Plan.generate_messages`, `message_count`, `city`, `intent`). The
tools are deterministic; no LLM calls here (generation happens inside the generate tool).
"""

from rm_copilot.agent.memory import SessionMemory
from rm_copilot.agent.models import Intent, Observation, Plan, ProspectCard
from rm_copilot.agent.trace import Tracer
from rm_copilot.domain.enums import OutreachStatus
from rm_copilot.tools.registry import ToolRegistry

_RUN_ID = "agent"  # stable per (customer, product) → idempotent dry-run logging


def execute(
    registry: ToolRegistry,
    plan: Plan,
    memory: SessionMemory,
    tracer: Tracer,
    eligible_only: bool = True,
) -> Observation:
    match plan.intent:
        case Intent.PROSPECT:
            return _prospect(registry, plan, tracer, eligible_only)
        case Intent.FILTER:
            return _filter(plan, memory, tracer)
        case Intent.EXPLAIN:
            return _explain(registry, plan, memory.last_product_id, tracer)
        case Intent.REDRAFT:
            return _redraft(registry, plan, memory.last_product_id, tracer)
        case _:
            return Observation(note="no execution for this intent")


def _prospect(
    registry: ToolRegistry, plan: Plan, tracer: Tracer, eligible_only: bool
) -> Observation:
    args = {"product_id": plan.product_id, "top_n": plan.top_n, "eligible_only": eligible_only}
    found = registry.invoke("find_and_rank_prospects", args)
    tracer.add("tool", "find_and_rank_prospects", args=args, result=_summary(found))
    if found.get("is_error"):
        return Observation(error=f"{found['error']}: {found.get('detail')}")

    rows = found["prospects"][: plan.top_n]
    if plan.city:
        rows = [r for r in rows if _city_match(r.get("city"), plan.city)]

    # The planner owns whether/how many messages to draft. Draft only the top
    # `message_count` when generate_messages is set; the rest are listed (ranked only).
    draft_budget = plan.message_count if plan.generate_messages else 0
    cards: list[ProspectCard] = []
    for i, row in enumerate(rows):
        if i < draft_budget:
            cards.append(_draft_and_log(registry, plan, row, tracer))
        else:
            cards.append(_ranked_card(row))
    return Observation(prospects=cards, raw_count=found["count"])


def _filter(plan: Plan, memory: SessionMemory, tracer: Tracer) -> Observation:
    """Narrow the current result set in place (no re-ranking, no regeneration)."""
    base = list(memory.last_prospects)
    cards = base
    if plan.city:
        cards = [c for c in base if _city_match(c.city, plan.city)]
    tracer.add("act", "filter current result set", city=plan.city, kept=len(cards), of=len(base))
    if not base:
        return Observation(note="No prior result set to filter — search for prospects first.")
    note = None if cards else f"No prospects in the current set match city={plan.city!r}."
    return Observation(prospects=cards, raw_count=len(base), note=note)


def _city_match(value: str | None, target: str) -> bool:
    return bool(value) and value.casefold() == target.casefold()


def _explain(
    registry: ToolRegistry, plan: Plan, last_product_id: str | None, tracer: Tracer
) -> Observation:
    product_id = plan.product_id or last_product_id
    args = {"customer_id": plan.customer_id, "product_id": product_id}
    result = registry.invoke("explain_assessment", args)
    tracer.add("tool", "explain_assessment", args=args, result=_summary(result))
    if result.get("is_error"):
        return Observation(error=f"{result['error']}: {result.get('detail')}")
    return Observation(explanation=result)


def _redraft(
    registry: ToolRegistry, plan: Plan, last_product_id: str | None, tracer: Tracer
) -> Observation:
    product_id = plan.product_id or last_product_id
    row = {"customer_id": plan.customer_id, "recommended_product_id": product_id}
    plan_for_draft = plan.model_copy(update={"product_id": product_id})
    card = _draft_and_log(registry, plan_for_draft, row, tracer)
    return Observation(redrafted=card)


def _draft_and_log(
    registry: ToolRegistry,
    plan: Plan,
    row: dict,
    tracer: Tracer,
) -> ProspectCard:
    customer_id = row["customer_id"]
    gen_args = {
        "customer_id": customer_id,
        "product_id": plan.product_id,
        "locale": plan.locale,
        "tone": plan.tone,
    }
    gen = registry.invoke("generate_outreach_message", gen_args)
    tracer.add(
        "tool",
        "generate_outreach_message",
        args={"customer_id": customer_id, "locale": plan.locale},
        result=_summary(gen),
    )

    status = gen.get("status", OutreachStatus.SUPPRESSED.value)
    log_status = (
        OutreachStatus.DRY_RUN_SENT.value if status == OutreachStatus.READY.value else status
    )
    log = registry.invoke(
        "log_outreach",
        {
            "customer_id": customer_id,
            "product_id": plan.product_id,
            "run_id": _RUN_ID,
            "status": log_status,
            "message": gen.get("message"),
            "locale": gen.get("locale"),
            "tone": gen.get("tone"),
            "recommended_product_id": row.get("recommended_product_id"),
            "value_score": row.get("value_score"),
            "propensity_score": row.get("propensity_score"),
            "confidence": row.get("confidence"),
            "groundedness_passed": gen.get("grounded"),
            "compliance_passed": gen.get("compliant"),
            "regeneration_count": gen.get("regeneration_count"),
            "suppressed_reason": gen.get("suppressed_reason"),
            "assessment_snapshot": {
                "reason_codes": row.get("reason_codes"),
                "triggers": row.get("triggers"),
            },
        },
    )
    tracer.add(
        "tool",
        "log_outreach",
        args={"customer_id": customer_id, "status": log_status},
        result=_summary(log),
    )

    return ProspectCard(
        customer_id=customer_id,
        first_name=row.get("first_name", ""),
        city=row.get("city"),
        value_score=row.get("value_score", 0),
        propensity_score=row.get("propensity_score", 0),
        rank_score=row.get("rank_score", 0.0),
        confidence=row.get("confidence", ""),
        recommended_product_id=row.get("recommended_product_id"),
        triggers=row.get("triggers", []),
        reason_codes=row.get("reason_codes", []),
        message=gen.get("message"),
        message_status=status,
        outreach_id=log.get("outreach_id") if not log.get("is_error") else None,
    )


def _ranked_card(row: dict) -> ProspectCard:
    """A ranked candidate surfaced in the list without a drafted message (drafting is bounded)."""
    return ProspectCard(
        customer_id=row["customer_id"],
        first_name=row.get("first_name", ""),
        city=row.get("city"),
        value_score=row.get("value_score", 0),
        propensity_score=row.get("propensity_score", 0),
        rank_score=row.get("rank_score", 0.0),
        confidence=row.get("confidence", ""),
        recommended_product_id=row.get("recommended_product_id"),
        triggers=row.get("triggers", []),
        reason_codes=row.get("reason_codes", []),
        message=None,
        message_status="NOT_DRAFTED",
    )


def _summary(result: dict) -> dict:
    """A compact, trace-safe view of a tool result (no large payloads in the trace)."""
    if result.get("is_error"):
        return {"is_error": True, "error": result.get("error")}
    keys = ("count", "status", "grounded", "compliant", "outreach_id", "created", "eligible")
    summary = {k: result[k] for k in keys if k in result}
    if "prospects" in result:
        summary["prospects"] = len(result["prospects"])
    return summary
