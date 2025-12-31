"""Tests for the message classifier using Pydantic AI TestModel."""

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from discord_support_agent.classifier import (
    ClassificationResult,
    MessageCategory,
    MessageClassifier,
)
from discord_support_agent.config import Settings

# Prevent accidental real API calls during tests
models.ALLOW_MODEL_REQUESTS = False  # type: ignore[assignment]

pytestmark = pytest.mark.anyio


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        discord_token="test-token",  # noqa: S106
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="test-model",
    )


@pytest.fixture
def classifier(settings: Settings) -> MessageClassifier:
    """Create a classifier instance for testing."""
    return MessageClassifier(settings)


class TestMessageClassifier:
    """Tests for MessageClassifier."""

    async def test_classify_with_support_request(
        self,
        classifier: MessageClassifier,
    ) -> None:
        """Test classification of a support request."""
        # Use custom_output_args to provide structured output
        custom_args = {
            "category": "support_request",
            "confidence": 0.95,
            "reason": "User is asking for help with password reset",
            "requires_attention": True,
        }

        with classifier.agent.override(
            model=TestModel(custom_output_args=custom_args),
        ):
            result = await classifier.classify(
                message_content="How do I reset my password?",
                author_name="TestUser",
                channel_name="support",
            )

        assert result.result.category == MessageCategory.SUPPORT_REQUEST
        assert result.result.confidence == 0.95
        assert result.result.requires_attention is True
        assert result.usage.total_tokens >= 0

    async def test_classify_bug_report(self, classifier: MessageClassifier) -> None:
        """Test classification of a bug report."""
        custom_args = {
            "category": "bug_report",
            "confidence": 0.88,
            "reason": "User is reporting an error",
            "requires_attention": True,
        }

        with classifier.agent.override(
            model=TestModel(custom_output_args=custom_args),
        ):
            result = await classifier.classify(
                message_content="The app crashes when I click submit",
                author_name="BugReporter",
                channel_name="bugs",
            )

        assert result.result.category == MessageCategory.BUG_REPORT
        assert result.result.requires_attention is True

    async def test_classify_complaint(self, classifier: MessageClassifier) -> None:
        """Test classification of a complaint."""
        custom_args = {
            "category": "complaint",
            "confidence": 0.92,
            "reason": "User is expressing frustration",
            "requires_attention": True,
        }

        with classifier.agent.override(
            model=TestModel(custom_output_args=custom_args),
        ):
            result = await classifier.classify(
                message_content="This is so frustrating, nothing works!",
                author_name="FrustratedUser",
                channel_name="general",
            )

        assert result.result.category == MessageCategory.COMPLAINT
        assert result.result.requires_attention is True

    async def test_classify_general_chat_no_attention(
        self,
        classifier: MessageClassifier,
    ) -> None:
        """Test that general chat doesn't require attention."""
        custom_args = {
            "category": "general_chat",
            "confidence": 0.99,
            "reason": "Casual greeting",
            "requires_attention": False,
        }

        with classifier.agent.override(
            model=TestModel(custom_output_args=custom_args),
        ):
            result = await classifier.classify(
                message_content="Hey everyone, happy Friday!",
                author_name="HappyUser",
                channel_name="general",
            )

        assert result.result.category == MessageCategory.GENERAL_CHAT
        assert result.result.requires_attention is False

    async def test_classify_other_category(
        self,
        classifier: MessageClassifier,
    ) -> None:
        """Test classification of other category."""
        custom_args = {
            "category": "other",
            "confidence": 0.75,
            "reason": "Unclassifiable message",
            "requires_attention": False,
        }

        with classifier.agent.override(
            model=TestModel(custom_output_args=custom_args),
        ):
            result = await classifier.classify(
                message_content="🎉🎊🎈",
                author_name="EmojiUser",
                channel_name="random",
            )

        assert result.result.category == MessageCategory.OTHER
        assert result.result.requires_attention is False


class TestClassificationResult:
    """Tests for ClassificationResult model."""

    def test_valid_classification_result(self) -> None:
        """Test creating a valid ClassificationResult."""
        result = ClassificationResult(
            category=MessageCategory.SUPPORT_REQUEST,
            confidence=0.85,
            reason="User needs help",
            requires_attention=True,
        )

        assert result.category == MessageCategory.SUPPORT_REQUEST
        assert result.confidence == 0.85
        assert result.reason == "User needs help"
        assert result.requires_attention is True

    def test_confidence_bounds(self) -> None:
        """Test that confidence must be between 0 and 1."""
        # Valid bounds
        ClassificationResult(
            category=MessageCategory.OTHER,
            confidence=0.0,
            reason="test",
            requires_attention=False,
        )
        ClassificationResult(
            category=MessageCategory.OTHER,
            confidence=1.0,
            reason="test",
            requires_attention=False,
        )

        # Invalid: below 0
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ClassificationResult(
                category=MessageCategory.OTHER,
                confidence=-0.1,
                reason="test",
                requires_attention=False,
            )

        # Invalid: above 1
        with pytest.raises(ValueError, match="less than or equal to 1"):
            ClassificationResult(
                category=MessageCategory.OTHER,
                confidence=1.1,
                reason="test",
                requires_attention=False,
            )


class TestMessageCategory:
    """Tests for MessageCategory enum."""

    def test_all_categories_exist(self) -> None:
        """Test that all expected categories exist."""
        expected = {
            "support_request",
            "complaint",
            "bug_report",
            "general_chat",
            "other",
        }
        actual = {cat.value for cat in MessageCategory}
        assert actual == expected

    def test_category_values(self) -> None:
        """Test category string values."""
        assert MessageCategory.SUPPORT_REQUEST.value == "support_request"
        assert MessageCategory.COMPLAINT.value == "complaint"
        assert MessageCategory.BUG_REPORT.value == "bug_report"
        assert MessageCategory.GENERAL_CHAT.value == "general_chat"
        assert MessageCategory.OTHER.value == "other"
