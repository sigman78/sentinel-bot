"""
Configuration management.

Loads settings from environment variables and .env file.
Prefix: SENTINEL_
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # LLM Providers
    anthropic_api_key: str = Field(default="", description="Claude API key")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    local_llm_url: str = Field(
        default="http://localhost:1234/v1",
        description="Local LLM endpoint (OpenAI-compatible)",
    )

    # Telegram
    telegram_token: str = Field(default="", description="Telegram bot token")
    telegram_owner_id: int = Field(default=0, description="Owner's Telegram user ID")

    # Storage
    data_dir: Path = Field(default=Path("data"), description="Data storage directory")
    db_name: str = Field(default="sentinel.db", description="SQLite database name")

    # Model defaults
    default_model: str = Field(default="claude-sonnet-4-20250514", description="Default model")
    fallback_model: str = Field(default="anthropic/claude-3-haiku", description="Fallback model")

    # Limits
    max_context_messages: int = Field(default=20, description="Max messages in context")
    daily_cost_limit: float = Field(default=5.0, description="Daily API cost limit USD")

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
