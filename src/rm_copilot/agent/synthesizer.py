"""Synthesizer — the Respond step (LLM cognition, grounded).

Composes the RM-facing markdown answer from the structured `Observation`, using only the
deterministic data (scores, reason codes, drafted messages). It synthesizes prose over
facts; it does not recompute or invent anything.
"""

import json

from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.models import Observation, Plan
from rm_copilot.agent.prompts import load_prompt


def synthesize(client: LLMClient, plan: Plan, observation: Observation) -> str:
    payload = _payload(plan, observation)
    prompt = (
        f"Intent: {plan.intent.value}\n\n"
        f"Structured results (use ONLY this data):\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
        f"Write the markdown summary for the RM."
    )
    return client.complete(system=load_prompt("respond"), prompt=prompt, max_output_tokens=1500)


def _payload(plan: Plan, observation: Observation) -> dict:
    if observation.explanation is not None:
        return {"explanation": observation.explanation}
    if observation.redrafted is not None:
        return {"redrafted": observation.redrafted.model_dump()}
    payload = {
        "reviewed": observation.raw_count,
        "shortlisted": len(observation.prospects),
        "prospects": [p.model_dump() for p in observation.prospects],
    }
    if observation.note:
        payload["note"] = observation.note
    return payload
