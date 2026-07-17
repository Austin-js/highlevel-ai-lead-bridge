"""Environment-driven application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HighLevel AI Lead Bridge"
    app_env: Literal["development", "demo", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    webhook_shared_secret: str | None = None
    webhook_secret_header: str = "X-Webhook-Secret"
    llm_provider: str = "mock"
    llm_model: str = "demo"
    llm_timeout_seconds: int = Field(default=30, ge=1, le=300)
    llm_secondary_provider: str | None = None
    llm_input_cost_per_million: float | None = Field(default=None, ge=0)
    llm_output_cost_per_million: float | None = Field(default=None, ge=0)
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    max_retry_attempts: int = Field(default=3, ge=1, le=10)
    http_timeout_seconds: int = Field(default=15, ge=1, le=120)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
