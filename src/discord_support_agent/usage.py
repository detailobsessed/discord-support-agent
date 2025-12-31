"""Usage tracking for LLM token consumption and cost estimation."""

import asyncio
import logging
from copy import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic_ai.usage import RunUsage

logger = logging.getLogger(__name__)

# Approximate costs per 1M tokens (as of late 2024)
# These are rough estimates - actual costs vary by model and provider
MODEL_COSTS_PER_MILLION: dict[str, dict[str, float]] = {
    "default": {"input": 0.0, "output": 0.0},  # Local models (Ollama) are free
}


@dataclass
class UsageStats:
    """Aggregated usage statistics."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    first_request_at: datetime | None = None
    last_request_at: datetime | None = None

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.total_input_tokens + self.total_output_tokens


@dataclass
class UsageTracker:
    """Tracks LLM usage across multiple requests.

    Thread-safe for concurrent async calls via internal asyncio.Lock.
    """

    model_name: str = "default"
    _stats: UsageStats = field(default_factory=UsageStats)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def record(self, usage: RunUsage) -> None:
        """Record usage from a single agent run.

        Args:
            usage: Usage statistics from a Pydantic AI agent run.
        """
        now = datetime.now(UTC)

        async with self._lock:
            self._stats.total_input_tokens += usage.input_tokens
            self._stats.total_output_tokens += usage.output_tokens
            self._stats.total_requests += 1

            if self._stats.first_request_at is None:
                self._stats.first_request_at = now
            self._stats.last_request_at = now

            total_tokens = self._stats.total_tokens
            total_requests = self._stats.total_requests

        logger.debug(
            "Usage recorded: input=%d, output=%d, total=%d (cumulative: %d tokens, %d requests)",
            usage.input_tokens,
            usage.output_tokens,
            usage.total_tokens,
            total_tokens,
            total_requests,
        )

    def get_stats(self) -> UsageStats:
        """Get current aggregated usage statistics.

        Returns a copy to prevent accidental mutation of internal state.
        """
        return copy(self._stats)

    def estimate_cost(self) -> float:
        """Estimate cost based on token usage and model pricing.

        Returns:
            Estimated cost in USD. Returns 0.0 for local models.
        """
        costs = MODEL_COSTS_PER_MILLION.get(
            self.model_name,
            MODEL_COSTS_PER_MILLION["default"],
        )

        input_cost = (self._stats.total_input_tokens / 1_000_000) * costs["input"]
        output_cost = (self._stats.total_output_tokens / 1_000_000) * costs["output"]

        return input_cost + output_cost

    def log_summary(self) -> None:
        """Log a summary of usage statistics."""
        stats = self._stats
        cost = self.estimate_cost()

        logger.info(
            "Usage summary: %d requests, %d input tokens, %d output tokens, %.4f USD estimated cost",
            stats.total_requests,
            stats.total_input_tokens,
            stats.total_output_tokens,
            cost,
        )

    def reset(self) -> None:
        """Reset all usage statistics."""
        self._stats = UsageStats()
