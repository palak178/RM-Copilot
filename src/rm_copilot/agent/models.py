"""Agent I/O models — the structured shapes the cognitive loop reasons with.

These are the agent layer's own value objects (distinct from `domain`): the Planner
output, the Reflector decision, per-customer result cards, and the turn result.
Pydantic is appropriate here — `Plan`/`ReflectDecision` are structured-output schemas.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from rm_copilot.agent.trace import TraceStep


class Intent(StrEnum):
    """What the agent decided the RM is asking for (the planner owns this choice)."""

    PROSPECT = "prospect"  # find & rank customers; outreach happens only if generate_messages
    FILTER = "filter"  # narrow the current result set (e.g. by city) without re-ranking
    EXPLAIN = "explain"  # "why her?" — explain a specific customer (uses memory)
    REDRAFT = "redraft"  # "redo in Hindi" — rewrite a message (uses memory)
    CLARIFY = "clarify"  # request underspecified — ask a question
    UNSUPPORTED = "unsupported"  # out of scope — decline


class Plan(BaseModel):
    """The Planner's structured output (LLM cognition) — the source of truth for the turn.

    The planner decides the whole workflow shape: which intent, how many to rank, whether
    outreach is generated and how many, and any filter. The executor deterministically
    realizes these decisions — it does not impose a fixed retrieve→draft pipeline.
    """

    intent: Intent
    rationale: str = ""
    product_id: str | None = None
    top_n: int = Field(default=10, ge=1, le=50)
    generate_messages: bool = (
        False  # planner decides whether outreach drafting is part of this turn
    )
    message_count: int = Field(default=3, ge=1, le=25)  # how many to draft (when generate_messages)
    city: str | None = None  # optional location filter (retrieval or current-set filter)
    locale: str | None = None
    tone: str = "friendly"
    customer_id: str | None = None  # resolved from memory for follow-ups
    assumptions: list[str] = []
    tool_plan: list[str] = []  # advisory/inspectable
    clarification_question: str | None = None


class ReflectDecision(BaseModel):
    """The Reflector's bounded decision after an empty/ineligible observation."""

    should_retry: bool
    adjusted_top_n: int | None = None
    adjusted_eligible_only: bool | None = None
    note: str = ""


class ProspectCard(BaseModel):
    """A surfaced customer with scores, reason codes, and the drafted outreach."""

    customer_id: str
    first_name: str
    city: str | None = None
    value_score: int
    propensity_score: int
    rank_score: float
    confidence: str
    recommended_product_id: str | None
    triggers: list[str]
    reason_codes: list[str]
    message: str | None = None
    message_status: str | None = None
    outreach_id: str | None = None


class Observation(BaseModel):
    """What the Executor saw after acting (the Observe step's input)."""

    prospects: list[ProspectCard] = []
    raw_count: int = 0
    explanation: dict | None = None
    redrafted: ProspectCard | None = None
    error: str | None = None
    note: str | None = None


class AgentResult(BaseModel):
    """The outcome of one turn — what the UI/API renders."""

    kind: Literal["answer", "clarification", "declined"]
    reply: str
    intent: str
    plan: Plan
    prospects: list[ProspectCard] = []
    explanation: dict | None = None
    trace: list[TraceStep]
    metrics: dict = Field(default_factory=dict)  # elapsed_ms, tool_calls (tokens/cost: future)
