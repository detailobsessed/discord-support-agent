"""discord-support-agent package.

AI agent that monitors Discord servers and notifies about support requests
"""

from discord_support_agent.bot import SupportMonitorBot
from discord_support_agent.classifier import ClassificationResult, MessageCategory, MessageClassifier
from discord_support_agent.config import Settings, get_settings
from discord_support_agent.issue_tracker import (
    GitHubIssueTracker,
    IssueInfo,
    IssueTracker,
    IssueTrackerType,
    MessageContext,
    create_issue_tracker,
)
from discord_support_agent.notifier import send_notification

__all__: list[str] = [
    "ClassificationResult",
    "GitHubIssueTracker",
    "IssueInfo",
    "IssueTracker",
    "IssueTrackerType",
    "MessageCategory",
    "MessageClassifier",
    "MessageContext",
    "Settings",
    "SupportMonitorBot",
    "create_issue_tracker",
    "get_settings",
    "send_notification",
]
