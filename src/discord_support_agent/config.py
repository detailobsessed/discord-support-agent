"""Configuration for the Discord Support Agent."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
