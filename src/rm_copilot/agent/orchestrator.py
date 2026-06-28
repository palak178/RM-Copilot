"""Orchestrator — the cognitive loop (the primary architectural component).

Wires Perceive → Plan → Act → Observe → Reflect → Respond, with conversational Memory
across turns (ADR-0005). The LLM does cognition (plan / clarify / reflect / synthesize);
the deterministic registry + services do execution. Bounded: message count is capped and
at most one reflect-driven re-plan per turn.
"""

import time
from collections.abc import Callable, Sequence

from rm_copilot.agent import executor, planner, reflector, synthesizer
from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.memory import SessionMemory
from rm_copilot.agent.models import AgentResult, Intent, Observation, Plan
from rm_copilot.agent.trace import Tracer, TraceStep
from rm_copilot.tools.registry import ToolRegistry

_DECLINE = (
    "That's outside what I can help with here. I can find high-potential customers for a "
    "product, explain why a customer was chosen, and draft personalized outreach."
)


class Orchestrator:
    """A single agent running the cognitive loop over deterministic tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        client: LLMClient,
        product_ids: Sequence[str],
        max_message_count: int = 3,
    ) -> None:
        self._registry = registry
        self._client = client
        self._product_ids = list(product_ids)
        self._max_message_count = max_message_count

    def handle_turn(
        self,
        message: str,
        memory: SessionMemory,
        on_trace: Callable[[TraceStep], None] | None = None,
    ) -> AgentResult:
        tracer = Tracer(on_step=on_trace)
        started = time.perf_counter()

        def _metrics() -> dict:
            return {
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "tool_calls": sum(1 for s in tracer.steps if s.stage == "tool"),
            }

        # 1. Perceive
        tracer.add("perceive", "read request + memory", history_turns=len(memory.history))
        memory.record_user(message)

        # 2. Plan (LLM, structured) — the planner owns the workflow shape for this turn.
        plan = planner.make_plan(
            self._client, message, memory, self._product_ids, self._registry.names()
        )
        tracer.add(
            "plan",
            f"intent={plan.intent.value}",
            intent=plan.intent.value,
            product_id=plan.product_id,
            customer_id=plan.customer_id,
            top_n=plan.top_n,
            generate_messages=plan.generate_messages,
            message_count=plan.message_count if plan.generate_messages else 0,
            city=plan.city,
            assumptions=plan.assumptions,
            tool_plan=plan.tool_plan,
        )

        # Deterministic policy: bound per-turn drafting and surface the decision (don't
        # silently truncate). The planner may request more; the agent explains the cap.
        policy_note: str | None = None
        if plan.generate_messages and plan.message_count > self._max_message_count:
            requested = plan.message_count
            plan.message_count = self._max_message_count
            policy_note = (
                f"You asked to draft {requested} messages; I drafted the top "
                f"{plan.message_count} this turn (a per-turn cap for cost and review quality) "
                f"and listed the remaining ranked candidates. Ask me to continue for the next batch."
            )
            tracer.add(
                "plan",
                "policy: per-turn message cap applied",
                requested=requested,
                cap=plan.message_count,
            )

        if plan.intent == Intent.CLARIFY or plan.clarification_question:
            question = (
                plan.clarification_question
                or "Which product and customer segment should I focus on?"
            )
            tracer.add("respond", "ask for clarification")
            memory.record_agent(question)
            return AgentResult(
                kind="clarification",
                reply=question,
                intent=plan.intent.value,
                plan=plan,
                trace=tracer.steps,
                metrics=_metrics(),
            )

        if plan.intent == Intent.UNSUPPORTED:
            tracer.add("respond", "decline (out of scope)")
            memory.record_agent(_DECLINE)
            return AgentResult(
                kind="declined",
                reply=_DECLINE,
                intent=plan.intent.value,
                plan=plan,
                trace=tracer.steps,
                metrics=_metrics(),
            )

        # 3-4. Act + Observe
        obs = executor.execute(self._registry, plan, memory, tracer)
        tracer.add(
            "observe", f"prospects={len(obs.prospects)} reviewed={obs.raw_count}", error=obs.error
        )

        # 5. Reflect (bounded: one re-plan) — only for prospecting that came back empty
        if plan.intent == Intent.PROSPECT and not obs.prospects and obs.error is None:
            obs = self._reflect_and_retry(plan, obs, tracer, memory)

        # 6. Respond
        if obs.error is not None:
            reply = f"I couldn't complete that request ({obs.error}). Please check the product or customer and try again."
            tracer.add("respond", "graceful error")
        else:
            reply = synthesizer.synthesize(self._client, plan, obs)
            if policy_note:
                reply = f"{reply}\n\n_{policy_note}_"
            tracer.add("respond", "grounded synthesis")

        memory.store_results(obs.prospects, plan.product_id)
        memory.record_agent(reply)
        return AgentResult(
            kind="answer",
            reply=reply,
            intent=plan.intent.value,
            plan=plan,
            prospects=obs.prospects,
            explanation=obs.explanation,
            trace=tracer.steps,
            metrics=_metrics(),
        )

    def _reflect_and_retry(
        self, plan: Plan, obs: Observation, tracer: Tracer, memory: SessionMemory
    ) -> Observation:
        decision = reflector.reflect(self._client, plan, obs)
        tracer.add("reflect", f"retry={decision.should_retry}", note=decision.note)
        if not decision.should_retry:
            return obs
        if decision.adjusted_top_n:
            plan.top_n = min(decision.adjusted_top_n, 50)
        eligible_only = (
            decision.adjusted_eligible_only if decision.adjusted_eligible_only is not None else True
        )
        retried = executor.execute(
            self._registry, plan, memory, tracer, eligible_only=eligible_only
        )
        tracer.add(
            "observe", f"(retry) prospects={len(retried.prospects)} reviewed={retried.raw_count}"
        )
        return retried
