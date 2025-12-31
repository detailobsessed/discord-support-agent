"""discord-support-agent package.

AI agent that monitors Discord servers and notifies about support requests
"""

from discord_support_agent.bot import SupportMonitorBot
from discord_support_agent.classifier import ClassificationResult, MessageCategory, MessageClassifier
from discord_support_agent.config import Settings, get_settings
from discord_support_agent.notifier import send_notification

__all__: list[str] = [
    "ClassificationResult",
    "MessageCategory",
    "MessageClassifier",
    "Settings",
    "SupportMonitorBot",
    "get_settings",
    "send_notification",
]
