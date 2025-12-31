"""Discord bot that monitors messages for support requests."""

import logging

import discord

from discord_support_agent.classifier import ClassificationResult, MessageClassifier
from discord_support_agent.config import Settings
from discord_support_agent.notifier import send_notification

_MAX_NOTIFICATION_LENGTH = 200

logger = logging.getLogger(__name__)


class SupportMonitorBot(discord.Client):
    """Discord bot that monitors channels for support requests."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the bot with settings."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(intents=intents)

        self.settings = settings
        self.classifier = MessageClassifier(settings)
        self._processed_message_ids: set[int] = set()
        self._max_processed_cache = 10000

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info("Bot is ready. Logged in as %s", self.user)
        logger.info("Monitoring %d guilds", len(self.guilds))

        for guild in self.guilds:
            logger.info("  - %s (ID: %d)", guild.name, guild.id)

    async def on_message(self, message: discord.Message) -> None:
        """Called when a message is received."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore DMs
        if not message.guild:
            return

        # Check guild filter
        if self.settings.discord_guild_ids and message.guild.id not in self.settings.discord_guild_ids:
            return

        # Skip if already processed
        if message.id in self._processed_message_ids:
            return

        # Add to processed set (with size limit)
        self._processed_message_ids.add(message.id)
        if len(self._processed_message_ids) > self._max_processed_cache:
            # Remove oldest entries (approximate - sets aren't ordered)
            to_remove = len(self._processed_message_ids) - self._max_processed_cache
            for msg_id in list(self._processed_message_ids)[:to_remove]:
                self._processed_message_ids.discard(msg_id)

        # Skip empty messages
        if not message.content.strip():
            return

        await self._process_message(message)

    async def _process_message(self, message: discord.Message) -> None:
        """Process and classify a message."""
        try:
            channel_name = getattr(message.channel, "name", "unknown")
            author_name = message.author.display_name

            logger.debug(
                "Classifying message from %s in #%s: %s",
                author_name,
                channel_name,
                message.content[:100],
            )

            result = await self.classifier.classify(
                message_content=message.content,
                author_name=author_name,
                channel_name=channel_name,
            )

            logger.debug(
                "Classification: %s (confidence: %.2f, attention: %s)",
                result.category.value,
                result.confidence,
                result.requires_attention,
            )

            if result.requires_attention:
                await self._notify(message, result)

        except Exception:
            logger.exception("Error processing message %d", message.id)

    async def _notify(
        self,
        message: discord.Message,
        result: ClassificationResult,
    ) -> None:
        """Send a notification for a message that requires attention."""
        channel_name = getattr(message.channel, "name", "unknown")
        guild_name = message.guild.name if message.guild else "DM"

        title = f"🔔 {result.category.value.replace('_', ' ').title()}"
        subtitle = f"#{channel_name} in {guild_name}"

        # Truncate message for notification
        content = message.content
        if len(content) > _MAX_NOTIFICATION_LENGTH:
            content = content[: _MAX_NOTIFICATION_LENGTH - 3] + "..."

        body = f"{message.author.display_name}: {content}"

        logger.info(
            "Sending notification: %s - %s",
            title,
            body[:50],
        )

        send_notification(
            title=title,
            message=body,
            subtitle=subtitle,
        )
