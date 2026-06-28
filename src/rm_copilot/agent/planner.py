"""Planner — the Plan step (LLM cognition, structured output).

Decomposes the RM request into intent + parameters, resolves follow-up references from
memory, and decides clarify-vs-proceed. Produces a `Plan`; never executes anything.
"""

from collections.abc import Sequence

from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.memory import SessionMemory
from rm_copilot.agent.models import Plan
from rm_copilot.agent.prompts import load_prompt


def make_plan(
    client: LLMClient,
    message: str,
    memory: SessionMemory,
    product_ids: Sequence[str],
    tool_names: Sequence[str],
) -> Plan:
    prompt = (
        f"RM request:\n{message}\n\n"
        f"Context:\n{memory.snapshot()}\n\n"
        f"Available product ids: {', '.join(product_ids)}\n"
        f"Available tools: {', '.join(tool_names)}\n\n"
        f"Produce the plan."
    )
    return client.structured(system=load_prompt("plan"), prompt=prompt, schema=Plan)
