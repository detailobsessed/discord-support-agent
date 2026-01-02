"""Tests for the issue tracker system."""

from unittest.mock import MagicMock, patch

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
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
        assert tracker.tracker_type == IssueTrackerType.GITHUB

    def test_build_title(self, sample_context: MessageContext) -> None:
        """Test issue title generation."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
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

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
        title = tracker._build_title(context)

        # Title should be truncated with ellipsis
        assert "..." in title
        assert len(title) < 100

    def test_build_body(self, sample_context: MessageContext) -> None:
        """Test issue body generation."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
        body = tracker._build_body(sample_context)

        assert "TestUser" in body
        assert "#support" in body
        assert "Test Server" in body
        assert sample_context.message_url in body
        assert sample_context.message_content in body
        assert "support_request" in body
        assert "95%" in body

    def test_build_body_includes_message_content(
        self,
        sample_context: MessageContext,
    ) -> None:
        """Test that issue body includes message content for deduplication."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
        body = tracker._build_body(sample_context)

        # Should contain the message content for content-based deduplication
        assert sample_context.message_content in body

    def test_find_existing_issue_returns_match_when_content_exists(
        self,
        sample_context: MessageContext,
    ) -> None:
        """Test that _find_existing_issue finds issues with matching content."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")

        # Create a mock issue with matching content in body
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_issue.html_url = "https://github.com/owner/repo/issues/42"
        mock_issue.title = "[Support Request] How do I reset..."
        mock_issue.body = f"## Message Content\n\n> {sample_context.message_content}\n"

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]

        with patch.object(tracker, "_get_repo", return_value=mock_repo):
            result = tracker._find_existing_issue(sample_context.message_content)

        assert result is not None
        assert result.issue_id == "42"
        assert result.issue_url == "https://github.com/owner/repo/issues/42"

    def test_find_existing_issue_returns_none_when_no_match(
        self,
        sample_context: MessageContext,
    ) -> None:
        """Test that _find_existing_issue returns None when no matching content."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")

        # Create a mock issue with different content
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_issue.body = "Some completely different message content"

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]

        with patch.object(tracker, "_get_repo", return_value=mock_repo):
            result = tracker._find_existing_issue(sample_context.message_content)

        assert result is None

    def test_find_existing_issue_handles_empty_body(self) -> None:
        """Test that _find_existing_issue handles issues with no body."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")

        # Create a mock issue with no body
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_issue.body = None

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]

        with patch.object(tracker, "_get_repo", return_value=mock_repo):
            result = tracker._find_existing_issue("some content")

        assert result is None

    def test_find_existing_issue_no_false_positive_on_partial_match(self) -> None:
        """Test that partial content matches don't create false positives."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")

        # Issue contains "help" but we're searching for "help with password"
        # This should NOT match because the quoted format is different
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_issue.body = "## Message Content\n\n> help\n\n## Classification"

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]

        with patch.object(tracker, "_get_repo", return_value=mock_repo):
            # Searching for longer message should not match shorter one
            result = tracker._find_existing_issue("help with password reset")

        assert result is None

    @pytest.mark.anyio
    async def test_create_issue_skips_creation_when_duplicate_exists(
        self,
        sample_context: MessageContext,
    ) -> None:
        """Test that create_issue returns existing issue without creating a new one."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")

        # Mock existing issue
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_issue.html_url = "https://github.com/owner/repo/issues/42"
        mock_issue.title = "[Support Request] How do I reset..."
        mock_issue.body = f"## Message Content\n\n> {sample_context.message_content}\n"

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]

        with patch.object(tracker, "_get_repo", return_value=mock_repo):
            result = await tracker.create_issue(sample_context)

        # Should return existing issue
        assert result.issue_id == "42"
        # Should NOT have called create_issue on the repo
        mock_repo.create_issue.assert_not_called()

    @pytest.mark.anyio
    async def test_create_issue_creates_when_no_duplicate(
        self,
        sample_context: MessageContext,
    ) -> None:
        """Test that create_issue creates a new issue when no duplicate exists."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")

        # Mock no existing issues
        mock_new_issue = MagicMock()
        mock_new_issue.number = 99
        mock_new_issue.html_url = "https://github.com/owner/repo/issues/99"
        mock_new_issue.title = "[Support Request] New issue"

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []  # No duplicates
        mock_repo.create_issue.return_value = mock_new_issue
        mock_repo.get_labels.return_value = []

        with patch.object(tracker, "_get_repo", return_value=mock_repo):
            result = await tracker.create_issue(sample_context)

        # Should return new issue
        assert result.issue_id == "99"
        # Should have called create_issue on the repo
        mock_repo.create_issue.assert_called_once()

    def test_get_labels_support_request(self, sample_context: MessageContext) -> None:
        """Test label generation for support requests."""
        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
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

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
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

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
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

        tracker = GitHubIssueTracker(token="test-token", repo="owner/repo")
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
            github_token="test-token",
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
                github_token="test-token",
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
