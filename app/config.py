"""
Application configuration using Pydantic Settings.

All configuration is loaded from environment variables (and .env in local
development). Nothing sensitive should ever be hardcoded here.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_name: str = Field(default="Risk Notification Backend")
    app_env: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # MongoDB
    mongodb_url: str = Field(default="mongodb://mongo:27017")
    mongodb_db_name: str = Field(default="notifications_db")

    # n8n
    n8n_notification_webhook_url: str = Field(
        default="https://example.n8n.cloud/webhook/teams-notification"
    )
    n8n_action_webhook_url: str = Field(
        default="https://example.n8n.cloud/webhook/teams-action"
    )
    n8n_timeout_seconds: float = Field(default=15.0)

    # Logging
    log_level: str = Field(default="INFO")

    # CORS - comma separated list of origins
    cors_origins: str = Field(default="http://localhost:3000")

    # Security
    internal_api_key: str = Field(default="")
    internal_api_key_enabled: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so we don't re-parse env vars every call."""
    return Settings()
