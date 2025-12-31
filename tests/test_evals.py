"""Tests for the evals module."""

from discord_support_agent.classifier import MessageCategory
from discord_support_agent.evals import (
    ClassifierInput,
    ExpectedClassification,
    create_eval_dataset,
)


class TestClassifierInput:
    """Tests for ClassifierInput dataclass."""

    def test_create_input(self) -> None:
        """Test creating a classifier input."""
        inp = ClassifierInput(
            message_content="Hello",
            author_name="user",
            channel_name="general",
        )
        assert inp.message_content == "Hello"
        assert inp.author_name == "user"
        assert inp.channel_name == "general"


class TestExpectedClassification:
    """Tests for ExpectedClassification dataclass."""

    def test_create_expected(self) -> None:
        """Test creating an expected classification."""
        expected = ExpectedClassification(
            category=MessageCategory.SUPPORT_REQUEST,
            requires_attention=True,
        )
        assert expected.category == MessageCategory.SUPPORT_REQUEST
        assert expected.requires_attention is True


class TestCreateEvalDataset:
    """Tests for create_eval_dataset function."""

    def test_dataset_has_cases(self) -> None:
        """Test that dataset has test cases."""
        dataset = create_eval_dataset()
        assert len(dataset.cases) >= 10

    def test_dataset_has_evaluators(self) -> None:
        """Test that dataset has evaluators configured."""
        dataset = create_eval_dataset()
        assert len(dataset.evaluators) == 3

    def test_cases_have_expected_outputs(self) -> None:
        """Test that all cases have expected outputs."""
        dataset = create_eval_dataset()
        for case in dataset.cases:
            assert case.expected_output is not None
            assert isinstance(case.expected_output, ExpectedClassification)

    def test_cases_have_metadata(self) -> None:
        """Test that all cases have metadata."""
        dataset = create_eval_dataset()
        for case in dataset.cases:
            assert case.metadata is not None
            assert "difficulty" in case.metadata
            assert "type" in case.metadata

    def test_attention_categories_require_attention(self) -> None:
        """Test that support/bug/complaint cases require attention."""
        dataset = create_eval_dataset()
        attention_types = {"support", "bug", "complaint"}

        for case in dataset.cases:
            if case.metadata and case.metadata.get("type") in attention_types:
                assert case.expected_output is not None
                assert case.expected_output.requires_attention is True

    def test_non_attention_categories_do_not_require_attention(self) -> None:
        """Test that chat/other cases don't require attention."""
        dataset = create_eval_dataset()
        non_attention_types = {"chat", "other"}

        for case in dataset.cases:
            if case.metadata and case.metadata.get("type") in non_attention_types:
                assert case.expected_output is not None
                assert case.expected_output.requires_attention is False
