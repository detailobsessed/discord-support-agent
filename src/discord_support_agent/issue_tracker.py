"""Issue tracking integrations for creating tickets from support requests."""

import asyncio
import itertools
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel

from discord_support_agent.classifier import ClassificationResult, MessageCategory

logger = logging.getLogger(__name__)


class IssueTrackerType(str, Enum):
    """Supported issue tracker types."""

    NONE = "none"
    GITHUB = "github"
    LINEAR = "linear"


class IssueInfo(BaseModel):
    """Information about a created issue."""

    tracker: IssueTrackerType
    issue_id: str
    issue_url: str
    title: str


class MessageContext(BaseModel):
    """Context about a Discord message for issue creation."""

    message_id: int
    message_content: str
    author_name: str
    author_id: int
    channel_name: str
    channel_id: int
    guild_name: str
    guild_id: int
    message_url: str
    classification: ClassificationResult


class IssueTracker(ABC):
    """Abstract base class for issue trackers."""

    @property
    @abstractmethod
    def tracker_type(self) -> IssueTrackerType:
        """Return the tracker type."""

    @abstractmethod
    async def create_issue(self, context: MessageContext) -> IssueInfo:
        """Create an issue from a message context.

        Args:
            context: The message context with classification.

        Returns:
            Information about the created issue.
        """

    _TITLE_MAX_LENGTH = 50

    def _build_title(self, context: MessageContext) -> str:
        """Build issue title from context."""
        category_display = context.classification.category.value.replace("_", " ").title()
        # Truncate message for title
        content_preview = context.message_content[: self._TITLE_MAX_LENGTH]
        if len(context.message_content) > self._TITLE_MAX_LENGTH:
            content_preview += "..."
        return f"[{category_display}] {content_preview}"

    def _build_body(self, context: MessageContext) -> str:
        """Build issue body from context."""
        return f"""## Discord Message

**Author:** {context.author_name}
**Channel:** #{context.channel_name}
**Server:** {context.guild_name}
**Link:** {context.message_url}

## Message Content

> {context.message_content}

## Classification

- **Category:** {context.classification.category.value}
- **Confidence:** {context.classification.confidence:.0%}
- **Reason:** {context.classification.reason}

---
<!-- discord_message_id:{context.message_id} -->
"""

    def _get_labels(self, context: MessageContext) -> list[str]:
        """Get labels based on classification category."""
        label_map = {
            MessageCategory.SUPPORT_REQUEST: ["support", "needs-response"],
            MessageCategory.COMPLAINT: ["complaint", "needs-response"],
            MessageCategory.BUG_REPORT: ["bug", "needs-triage"],
            MessageCategory.GENERAL_CHAT: [],
            MessageCategory.OTHER: ["needs-triage"],
        }
        return label_map.get(context.classification.category, [])


class NoOpIssueTracker(IssueTracker):
    """Issue tracker that does nothing (for when tracking is disabled)."""

    @property
    def tracker_type(self) -> IssueTrackerType:
        """Return the tracker type."""
        return IssueTrackerType.NONE

    async def create_issue(self, context: MessageContext) -> IssueInfo:
        """Log but don't create an issue."""
        logger.debug("Issue tracking disabled, skipping issue creation")
        return IssueInfo(
            tracker=IssueTrackerType.NONE,
            issue_id="",
            issue_url="",
            title=self._build_title(context),
        )


class GitHubIssueTracker(IssueTracker):
    """GitHub Issues integration."""

    def __init__(
        self,
        token: str,
        repo: str,
        *,
        create_labels: bool = True,
    ) -> None:
        """Initialize GitHub issue tracker.

        Args:
            token: GitHub personal access token or app token.
            repo: Repository in "owner/repo" format.
            create_labels: Whether to create missing labels.
        """
        self.token = token
        self.repo = repo
        self.create_labels = create_labels
        self._github: Any = None
        self._repo_obj: Any = None

    @property
    def tracker_type(self) -> IssueTrackerType:
        """Return the tracker type."""
        return IssueTrackerType.GITHUB

    def _get_github(self) -> Any:
        """Lazily initialize GitHub client."""
        if self._github is None:
            import github  # noqa: PLC0415

            self._github = github.Github(self.token)
        return self._github

    def _get_repo(self) -> Any:
        """Lazily get repository object."""
        if self._repo_obj is None:
            self._repo_obj = self._get_github().get_repo(self.repo)
        return self._repo_obj

    async def create_issue(self, context: MessageContext) -> IssueInfo:
        """Create a GitHub issue if one doesn't already exist for this message."""
        loop = asyncio.get_event_loop()

        # Check for existing issue with same content first
        existing = await loop.run_in_executor(
            None,
            self._find_existing_issue,
            context.message_content,
        )
        if existing:
            logger.info(
                "Duplicate issue found for content: #%s",
                existing.issue_id,
            )
            return existing

        # PyGithub is sync, run in executor
        return await loop.run_in_executor(None, self._create_issue_sync, context)

    _DEDUP_SEARCH_LIMIT = 50

    def _find_existing_issue(self, message_content: str) -> IssueInfo | None:
        """Search for an existing issue with the same message content."""
        # Use repo.get_issues() instead of search_issues() to avoid indexing delay
        # GitHub's search index can take minutes to update, causing duplicates
        #
        # Match the exact quoted format from _build_body to avoid false positives
        # e.g., "help" should NOT match "help with password reset"
        quoted_content = f"> {message_content}"
        try:
            repo = self._get_repo()
            for issue in itertools.islice(
                repo.get_issues(state="open", sort="created", direction="desc"),
                self._DEDUP_SEARCH_LIMIT,
            ):
                # Check for exact quoted content match
                if issue.body and quoted_content in issue.body:
                    return IssueInfo(
                        tracker=IssueTrackerType.GITHUB,
                        issue_id=str(issue.number),
                        issue_url=issue.html_url,
                        title=issue.title,
                    )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to search for existing issues, proceeding with creation",
                exc_info=True,
            )
        return None

    def _create_issue_sync(self, context: MessageContext) -> IssueInfo:
        """Synchronous issue creation."""
        repo = self._get_repo()

        title = self._build_title(context)
        body = self._build_body(context)
        labels = self._get_labels(context)

        # Ensure labels exist if configured
        if self.create_labels and labels:
            self._ensure_labels_exist(repo, labels)

        # Create the issue
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels or [],
        )

        logger.info("Created GitHub issue #%d: %s", issue.number, title)

        return IssueInfo(
            tracker=IssueTrackerType.GITHUB,
            issue_id=str(issue.number),
            issue_url=issue.html_url,
            title=title,
        )

    def _ensure_labels_exist(self, repo: Any, labels: list[str]) -> None:
        """Create labels if they don't exist."""
        existing_labels = {label.name for label in repo.get_labels()}

        label_colors = {
            "support": "0366d6",
            "complaint": "d93f0b",
            "bug": "d73a4a",
            "needs-response": "fbca04",
            "needs-triage": "7057ff",
        }

        for label in labels:
            if label not in existing_labels:
                color = label_colors.get(label, "ededed")
                try:
                    repo.create_label(name=label, color=color)
                    logger.info("Created label: %s", label)
                except Exception:  # noqa: BLE001
                    logger.debug("Label %s may already exist", label)


class LinearIssueTracker(IssueTracker):
    """Linear integration (placeholder for future implementation)."""

    def __init__(self, api_key: str, team_id: str) -> None:
        """Initialize Linear issue tracker.

        Args:
            api_key: Linear API key.
            team_id: Linear team ID.
        """
        self.api_key = api_key
        self.team_id = team_id

    @property
    def tracker_type(self) -> IssueTrackerType:
        """Return the tracker type."""
        return IssueTrackerType.LINEAR

    async def create_issue(self, context: MessageContext) -> IssueInfo:
        """Create a Linear issue."""
        # TODO: Implement Linear API integration
        msg = "Linear integration not yet implemented"
        raise NotImplementedError(msg)


def create_issue_tracker(
    tracker_type: IssueTrackerType,
    *,
    github_token: str = "",
    github_repo: str = "",
    linear_api_key: str = "",
    linear_team_id: str = "",
) -> IssueTracker:
    """Factory function to create an issue tracker.

    Args:
        tracker_type: Which tracker to use.
        github_token: GitHub token (required if tracker_type is GITHUB).
        github_repo: GitHub repo in "owner/repo" format.
        linear_api_key: Linear API key (required if tracker_type is LINEAR).
        linear_team_id: Linear team ID.

    Returns:
        Configured issue tracker instance.
    """
    if tracker_type == IssueTrackerType.NONE:
        return NoOpIssueTracker()

    if tracker_type == IssueTrackerType.GITHUB:
        if not github_token or not github_repo:
            msg = "GitHub token and repo are required for GitHub issue tracking"
            raise ValueError(msg)
        return GitHubIssueTracker(token=github_token, repo=github_repo)

    if tracker_type == IssueTrackerType.LINEAR:
        if not linear_api_key or not linear_team_id:
            msg = "Linear API key and team ID are required for Linear issue tracking"
            raise ValueError(msg)
        msg = "Linear issue tracking is not yet implemented"
        raise NotImplementedError(msg)

    msg = f"Unknown tracker type: {tracker_type}"
    raise ValueError(msg)
