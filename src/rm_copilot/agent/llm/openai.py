"""OpenAIClient — documented extension point (not implemented). See ADR-0004.

To enable: `pip install '.[openai]'`, set RM_COPILOT_LLM_PROVIDER=openai, and
implement the two methods using the official `openai` SDK (Chat Completions /
Responses API with tool calling). No other module changes are required — the
factory already wires this provider by name.
"""

from rm_copilot.agent.llm.base import LLMClient, LLMMessage, LLMResponse, SchemaT

_NOT_IMPLEMENTED = (
    "OpenAIClient is a documented extension point (ADR-0004) and is not implemented. "
    "Use provider 'gemini' (runtime default) or 'mock' (tests)."
)


class OpenAIClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(model)
        self._api_key = api_key

    def complete(self, *, system: str, prompt: str, max_output_tokens: int = 1024) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        max_output_tokens: int = 2048,
    ) -> LLMResponse:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        raise NotImplementedError(_NOT_IMPLEMENTED)
