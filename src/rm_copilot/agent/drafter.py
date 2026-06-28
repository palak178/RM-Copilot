"""LLM-backed message drafter — bridges the provider-agnostic LLMClient to the
tool layer's MessageDrafter protocol.

The generation tool injects this; it depends only on `LLMClient` (never on a
provider SDK). Deterministic groundedness + compliance guardrails run in the tool
AFTER drafting, so this stays a thin, fact-bounded prompt builder.
"""

from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.prompts import load_prompt
from rm_copilot.tools.generate_outreach import DraftContext


class LlmMessageDrafter:
    """A MessageDrafter (duck-typed) backed by any LLMClient."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def draft(self, context: DraftContext) -> str:
        system = load_prompt("generate_outreach")
        return self._client.complete(system=system, prompt=_build_prompt(context))


def _build_prompt(context: DraftContext) -> str:
    facts = "\n".join(f"- {fact}" for fact in context.facts)
    return (
        f"Customer first name: {context.first_name}\n"
        f"Product: {context.product_name}\n"
        f"Locale: {context.locale}\n"
        f"Tone: {context.tone}\n\n"
        f"Facts you may use (and only these):\n{facts}\n\n"
        f"Draft the WhatsApp message now."
    )
