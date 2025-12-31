"""Message classification using Pydantic AI with Ollama."""

import logging
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
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
        self._agent: Agent[None, ClassificationResult] | None = None
        self.usage_tracker = UsageTracker(model_name=settings.ollama_model)

    @property
    def agent(self) -> Agent[None, ClassificationResult]:
        """Lazily initialize the Pydantic AI agent."""
        if self._agent is None:
            model = OpenAIChatModel(
                model_name=self.settings.ollama_model,
                provider=OllamaProvider(base_url=self.settings.ollama_base_url),
            )
            self._agent = Agent[None, ClassificationResult](
                model,
                output_type=ClassificationResult,
                system_prompt=SYSTEM_PROMPT,
                name="discord-message-classifier",
                retries=2,
                output_retries=3,
            )
            self._register_output_validator()
        return self._agent

    def _register_output_validator(self) -> None:
        """Register output validator for classification results."""

        @self._agent.output_validator  # type: ignore[union-attr]
        def validate_classification(
            _ctx: RunContext[None],
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
        author_name: str,
        channel_name: str,
    ) -> ClassificationOutput:
        """Classify a Discord message.

        Args:
            message_content: The text content of the message.
            author_name: The name of the message author.
            channel_name: The name of the channel where the message was posted.

        Returns:
            Classification output with result and usage information.

        Raises:
            Exception: If classification fails after all retries.
        """
        prompt = f"""Classify this Discord message:

Channel: #{channel_name}
Author: {author_name}
Message: {message_content}

Determine the category and whether it requires support staff attention."""

        try:
            result = await self.agent.run(prompt)
        except Exception:
            logger.exception("Failed to classify message from %s", author_name)
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
