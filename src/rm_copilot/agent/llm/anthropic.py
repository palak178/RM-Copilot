"""AnthropicClient — Claude provider via the official `anthropic` SDK (ADR-0004).

A real provider alongside Gemini. The only module that imports the `anthropic` SDK,
lazily, so the dependency is needed only when Anthropic is the configured provider.
Grounded in the official Messages API (the `claude-api` skill is the authoritative
reference): `client.messages.create(...)`, content blocks (`block.type == "text" |
"tool_use"`), forced `tool_choice` for schema-valid structured output, and the
`refusal` stop reason.

Enable with `pip install '.[anthropic]'`, `RM_COPILOT_LLM_PROVIDER=anthropic`, a Claude
model id (e.g. `RM_COPILOT_LLM_MODEL=claude-opus-4-8`), and a key
(`RM_COPILOT_LLM_API_KEY` or the `ANTHROPIC_API_KEY` environment variable). The factory
already wires this provider by name; no other module changes. Not exercised in unit
tests (the LLM is mocked).
"""

from typing import Any

from rm_copilot.agent.llm.base import (
    LLMClient,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    Role,
    SchemaT,
)

# A single forced tool is the most version-robust way to get schema-valid JSON
# across Claude models (vs. the newer messages.parse helper).
_STRUCTURED_TOOL = "emit_result"
_STRUCTURED_MAX_TOKENS = 2048


class AnthropicClient(LLMClient):
    """Provider-agnostic LLMClient backed by Claude via the `anthropic` SDK."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(model)
        self._api_key = api_key
        self._client: Any | None = None

    def _anthropic_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on optional extra
                raise RuntimeError(
                    "anthropic is not installed. Install the Anthropic provider with "
                    "`pip install '.[anthropic]'`."
                ) from exc
            self._client = (
                anthropic.Anthropic(api_key=self._api_key)
                if self._api_key
                else anthropic.Anthropic()
            )
        return self._client

    def complete(self, *, system: str, prompt: str, max_output_tokens: int = 1024) -> str:
        response = self._anthropic_client().messages.create(
            model=self.model,
            max_tokens=max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        self._guard_refusal(response)
        return self._text(response)

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        max_output_tokens: int = 2048,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": [self._to_message(m) for m in messages],
        }
        if tools:
            # Registry schemas ({name, description, input_schema}) are already the
            # Anthropic-native tool shape, so they pass through unchanged.
            kwargs["tools"] = tools
        response = self._anthropic_client().messages.create(**kwargs)
        self._guard_refusal(response)
        calls = tuple(
            LLMToolCall(id=block.id, name=block.name, arguments=dict(block.input or {}))
            for block in response.content
            if block.type == "tool_use"
        )
        return LLMResponse(
            text=None if calls else self._text(response),
            tool_calls=calls,
            stop_reason="tool_use" if calls else "end_turn",
        )

    def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        tool = {
            "name": _STRUCTURED_TOOL,
            "description": f"Return the result as structured {schema.__name__} data.",
            "input_schema": schema.model_json_schema(),
        }
        response = self._anthropic_client().messages.create(
            model=self.model,
            max_tokens=_STRUCTURED_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": _STRUCTURED_TOOL},
        )
        self._guard_refusal(response)
        for block in response.content:
            if block.type == "tool_use" and block.name == _STRUCTURED_TOOL:
                return schema.model_validate(block.input)
        raise RuntimeError("Anthropic structured(): model did not return the forced tool call.")

    @staticmethod
    def _guard_refusal(response: Any) -> None:
        if getattr(response, "stop_reason", None) == "refusal":
            raise RuntimeError(
                "Anthropic request was refused for safety reasons (stop_reason=refusal)."
            )

    @staticmethod
    def _text(response: Any) -> str:
        return "".join(block.text for block in response.content if block.type == "text")

    @staticmethod
    def _to_message(message: LLMMessage) -> dict:
        if message.role == Role.TOOL:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id or "",
                        "content": message.text or "",
                    }
                ],
            }
        if message.role == Role.ASSISTANT and message.tool_calls:
            content: list[dict] = []
            if message.text:
                content.append({"type": "text", "text": message.text})
            content += [
                {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                for tc in message.tool_calls
            ]
            return {"role": "assistant", "content": content}
        role = "assistant" if message.role == Role.ASSISTANT else "user"
        return {"role": role, "content": message.text or ""}
