"""Configuration for the Discord Support Agent."""

import logging
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Must match MessageCategory enum values in classifier.py (circular import prevents deriving)
VALID_CATEGORIES = {"support_request", "complaint", "bug_report", "general_chat", "other"}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Discord
    discord_token: str = Field(default="", description="Discord bot token")
    discord_guild_ids: list[int] = Field(
        default_factory=list,
        description="Guild IDs to monitor (empty = all guilds the bot is in)",
    )

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Ollama API base URL",
    )
    ollama_model: str = Field(
        default="qwen3:30b",
        description="Ollama model to use for classification",
    )

    # Agent behavior
    check_interval_seconds: int = Field(
        default=60,
        description="How often to check for new messages (seconds)",
    )
    lookback_minutes: int = Field(
        default=5,
        description="How far back to look for messages on each check",
    )

    # Issue tracking
    issue_tracker: Literal["none", "github", "linear"] = Field(
        default="none",
        description="Issue tracker to use: none, github, or linear",
    )
    github_token: str = Field(
        default="",
        description="GitHub personal access token for issue creation",
    )
    github_repo: str = Field(
        default="",
        description="GitHub repository in 'owner/repo' format",
    )
    linear_api_key: str = Field(
        default="",
        description="Linear API key for issue creation",
    )
    linear_team_id: str = Field(
        default="",
        description="Linear team ID for issue creation",
    )
    issue_categories: list[str] = Field(
        default_factory=lambda: ["support_request", "complaint", "bug_report"],
        description="Message categories that create issues (empty = all that require attention)",
    )

    @field_validator("issue_categories")
    @classmethod
    def warn_invalid_categories(cls, v: list[str]) -> list[str]:
        """Warn about invalid category names that won't match any messages."""
        invalid = set(v) - VALID_CATEGORIES
        if invalid:
            logger.warning(
                "Unknown issue categories (won't match any messages): %s. Valid categories: %s",
                sorted(invalid),
                sorted(VALID_CATEGORIES),
            )
        return v

    # OpenTelemetry / Instrumentation
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry instrumentation",
    )
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4318",
        description="OTLP exporter endpoint (e.g., otel-tui, Jaeger)",
    )
    otel_instrument_httpx: bool = Field(
        default=False,
        description="Also instrument HTTPX for raw HTTP request visibility",
    )


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
