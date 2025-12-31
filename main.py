"""Main entry point for discord-support-agent."""

import asyncio
import logging
import sys
from pathlib import Path

from discord_support_agent.bot import SupportMonitorBot
from discord_support_agent.config import get_settings


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


async def run_bot() -> None:
    """Run the Discord bot."""
    settings = get_settings()
    bot = SupportMonitorBot(settings)

    async with bot:
        await bot.start(settings.discord_token)


def main() -> None:
    """Run the application."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Discord Support Agent...")

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
