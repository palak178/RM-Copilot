"""Typed application settings (pydantic-settings).

Reads ``RM_COPILOT_*`` environment variables (and an optional ``.env``). Only the
fields needed so far are defined; unknown env vars are ignored so the full
``.env.example`` can list variables consumed by later milestones.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration sourced from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="RM_COPILOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "./var/rm_copilot.db"
    seed: int = 42
    customer_count: int = 500
    scoring_config_path: str = "./config/scoring.yaml"

    # LLM is provider-agnostic; selection is config-driven (see agent.llm.LLMFactory).
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.1-flash-lite"
    llm_api_key: str | None = None  # falls back to the provider's own env var if unset


def get_settings() -> Settings:
    """Return settings loaded from the environment."""
    return Settings()
