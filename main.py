"""Main entry point for discord-support-agent."""

import asyncio
import logging
import os
import sys
from pathlib import Path

from discord_support_agent.bot import SupportMonitorBot
from discord_support_agent.config import Settings, get_settings
from discord_support_agent.instrumentation import configure_instrumentation


def setup_logging() -> None:
    """Configure logging for the application."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "agent.log"),
        ],
    )
    # Reduce noise from discord.py
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


async def run_bot(settings: Settings) -> None:
    """Run the Discord bot."""
    bot = SupportMonitorBot(settings)

    async with bot:
        await bot.start(settings.discord_token)


def validate_issue_tracking(settings: Settings, logger: logging.Logger) -> None:
    """Validate issue tracking configuration and log status."""
    if settings.issue_tracker == "none":
        logger.info("Issue tracking: disabled (messages will be classified but no issues created)")
        return

    if settings.issue_tracker == "github":
        if not settings.github_repo:
            logger.warning(
                "Issue tracking: GitHub enabled but GITHUB_REPO not set. "
                "Run 'uv run setup.py' to configure, or set GITHUB_REPO in .env",
            )
            return
        if not settings.github_token:
            logger.warning(
                "Issue tracking: GitHub enabled but GITHUB_TOKEN not set. "
                "Issues will fail to create until token is configured.",
            )
            return
        logger.info("Issue tracking: GitHub → %s", settings.github_repo)

    elif settings.issue_tracker == "linear":
        if not settings.linear_api_key:
            logger.warning(
                "Issue tracking: Linear enabled but LINEAR_API_KEY not set. Set LINEAR_API_KEY in .env",
            )
            return
        if not settings.linear_team_id:
            logger.warning(
                "Issue tracking: Linear enabled but LINEAR_TEAM_ID not set. Set LINEAR_TEAM_ID in .env",
            )
            return
        logger.info("Issue tracking: Linear → team %s", settings.linear_team_id)


def main() -> None:
    """Run the application."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Load settings and configure instrumentation before anything else
    settings = get_settings()

    # Set OTEL endpoint from settings (must be set before logfire.configure)
    if settings.otel_enabled:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", settings.otel_exporter_endpoint)

    configure_instrumentation(settings)

    # Validate and log issue tracking status
    validate_issue_tracking(settings, logger)

    logger.info("Starting Discord Support Agent...")

    try:
        asyncio.run(run_bot(settings))
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
