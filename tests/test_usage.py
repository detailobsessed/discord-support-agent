"""Tests for usage tracking module."""

import pytest
from pydantic_ai.usage import RunUsage

from discord_support_agent.usage import UsageStats, UsageTracker

pytestmark = pytest.mark.anyio


class TestUsageStats:
    """Tests for UsageStats dataclass."""

    def test_default_values(self) -> None:
        """Test default values are zero."""
        stats = UsageStats()

        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_requests == 0
        assert stats.first_request_at is None
        assert stats.last_request_at is None

    def test_total_tokens_property(self) -> None:
        """Test total_tokens sums input and output."""
        stats = UsageStats(total_input_tokens=100, total_output_tokens=50)

        assert stats.total_tokens == 150


class TestUsageTracker:
    """Tests for UsageTracker."""

    async def test_record_single_usage(self) -> None:
        """Test recording a single usage."""
        tracker = UsageTracker()
        usage = RunUsage(input_tokens=100, output_tokens=50)

        await tracker.record(usage)

        stats = tracker.get_stats()
        assert stats.total_input_tokens == 100
        assert stats.total_output_tokens == 50
        assert stats.total_requests == 1
        assert stats.first_request_at is not None
        assert stats.last_request_at is not None

    async def test_record_multiple_usages(self) -> None:
        """Test recording multiple usages accumulates."""
        tracker = UsageTracker()

        await tracker.record(RunUsage(input_tokens=100, output_tokens=50))
        await tracker.record(RunUsage(input_tokens=200, output_tokens=100))
        await tracker.record(RunUsage(input_tokens=50, output_tokens=25))

        stats = tracker.get_stats()
        assert stats.total_input_tokens == 350
        assert stats.total_output_tokens == 175
        assert stats.total_requests == 3

    async def test_estimate_cost_default_model(self) -> None:
        """Test cost estimation for default (local) model is zero."""
        tracker = UsageTracker()
        await tracker.record(RunUsage(input_tokens=1_000_000, output_tokens=500_000))

        cost = tracker.estimate_cost()
        assert cost == 0.0

    async def test_reset_clears_stats(self) -> None:
        """Test reset clears all statistics."""
        tracker = UsageTracker()
        await tracker.record(RunUsage(input_tokens=100, output_tokens=50))

        tracker.reset()

        stats = tracker.get_stats()
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_requests == 0

    def test_model_name_stored(self) -> None:
        """Test model name is stored."""
        tracker = UsageTracker(model_name="gpt-4")

        assert tracker.model_name == "gpt-4"

    async def test_log_summary_does_not_raise(self) -> None:
        """Test log_summary runs without error."""
        tracker = UsageTracker()
        await tracker.record(RunUsage(input_tokens=100, output_tokens=50))

        # Should not raise
        tracker.log_summary()
