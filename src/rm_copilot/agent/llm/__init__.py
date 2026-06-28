"""Provider-agnostic LLM layer.

The application depends ONLY on the `LLMClient` abstraction (base.py). Concrete
providers (Gemini, Anthropic, OpenAI, Mock) are selected by `LLMFactory` from
configuration — no business-logic module imports a provider SDK directly.
See docs/adr/0004-provider-agnostic-llm.md.
"""
