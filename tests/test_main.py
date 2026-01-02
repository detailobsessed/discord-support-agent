"""Tests for main.py startup validation."""

import logging
from unittest.mock import MagicMock

import pytest

from discord_support_agent.config import Settings
from main import validate_issue_tracking


class TestValidateIssueTracking:
    """Tests for validate_issue_tracking function."""

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create a mock logger."""
        return MagicMock(spec=logging.Logger)

    def test_issue_tracking_disabled(self, mock_logger: MagicMock) -> None:
        """Test when issue tracking is disabled."""
        settings = Settings(issue_tracker="none")

        validate_issue_tracking(settings, mock_logger)

        mock_logger.info.assert_called_once()
        assert "disabled" in mock_logger.info.call_args[0][0]

    def test_github_missing_repo(self, mock_logger: MagicMock) -> None:
        """Test GitHub enabled but GITHUB_REPO not set."""
        settings = Settings(
            issue_tracker="github",
            github_token="token",
            github_repo="",
        )

        validate_issue_tracking(settings, mock_logger)

        mock_logger.warning.assert_called_once()
        assert "GITHUB_REPO not set" in mock_logger.warning.call_args[0][0]

    def test_github_missing_token(self, mock_logger: MagicMock) -> None:
        """Test GitHub enabled but GITHUB_TOKEN not set."""
        settings = Settings(
            issue_tracker="github",
            github_repo="owner/repo",
            github_token="",
        )

        validate_issue_tracking(settings, mock_logger)

        mock_logger.warning.assert_called_once()
        assert "GITHUB_TOKEN not set" in mock_logger.warning.call_args[0][0]

    def test_github_fully_configured(self, mock_logger: MagicMock) -> None:
        """Test GitHub fully configured."""
        settings = Settings(
            issue_tracker="github",
            github_repo="owner/repo",
            github_token="ghp_token",
        )

        validate_issue_tracking(settings, mock_logger)

        mock_logger.info.assert_called_once()
        assert "owner/repo" in mock_logger.info.call_args[0][1]

    def test_linear_missing_credentials(self, mock_logger: MagicMock) -> None:
        """Test Linear enabled but credentials not set."""
        settings = Settings(
            issue_tracker="linear",
            linear_api_key="",
            linear_team_id="",
        )

        validate_issue_tracking(settings, mock_logger)

        mock_logger.warning.assert_called_once()
        assert "LINEAR_API_KEY not set" in mock_logger.warning.call_args[0][0]

    def test_linear_fully_configured(self, mock_logger: MagicMock) -> None:
        """Test Linear fully configured."""
        settings = Settings(
            issue_tracker="linear",
            linear_api_key="lin_api_key",
            linear_team_id="team123",
        )

        validate_issue_tracking(settings, mock_logger)

        mock_logger.info.assert_called_once()
        assert "team123" in mock_logger.info.call_args[0][1]
