"""LLMClient abstraction — the provider-agnostic capabilities the app needs.

Two capabilities:
- ``complete`` — single-shot text generation (used by the message drafter).
- ``generate`` — one tool-use turn over normalized messages (used by the M4
  orchestrator loop). Returns either text or tool calls; the loop itself lives in
  the orchestrator, not here.

Normalized request/response types isolate the app from provider wire formats.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """A normalized conversation message.

    - USER/ASSISTANT carry ``text``.
    - An ASSISTANT turn that called tools carries ``tool_calls``.
    - A TOOL message carries a tool result (``tool_name`` + ``text``).
    """

    role: Role
    text: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Result of one model turn."""

    text: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use"


class LLMClient(ABC):
    """A provider-agnostic LLM. Business logic depends only on this type."""

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def complete(self, *, system: str, prompt: str, max_output_tokens: int = 1024) -> str:
        """Return plain text for a single system + user prompt."""

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        max_output_tokens: int = 2048,
    ) -> LLMResponse:
        """Run one turn; may return tool calls. ``tools`` are registry JSON schemas."""

    @abstractmethod
    def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """Return a validated instance of ``schema`` via constrained/JSON-schema decoding.

        Used for the agent's Planner and Reflector (cognition with a fixed output shape).
        """
