"""Tests for bot.py issue creation filtering."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_support_agent.bot import SupportMonitorBot
from discord_support_agent.classifier import ClassificationResult, MessageCategory
from discord_support_agent.config import Settings
from discord_support_agent.issue_tracker import IssueTrackerType


class TestMaybeCreateIssue:
    """Tests for _maybe_create_issue category filtering."""

    @pytest.fixture
    def mock_message(self) -> MagicMock:
        """Create a mock Discord message."""
        message = MagicMock()
        message.id = 123
        message.content = "Test message"
        message.author.display_name = "TestUser"
        message.author.id = 456
        message.channel.name = "general"
        message.channel.id = 789
        message.guild.name = "TestServer"
        message.guild.id = 101112
        message.jump_url = "https://discord.com/channels/..."
        return message

    @pytest.fixture
    def bug_report_result(self) -> ClassificationResult:
        """Create a bug report classification result."""
        return ClassificationResult(
            category=MessageCategory.BUG_REPORT,
            confidence=0.9,
            reason="User reported a bug",
            requires_attention=True,
        )

    @pytest.fixture
    def support_result(self) -> ClassificationResult:
        """Create a support request classification result."""
        return ClassificationResult(
            category=MessageCategory.SUPPORT_REQUEST,
            confidence=0.9,
            reason="User needs help",
            requires_attention=True,
        )

    @pytest.mark.asyncio
    async def test_issue_created_when_category_matches(
        self,
        mock_message: MagicMock,
        bug_report_result: ClassificationResult,
    ) -> None:
        """Test issue is created when category is in issue_categories."""
        settings = Settings(
            discord_token="test",
            issue_tracker="github",
            github_token="token",
            github_repo="owner/repo",
            issue_categories=["bug_report"],
        )

        bot = SupportMonitorBot(settings)
        bot.issue_tracker = MagicMock()
        bot.issue_tracker.tracker_type = IssueTrackerType.GITHUB
        bot.issue_tracker.create_issue = AsyncMock()

        await bot._maybe_create_issue(mock_message, bug_report_result)

        bot.issue_tracker.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_issue_skipped_when_category_not_in_list(
        self,
        mock_message: MagicMock,
        support_result: ClassificationResult,
    ) -> None:
        """Test issue is NOT created when category is not in issue_categories."""
        settings = Settings(
            discord_token="test",
            issue_tracker="github",
            github_token="token",
            github_repo="owner/repo",
            issue_categories=["bug_report"],  # Only bug_report, not support_request
        )

        bot = SupportMonitorBot(settings)
        bot.issue_tracker = MagicMock()
        bot.issue_tracker.tracker_type = IssueTrackerType.GITHUB
        bot.issue_tracker.create_issue = AsyncMock()

        await bot._maybe_create_issue(mock_message, support_result)

        bot.issue_tracker.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_list_creates_issues_for_all_categories(
        self,
        mock_message: MagicMock,
        support_result: ClassificationResult,
    ) -> None:
        """Test empty issue_categories creates issues for all categories."""
        settings = Settings(
            discord_token="test",
            issue_tracker="github",
            github_token="token",
            github_repo="owner/repo",
            issue_categories=[],  # Empty = all categories
        )

        bot = SupportMonitorBot(settings)
        bot.issue_tracker = MagicMock()
        bot.issue_tracker.tracker_type = IssueTrackerType.GITHUB
        bot.issue_tracker.create_issue = AsyncMock()

        await bot._maybe_create_issue(mock_message, support_result)

        bot.issue_tracker.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_issue_when_tracker_disabled(
        self,
        mock_message: MagicMock,
        bug_report_result: ClassificationResult,
    ) -> None:
        """Test no issue created when tracker is disabled."""
        settings = Settings(
            discord_token="test",
            issue_tracker="none",
        )

        bot = SupportMonitorBot(settings)

        # Should return early without error
        await bot._maybe_create_issue(mock_message, bug_report_result)
