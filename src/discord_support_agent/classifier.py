"""Message classification using Pydantic AI with Ollama."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.usage import RunUsage

from discord_support_agent.config import Settings
from discord_support_agent.usage import UsageTracker

logger = logging.getLogger(__name__)


class MessageCategory(str, Enum):
    """Categories for Discord messages."""

    SUPPORT_REQUEST = "support_request"
    COMPLAINT = "complaint"
    BUG_REPORT = "bug_report"
    GENERAL_CHAT = "general_chat"
    OTHER = "other"


class ClassificationResult(BaseModel):
    """Result of message classification."""

    category: MessageCategory = Field(description="The category of the message")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )
    reason: str = Field(description="Brief explanation for the classification")
    requires_attention: bool = Field(
        description="Whether this message requires human attention",
    )


@dataclass
class ClassificationOutput:
    """Classification result with usage information."""

    result: ClassificationResult
    usage: RunUsage


@dataclass
class ClassifierDeps:
    """Dependencies passed to the classifier agent for tool access."""

    author_id: int
    author_name: str
    channel_name: str
    guild_name: str
    message_timestamp: datetime
    author_joined_at: datetime | None = None
    author_message_count: int | None = None
    recent_channel_messages: list[str] = field(default_factory=list)


_NEW_USER_DAYS = 7
_RECENT_USER_DAYS = 30
_LOW_ACTIVITY_MESSAGES = 5
_MODERATE_ACTIVITY_MESSAGES = 50


def get_user_context(ctx: RunContext[ClassifierDeps]) -> str:
    """Get context about the message author.

    Returns information about whether the user is new, their activity level,
    and recent channel context to help with classification.
    """
    deps = ctx.deps
    lines = [f"Author: {deps.author_name}"]

    if deps.author_joined_at:
        days_since_join = (deps.message_timestamp - deps.author_joined_at).days
        if days_since_join < _NEW_USER_DAYS:
            lines.append(f"User status: NEW (joined {days_since_join} days ago)")
        elif days_since_join < _RECENT_USER_DAYS:
            lines.append(f"User status: Recent member ({days_since_join} days)")
        else:
            lines.append(f"User status: Established member ({days_since_join} days)")

    if deps.author_message_count is not None:
        if deps.author_message_count < _LOW_ACTIVITY_MESSAGES:
            lines.append(f"Activity: Low ({deps.author_message_count} messages)")
        elif deps.author_message_count < _MODERATE_ACTIVITY_MESSAGES:
            lines.append(f"Activity: Moderate ({deps.author_message_count} messages)")
        else:
            lines.append(f"Activity: High ({deps.author_message_count} messages)")

    return "\n".join(lines)


def get_channel_context(ctx: RunContext[ClassifierDeps]) -> str:
    """Get recent messages from the channel for context.

    Returns the last few messages to help understand the conversation flow.
    """
    deps = ctx.deps
    if not deps.recent_channel_messages:
        return "No recent channel context available."

    lines = [f"Recent messages in #{deps.channel_name}:"]
    for msg in deps.recent_channel_messages[-5:]:
        lines.append(f"  - {msg[:100]}...")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a Discord message classifier for a community support server.

Your job is to analyze messages and determine if they require attention from support staff.

Messages that require attention include:
- Support requests: Users asking for help with a product, service, or technical issue
- Complaints: Users expressing frustration or dissatisfaction
- Bug reports: Users reporting problems, errors, or unexpected behavior

Messages that do NOT require attention include:
- General chat: Casual conversation, greetings, jokes
- Off-topic discussion
- Messages that are clearly resolved or just acknowledgments

Be conservative - only flag messages that genuinely need human attention.
Consider the context and tone of the message."""


class MessageClassifier:
    """Classifies Discord messages using a local LLM via Ollama."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the classifier with settings."""
        self.settings = settings
        self._agent: Agent[ClassifierDeps, ClassificationResult] | None = None
        self.usage_tracker = UsageTracker(model_name=settings.ollama_model)

    @property
    def agent(self) -> Agent[ClassifierDeps, ClassificationResult]:
        """Lazily initialize the Pydantic AI agent."""
        if self._agent is None:
            model = OpenAIChatModel(
                model_name=self.settings.ollama_model,
                provider=OllamaProvider(base_url=self.settings.ollama_base_url),
            )
            self._agent = Agent[ClassifierDeps, ClassificationResult](
                model,
                deps_type=ClassifierDeps,
                output_type=ClassificationResult,
                system_prompt=SYSTEM_PROMPT,
                name="discord-message-classifier",
                retries=2,
                output_retries=3,
                tools=[
                    Tool(get_user_context, takes_ctx=True),
                    Tool(get_channel_context, takes_ctx=True),
                ],
            )
            self._register_output_validator()
        return self._agent

    def _register_output_validator(self) -> None:
        """Register output validator for classification results."""

        @self._agent.output_validator  # type: ignore[union-attr]
        def validate_classification(
            _ctx: RunContext[ClassifierDeps],
            result: ClassificationResult,
        ) -> ClassificationResult:
            """Validate classification output for consistency."""
            # Ensure requires_attention matches category
            attention_categories = {
                MessageCategory.SUPPORT_REQUEST,
                MessageCategory.COMPLAINT,
                MessageCategory.BUG_REPORT,
            }

            expected_attention = result.category in attention_categories

            if result.requires_attention != expected_attention:
                logger.warning(
                    "Classification inconsistency: category=%s but requires_attention=%s, correcting to %s",
                    result.category,
                    result.requires_attention,
                    expected_attention,
                )
                result.requires_attention = expected_attention

            # Validate confidence is reasonable
            min_confidence = 0.3
            if result.confidence < min_confidence and result.requires_attention:
                raise ModelRetry(
                    "Low confidence classification that requires attention. "
                    "Please re-analyze the message more carefully.",
                )

            return result

    async def classify(
        self,
        message_content: str,
        deps: ClassifierDeps,
    ) -> ClassificationOutput:
        """Classify a Discord message.

        Args:
            message_content: The text content of the message.
            deps: Dependencies containing author, channel, and context information.

        Returns:
            Classification output with result and usage information.

        Raises:
            Exception: If classification fails after all retries.
        """
        prompt = f"""Classify this Discord message:

Channel: #{deps.channel_name}
Author: {deps.author_name}
Message: {message_content}

You can use the available tools to get more context about the user and channel if needed.
Determine the category and whether it requires support staff attention."""

        try:
            result = await self.agent.run(prompt, deps=deps)
        except Exception:
            logger.exception("Failed to classify message from %s", deps.author_name)
            raise
        else:
            usage = result.usage()
            await self.usage_tracker.record(usage)

            logger.debug(
                "Classified message: category=%s, confidence=%.2f, attention=%s, tokens=%d",
                result.output.category,
                result.output.confidence,
                result.output.requires_attention,
                usage.total_tokens,
            )
            return ClassificationOutput(result=result.output, usage=usage)
