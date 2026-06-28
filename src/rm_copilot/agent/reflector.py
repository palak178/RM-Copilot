"""Reflector — the Reflect step (LLM cognition, bounded).

Invoked only when an observation is empty/ineligible. Decides whether a single
bounded re-query (broaden eligibility / widen N) is worthwhile. Never changes scores
or eligibility rules — only whether and how to re-query.
"""

from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.models import Observation, Plan, ReflectDecision
from rm_copilot.agent.prompts import load_prompt


def reflect(client: LLMClient, plan: Plan, observation: "Observation") -> ReflectDecision:
    prompt = (
        f"Request intent: {plan.intent.value}; product: {plan.product_id}; top_n: {plan.top_n}.\n"
        f"Observation: {observation.raw_count} candidate(s) found, "
        f"{len(observation.prospects)} eligible prospect(s). The request was not satisfied.\n"
        f"Decide whether to retry with broadened parameters."
    )
    return client.structured(system=load_prompt("reflect"), prompt=prompt, schema=ReflectDecision)
