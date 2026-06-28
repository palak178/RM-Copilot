"""Provider-agnostic LLM layer: factory selection, Mock client, extension stubs."""

import pytest

from rm_copilot.agent.llm.anthropic import AnthropicClient
from rm_copilot.agent.llm.base import LLMMessage, LLMResponse, LLMToolCall, Role
from rm_copilot.agent.llm.factory import LLMFactory
from rm_copilot.agent.llm.gemini import GeminiClient
from rm_copilot.agent.llm.mock import MockClient
from rm_copilot.agent.llm.openai import OpenAIClient
from rm_copilot.config.settings import Settings


def test_factory_selects_mock() -> None:
    client = LLMFactory.create("mock", "mock")
    assert isinstance(client, MockClient)


def test_factory_selects_gemini_without_importing_sdk() -> None:
    # Construction must not import google-genai (it is lazy), so this works without the extra.
    client = LLMFactory.create("gemini", "gemini-2.5-flash", api_key="k")
    assert isinstance(client, GeminiClient)
    assert client.model == "gemini-2.5-flash"


def test_factory_selects_anthropic_without_importing_sdk() -> None:
    # Anthropic is a real provider; construction is lazy (no `anthropic` import needed).
    client = LLMFactory.create("anthropic", "claude-opus-4-8", api_key="k")
    assert isinstance(client, AnthropicClient)
    assert client.model == "claude-opus-4-8"


def test_factory_openai_stub_raises_on_use() -> None:
    client = LLMFactory.create("openai", "x")
    assert isinstance(client, OpenAIClient)
    with pytest.raises(NotImplementedError):
        client.complete(system="s", prompt="p")


def test_factory_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="unknown LLM provider"):
        LLMFactory.create("llama-on-toaster", "x")


def test_factory_from_settings() -> None:
    settings = Settings(llm_provider="mock", llm_model="mock")
    assert isinstance(LLMFactory.from_settings(settings), MockClient)


def test_mock_complete_and_generate_scripting() -> None:
    scripted = LLMResponse(
        tool_calls=(
            LLMToolCall(id="t", name="find_and_rank_prospects", arguments={"product_id": "X"}),
        ),
        stop_reason="tool_use",
    )
    client = MockClient(complete_text="drafted text", responses=[scripted])
    assert client.complete(system="s", prompt="p") == "drafted text"
    first = client.generate(system="s", messages=[LLMMessage(role=Role.USER, text="hi")])
    assert first.stop_reason == "tool_use" and first.tool_calls[0].name == "find_and_rank_prospects"
    # Exhausted script -> terminal response.
    assert client.generate(system="s", messages=[]).stop_reason == "end_turn"
