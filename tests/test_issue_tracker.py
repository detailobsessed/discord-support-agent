"""Tests for the issue tracker system."""

import pytest

from discord_support_agent.classifier import ClassificationResult, MessageCategory
from discord_support_agent.issue_tracker import (
    GitHubIssueTracker,
    IssueInfo,
    IssueTrackerType,
    MessageContext,
    NoOpIssueTracker,
    create_issue_tracker,
)


@pytest.fixture
def sample_context() -> MessageContext:
    """Create a sample message context for testing."""
    return MessageContext(
        message_id=123456789,
        message_content="How do I reset my password? I've been trying for hours!",
        author_name="TestUser",
        author_id=987654321,
        channel_name="support",
        channel_id=111222333,
        guild_name="Test Server",
        guild_id=444555666,
        message_url="https://discord.com/channels/444555666/111222333/123456789",
        classification=ClassificationResult(
            category=MessageCategory.SUPPORT_REQUEST,
            confidence=0.95,
            reason="User is asking for help with password reset",
            requires_attention=True,
        ),
    )


class TestIssueTrackerType:
    """Tests for IssueTrackerType enum."""

    def test_all_types_exist(self) -> None:
        """Test that all expected tracker types exist."""
        expected = {"none", "github", "linear"}
        actual = {t.value for t in IssueTrackerType}
        assert actual == expected


class TestMessageContext:
    """Tests for MessageContext model."""

    def test_create_message_context(self, sample_context: MessageContext) -> None:
        """Test creating a MessageContext."""
        assert sample_context.message_id == 123456789
        assert sample_context.author_name == "TestUser"
        assert sample_context.channel_name == "support"
        assert sample_context.guild_name == "Test Server"
        assert sample_context.classification.category == MessageCategory.SUPPORT_REQUEST


class TestIssueInfo:
    """Tests for IssueInfo model."""

    def test_create_issue_info(self) -> None:
        """Test creating an IssueInfo."""
        info = IssueInfo(
            tracker=IssueTrackerType.GITHUB,
            issue_id="42",
            issue_url="https://github.com/owner/repo/issues/42",
            title="[Support Request] How do I reset my password?",
        )

        assert info.tracker == IssueTrackerType.GITHUB
        assert info.issue_id == "42"
        assert "github.com" in info.issue_url


class TestNoOpIssueTracker:
    """Tests for NoOpIssueTracker."""

    def test_tracker_type(self) -> None:
        """Test that NoOpIssueTracker returns correct type."""
        tracker = NoOpIssueTracker()
        assert tracker.tracker_type == IssueTrackerType.NONE

    @pytest.mark.anyio
    async def test_create_issue_returns_empty_info(
        self,
        sample_context: MessageContext,
    ) -> None:
        """Test that NoOpIssueTracker returns empty issue info."""
        tracker = NoOpIssueTracker()
        result = await tracker.create_issue(sample_context)

        assert result.tracker == IssueTrackerType.NONE
        assert result.issue_id == ""
        assert result.issue_url == ""
        assert "Support Request" in result.title


class TestGitHubIssueTracker:
    """Tests for GitHubIssueTracker."""

    def test_tracker_type(self) -> None:
        """Test that GitHubIssueTracker returns correct type."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        assert tracker.tracker_type == IssueTrackerType.GITHUB

    def test_build_title(self, sample_context: MessageContext) -> None:
        """Test issue title generation."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        title = tracker._build_title(sample_context)

        assert "[Support Request]" in title
        assert "How do I reset my password?" in title

    def test_build_title_truncates_long_messages(self) -> None:
        """Test that long messages are truncated in title."""
        context = MessageContext(
            message_id=1,
            message_content="A" * 100,  # 100 character message
            author_name="User",
            author_id=1,
            channel_name="test",
            channel_id=1,
            guild_name="Test",
            guild_id=1,
            message_url="https://example.com",
            classification=ClassificationResult(
                category=MessageCategory.BUG_REPORT,
                confidence=0.9,
                reason="test",
                requires_attention=True,
            ),
        )

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        title = tracker._build_title(context)

        # Title should be truncated with ellipsis
        assert "..." in title
        assert len(title) < 100

    def test_build_body(self, sample_context: MessageContext) -> None:
        """Test issue body generation."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        body = tracker._build_body(sample_context)

        assert "TestUser" in body
        assert "#support" in body
        assert "Test Server" in body
        assert sample_context.message_url in body
        assert sample_context.message_content in body
        assert "support_request" in body
        assert "95%" in body

    def test_get_labels_support_request(self, sample_context: MessageContext) -> None:
        """Test label generation for support requests."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        labels = tracker._get_labels(sample_context)

        assert "support" in labels
        assert "needs-response" in labels

    def test_get_labels_bug_report(self) -> None:
        """Test label generation for bug reports."""
        context = MessageContext(
            message_id=1,
            message_content="App crashes",
            author_name="User",
            author_id=1,
            channel_name="bugs",
            channel_id=1,
            guild_name="Test",
            guild_id=1,
            message_url="https://example.com",
            classification=ClassificationResult(
                category=MessageCategory.BUG_REPORT,
                confidence=0.9,
                reason="Bug report",
                requires_attention=True,
            ),
        )

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        labels = tracker._get_labels(context)

        assert "bug" in labels
        assert "needs-triage" in labels

    def test_get_labels_complaint(self) -> None:
        """Test label generation for complaints."""
        context = MessageContext(
            message_id=1,
            message_content="This is terrible",
            author_name="User",
            author_id=1,
            channel_name="general",
            channel_id=1,
            guild_name="Test",
            guild_id=1,
            message_url="https://example.com",
            classification=ClassificationResult(
                category=MessageCategory.COMPLAINT,
                confidence=0.9,
                reason="Complaint",
                requires_attention=True,
            ),
        )

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        labels = tracker._get_labels(context)

        assert "complaint" in labels
        assert "needs-response" in labels

    def test_get_labels_general_chat_empty(self) -> None:
        """Test that general chat gets no labels."""
        context = MessageContext(
            message_id=1,
            message_content="Hello everyone!",
            author_name="User",
            author_id=1,
            channel_name="general",
            channel_id=1,
            guild_name="Test",
            guild_id=1,
            message_url="https://example.com",
            classification=ClassificationResult(
                category=MessageCategory.GENERAL_CHAT,
                confidence=0.99,
                reason="Greeting",
                requires_attention=False,
            ),
        )

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")  # noqa: S106
        labels = tracker._get_labels(context)

        assert labels == []


class TestCreateIssueTracker:
    """Tests for create_issue_tracker factory function."""

    def test_create_none_tracker(self) -> None:
        """Test creating a NoOp tracker."""
        tracker = create_issue_tracker(IssueTrackerType.NONE)
        assert isinstance(tracker, NoOpIssueTracker)

    def test_create_github_tracker(self) -> None:
        """Test creating a GitHub tracker."""
        tracker = create_issue_tracker(
            IssueTrackerType.GITHUB,
            github_token="test-token",  # noqa: S106
            github_repo="owner/repo",
        )
        assert isinstance(tracker, GitHubIssueTracker)

    def test_create_github_tracker_missing_token_raises(self) -> None:
        """Test that missing GitHub token raises ValueError."""
        with pytest.raises(ValueError, match="GitHub token and repo are required"):
            create_issue_tracker(
                IssueTrackerType.GITHUB,
                github_token="",
                github_repo="owner/repo",
            )

    def test_create_github_tracker_missing_repo_raises(self) -> None:
        """Test that missing GitHub repo raises ValueError."""
        with pytest.raises(ValueError, match="GitHub token and repo are required"):
            create_issue_tracker(
                IssueTrackerType.GITHUB,
                github_token="test-token",  # noqa: S106
                github_repo="",
            )

    def test_create_linear_tracker_missing_config_raises(self) -> None:
        """Test that Linear tracker raises ValueError for missing config."""
        with pytest.raises(ValueError, match="Linear API key and team ID are required"):
            create_issue_tracker(
                IssueTrackerType.LINEAR,
                linear_api_key="",
                linear_team_id="",
            )

    def test_create_linear_tracker_not_implemented(self) -> None:
        """Test that Linear tracker raises NotImplementedError even with valid config."""
        with pytest.raises(NotImplementedError, match="Linear issue tracking is not yet implemented"):
            create_issue_tracker(
                IssueTrackerType.LINEAR,
                linear_api_key="test-key",
                linear_team_id="test-team",
            )
