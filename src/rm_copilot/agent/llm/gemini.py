"""GeminiClient — runtime LLM provider via the google-genai SDK.

The only place that imports google-genai (lazily, so the dependency is needed only
when Gemini is the configured provider). Grounded in the current google-genai API:
`genai.Client`, `models.generate_content(model, contents, config=GenerateContentConfig(...))`,
`types.FunctionDeclaration(parameters_json_schema=...)`, `response.text` /
`response.function_calls`.

Note: requires `pip install '.[llm]'` and a key (RM_COPILOT_LLM_API_KEY or the
GEMINI_API_KEY environment variable). Not exercised in unit tests (LLM is mocked).
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


class GeminiClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(model)
        self._api_key = api_key
        self._client: Any | None = None

    def _genai_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - depends on optional extra
                raise RuntimeError(
                    "google-genai is not installed. Install the Gemini provider with "
                    "`pip install '.[llm]'`."
                ) from exc
            self._client = genai.Client(api_key=self._api_key) if self._api_key else genai.Client()
        return self._client

    def complete(self, *, system: str, prompt: str, max_output_tokens: int = 1024) -> str:
        from google.genai import types

        response = self._genai_client().models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system, max_output_tokens=max_output_tokens
            ),
        )
        return response.text or ""

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        max_output_tokens: int = 2048,
    ) -> LLMResponse:
        from google.genai import types

        config_kwargs: dict[str, Any] = {
            "system_instruction": system,
            "max_output_tokens": max_output_tokens,
        }
        if tools:
            config_kwargs["tools"] = [self._to_tool(tools, types)]

        response = self._genai_client().models.generate_content(
            model=self.model,
            contents=[self._to_content(m, types) for m in messages],
            config=types.GenerateContentConfig(**config_kwargs),
        )
        calls = tuple(
            # Gemini function calls have no id; use the name (sufficient per-turn).
            LLMToolCall(id=fc.name, name=fc.name, arguments=dict(fc.args or {}))
            for fc in (response.function_calls or [])
        )
        return LLMResponse(
            text=None if calls else (response.text or ""),
            tool_calls=calls,
            stop_reason="tool_use" if calls else "end_turn",
        )

    def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        from google.genai import types

        response = self._genai_client().models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate_json(response.text or "{}")

    @staticmethod
    def _to_tool(tools: list[dict], types: Any) -> Any:
        declarations = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters_json_schema=t["input_schema"],
            )
            for t in tools
        ]
        return types.Tool(function_declarations=declarations)

    @staticmethod
    def _to_content(message: LLMMessage, types: Any) -> Any:
        if message.role == Role.TOOL:
            return types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=message.tool_name or "", response={"result": message.text or ""}
                    )
                ],
            )
        if message.role == Role.ASSISTANT and message.tool_calls:
            return types.Content(
                role="model",
                parts=[
                    types.Part(function_call=types.FunctionCall(name=tc.name, args=tc.arguments))
                    for tc in message.tool_calls
                ],
            )
        role = "model" if message.role == Role.ASSISTANT else "user"
        return types.Content(role=role, parts=[types.Part(text=message.text or "")])
