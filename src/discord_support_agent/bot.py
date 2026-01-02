"""Discord bot that monitors messages for support requests."""

import logging

import discord

from discord_support_agent.classifier import (
    ClassificationResult,
    ClassifierDeps,
    MessageClassifier,
)
from discord_support_agent.config import Settings
from discord_support_agent.issue_tracker import (
    IssueTracker,
    IssueTrackerType,
    MessageContext,
    create_issue_tracker,
)
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
        self.issue_tracker: IssueTracker = create_issue_tracker(
            IssueTrackerType(settings.issue_tracker),
            github_token=settings.github_token,
            github_repo=settings.github_repo,
            linear_api_key=settings.linear_api_key,
            linear_team_id=settings.linear_team_id,
        )
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
            guild_name = message.guild.name if message.guild else "DM"

            logger.debug(
                "Classifying message from %s in #%s: %s",
                author_name,
                channel_name,
                message.content[:100],
            )

            # Build classifier dependencies with available context
            deps = ClassifierDeps(
                author_id=message.author.id,
                author_name=author_name,
                channel_name=channel_name,
                guild_name=guild_name,
                message_timestamp=message.created_at,
                author_joined_at=getattr(message.author, "joined_at", None),
            )

            output = await self.classifier.classify(
                message_content=message.content,
                deps=deps,
            )

            logger.debug(
                "Classification: %s (confidence: %.2f, attention: %s, tokens: %d)",
                output.result.category.value,
                output.result.confidence,
                output.result.requires_attention,
                output.usage.total_tokens,
            )

            if output.result.requires_attention:
                await self._notify(message, output.result)
                await self._maybe_create_issue(message, output.result)

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

    async def _maybe_create_issue(
        self,
        message: discord.Message,
        result: ClassificationResult,
    ) -> None:
        """Create an issue if the category is configured for issue tracking."""
        if self.issue_tracker.tracker_type == IssueTrackerType.NONE:
            return

        # Check if this category should create issues
        # Empty list = create issues for all messages that require attention (falsy, skips filter)
        issue_categories = self.settings.issue_categories
        if issue_categories and result.category.value not in issue_categories:
            logger.debug(
                "Skipping issue creation for category %s (not in %s)",
                result.category.value,
                issue_categories,
            )
            return

        channel_name = getattr(message.channel, "name", "unknown")
        guild_name = message.guild.name if message.guild else "DM"
        guild_id = message.guild.id if message.guild else 0

        context = MessageContext(
            message_id=message.id,
            message_content=message.content,
            author_name=message.author.display_name,
            author_id=message.author.id,
            channel_name=channel_name,
            channel_id=message.channel.id,
            guild_name=guild_name,
            guild_id=guild_id,
            message_url=message.jump_url,
            classification=result,
        )

        try:
            issue_info = await self.issue_tracker.create_issue(context)
            logger.info(
                "Issue %s: %s",
                issue_info.issue_id,
                issue_info.issue_url,
            )
        except Exception:
            logger.exception("Failed to create issue for message %d", message.id)
