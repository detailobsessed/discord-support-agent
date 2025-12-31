"""Pydantic Evals for classifier quality testing."""

from dataclasses import dataclass
from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from discord_support_agent.classifier import (
    ClassificationOutput,
    MessageCategory,
)


@dataclass
class ClassifierInput:
    """Input for classifier evaluation."""

    message_content: str
    author_name: str
    channel_name: str


@dataclass
class ExpectedClassification:
    """Expected classification output."""

    category: MessageCategory
    requires_attention: bool


@dataclass
class CategoryMatch(Evaluator[Any, Any]):
    """Evaluator that checks if the category matches expected."""

    def evaluate(self, ctx: EvaluatorContext[Any, Any]) -> float:
        """Return 1.0 if category matches, 0.0 otherwise."""
        if ctx.expected_output is None:
            return 0.0
        output: ClassificationOutput = ctx.output
        expected: ExpectedClassification = ctx.expected_output
        return 1.0 if output.result.category == expected.category else 0.0


@dataclass
class AttentionMatch(Evaluator[Any, Any]):
    """Evaluator that checks if requires_attention matches expected."""

    def evaluate(self, ctx: EvaluatorContext[Any, Any]) -> float:
        """Return 1.0 if attention flag matches, 0.0 otherwise."""
        if ctx.expected_output is None:
            return 0.0
        output: ClassificationOutput = ctx.output
        expected: ExpectedClassification = ctx.expected_output
        return 1.0 if output.result.requires_attention == expected.requires_attention else 0.0


@dataclass
class ConfidenceThreshold(Evaluator[Any, Any]):
    """Evaluator that checks if confidence meets minimum threshold."""

    min_confidence: float = 0.5

    def evaluate(self, ctx: EvaluatorContext[Any, Any]) -> float:
        """Return 1.0 if confidence >= threshold, 0.0 otherwise."""
        output: ClassificationOutput = ctx.output
        return 1.0 if output.result.confidence >= self.min_confidence else 0.0


def create_eval_dataset() -> Dataset[ClassifierInput, ExpectedClassification]:
    """Create the evaluation dataset with sample messages.

    Returns:
        Dataset with test cases for classifier evaluation.
    """
    cases = [
        # Support requests - should require attention
        Case(
            name="password_reset",
            inputs=ClassifierInput(
                message_content="How do I reset my password? I can't log in.",
                author_name="user123",
                channel_name="support",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.SUPPORT_REQUEST,
                requires_attention=True,
            ),
            metadata={"difficulty": "easy", "type": "support"},
        ),
        Case(
            name="api_help",
            inputs=ClassifierInput(
                message_content="Can someone help me understand how to use the API? The docs are confusing.",
                author_name="developer42",
                channel_name="help",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.SUPPORT_REQUEST,
                requires_attention=True,
            ),
            metadata={"difficulty": "medium", "type": "support"},
        ),
        # Bug reports - should require attention
        Case(
            name="crash_report",
            inputs=ClassifierInput(
                message_content="The app crashes every time I try to upload a file larger than 10MB",
                author_name="tester99",
                channel_name="bugs",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.BUG_REPORT,
                requires_attention=True,
            ),
            metadata={"difficulty": "easy", "type": "bug"},
        ),
        Case(
            name="error_message",
            inputs=ClassifierInput(
                message_content="Getting 'Error 500: Internal Server Error' when I try to save my settings",
                author_name="user456",
                channel_name="support",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.BUG_REPORT,
                requires_attention=True,
            ),
            metadata={"difficulty": "medium", "type": "bug"},
        ),
        # Complaints - should require attention
        Case(
            name="frustrated_user",
            inputs=ClassifierInput(
                message_content="This is ridiculous! I've been waiting 3 days for a response and nothing!",
                author_name="angryuser",
                channel_name="general",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.COMPLAINT,
                requires_attention=True,
            ),
            metadata={"difficulty": "easy", "type": "complaint"},
        ),
        Case(
            name="service_complaint",
            inputs=ClassifierInput(
                message_content="The service has been down twice this week. This is unacceptable for a paid product.",
                author_name="premium_user",
                channel_name="feedback",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.COMPLAINT,
                requires_attention=True,
            ),
            metadata={"difficulty": "medium", "type": "complaint"},
        ),
        # General chat - should NOT require attention
        Case(
            name="greeting",
            inputs=ClassifierInput(
                message_content="Hey everyone! Happy Friday!",
                author_name="friendly_user",
                channel_name="general",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.GENERAL_CHAT,
                requires_attention=False,
            ),
            metadata={"difficulty": "easy", "type": "chat"},
        ),
        Case(
            name="casual_chat",
            inputs=ClassifierInput(
                message_content="Anyone watching the game tonight? Should be a good one!",
                author_name="sports_fan",
                channel_name="off-topic",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.GENERAL_CHAT,
                requires_attention=False,
            ),
            metadata={"difficulty": "easy", "type": "chat"},
        ),
        Case(
            name="thanks_message",
            inputs=ClassifierInput(
                message_content="Thanks for the help earlier, got it working now!",
                author_name="grateful_user",
                channel_name="support",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.GENERAL_CHAT,
                requires_attention=False,
            ),
            metadata={"difficulty": "medium", "type": "chat"},
        ),
        # Other - should NOT require attention
        Case(
            name="emoji_only",
            inputs=ClassifierInput(
                message_content="🎉🎊🎈",
                author_name="emoji_user",
                channel_name="random",
            ),
            expected_output=ExpectedClassification(
                category=MessageCategory.OTHER,
                requires_attention=False,
            ),
            metadata={"difficulty": "easy", "type": "other"},
        ),
    ]

    return Dataset(
        cases=cases,
        evaluators=[
            CategoryMatch(),
            AttentionMatch(),
            ConfidenceThreshold(min_confidence=0.5),
        ],
    )
