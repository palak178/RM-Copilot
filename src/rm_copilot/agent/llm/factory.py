"""LLMFactory — the single place providers are selected, from configuration.

Provider choice comes entirely from settings (provider, model, api_key) — no
hardcoded imports or conditionals scattered through the codebase. Adding a
provider = one entry here + a client class.
"""

from rm_copilot.agent.llm.anthropic import AnthropicClient
from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.llm.gemini import GeminiClient
from rm_copilot.agent.llm.mock import MockClient
from rm_copilot.agent.llm.openai import OpenAIClient
from rm_copilot.config.settings import Settings

_PROVIDERS = ("gemini", "mock", "anthropic", "openai")


class LLMFactory:
    """Creates the configured LLMClient implementation."""

    @staticmethod
    def create(provider: str, model: str, api_key: str | None = None) -> LLMClient:
        match provider.lower():
            case "gemini":
                return GeminiClient(model, api_key)
            case "mock":
                return MockClient(model)
            case "anthropic":
                return AnthropicClient(model, api_key)
            case "openai":
                return OpenAIClient(model, api_key)
            case _:
                raise ValueError(f"unknown LLM provider {provider!r}; expected one of {_PROVIDERS}")

    @staticmethod
    def from_settings(settings: Settings) -> LLMClient:
        return LLMFactory.create(settings.llm_provider, settings.llm_model, settings.llm_api_key)
