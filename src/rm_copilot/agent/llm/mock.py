"""MockClient — deterministic, in-memory LLM for tests. No network, no SDK.

- `complete` returns a fixed string (or a callable's output).
- `generate` replays a scripted list of LLMResponses, then a terminal end_turn.
- `structured` replays a scripted queue of Pydantic objects (Plans, ReflectDecisions),
  so agent trajectories are fully deterministic.
"""

from collections.abc import Callable, Sequence

from pydantic import BaseModel

from rm_copilot.agent.llm.base import LLMClient, LLMMessage, LLMResponse, SchemaT


class MockClient(LLMClient):
    def __init__(
        self,
        model: str = "mock",
        *,
        complete_text: str | Callable[[str, str], str] = "Hello. Reply STOP to opt out.",
        responses: Sequence[LLMResponse] | None = None,
        structured_responses: Sequence[BaseModel] | None = None,
    ) -> None:
        super().__init__(model)
        self._complete_text = complete_text
        self._responses = list(responses or [])
        self._index = 0
        self._structured = list(structured_responses or [])
        self._structured_index = 0

    def complete(self, *, system: str, prompt: str, max_output_tokens: int = 1024) -> str:
        if callable(self._complete_text):
            return self._complete_text(system, prompt)
        return self._complete_text

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        max_output_tokens: int = 2048,
    ) -> LLMResponse:
        if self._index < len(self._responses):
            response = self._responses[self._index]
            self._index += 1
            return response
        return LLMResponse(text="Done.", stop_reason="end_turn")

    def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        if self._structured_index >= len(self._structured):
            raise RuntimeError("MockClient.structured: no scripted response queued")
        obj = self._structured[self._structured_index]
        self._structured_index += 1
        if not isinstance(obj, schema):
            raise TypeError(
                f"MockClient.structured: queued {type(obj).__name__}, expected {schema.__name__}"
            )
        return obj
