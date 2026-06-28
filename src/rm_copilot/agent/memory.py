"""Conversational memory — working state spanning turns.

Holds the conversation history and the last result set so follow-ups ("why her?",
"redo in Hindi", "same segment but credit cards") can be resolved against prior
context. In-process for the demo; a store can back it later.
"""

from rm_copilot.agent.models import ProspectCard

_MAX_HISTORY_TURNS = 6
_MAX_LISTED_PROSPECTS = 10


class SessionMemory:
    def __init__(self) -> None:
        self.history: list[tuple[str, str]] = []  # (role, text)
        self.last_prospects: list[ProspectCard] = []
        self.last_product_id: str | None = None

    def record_user(self, text: str) -> None:
        self.history.append(("user", text))

    def record_agent(self, text: str) -> None:
        self.history.append(("agent", text))

    def store_results(self, prospects: list[ProspectCard], product_id: str | None) -> None:
        if prospects:
            self.last_prospects = prospects
        if product_id:
            self.last_product_id = product_id

    def snapshot(self) -> str:
        """Compact context for the Planner prompt (history + last results for references)."""
        lines: list[str] = []
        if self.last_product_id:
            lines.append(f"Last product discussed: {self.last_product_id}")
        if self.last_prospects:
            lines.append("Last result set (resolve references like 'her'/a name to a customer_id):")
            for p in self.last_prospects[:_MAX_LISTED_PROSPECTS]:
                lines.append(
                    f"  - {p.customer_id} | {p.first_name} | rec={p.recommended_product_id}"
                )
        if self.history:
            lines.append("Recent conversation:")
            for role, text in self.history[-_MAX_HISTORY_TURNS:]:
                lines.append(f"  {role}: {text}")
        return "\n".join(lines) if lines else "(no prior context)"
