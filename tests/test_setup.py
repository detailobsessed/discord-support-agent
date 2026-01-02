"""Tests for setup.py interactive setup script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from setup import (
    check_gh_cli,
    create_repo,
    get_gh_orgs,
    get_gh_username,
    repo_exists,
    run_command,
    update_env_file,
)


class TestRunCommand:
    """Tests for run_command helper."""

    def test_run_command_success(self) -> None:
        """Test running a successful command."""
        result = run_command(["echo", "hello"])
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_run_command_failure(self) -> None:
        """Test running a failing command."""
        # Use cross-platform Python invocation instead of shell 'false'
        result = run_command([sys.executable, "-c", "import sys; sys.exit(1)"])
        assert result.returncode != 0


class TestCheckGhCli:
    """Tests for check_gh_cli function."""

    def test_gh_not_installed(self) -> None:
        """Test when gh CLI is not installed."""
        with patch("setup.shutil.which", return_value=None):
            assert check_gh_cli() is False

    def test_gh_not_authenticated(self) -> None:
        """Test when gh CLI is installed but not authenticated."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch("setup.shutil.which", return_value="/usr/bin/gh"),
            patch("setup.run_command", return_value=mock_result),
        ):
            assert check_gh_cli() is False

    def test_gh_authenticated(self) -> None:
        """Test when gh CLI is installed and authenticated."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("setup.shutil.which", return_value="/usr/bin/gh"),
            patch("setup.run_command", return_value=mock_result),
        ):
            assert check_gh_cli() is True


class TestGetGhUsername:
    """Tests for get_gh_username function."""

    def test_get_username_success(self) -> None:
        """Test getting username successfully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "testuser\n"

        with patch("setup.run_command", return_value=mock_result):
            assert get_gh_username() == "testuser"

    def test_get_username_failure(self) -> None:
        """Test when getting username fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("setup.run_command", return_value=mock_result):
            assert get_gh_username() is None


class TestGetGhOrgs:
    """Tests for get_gh_orgs function."""

    def test_get_orgs_success(self) -> None:
        """Test getting organizations successfully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "org1\norg2\norg3\n"

        with patch("setup.run_command", return_value=mock_result):
            assert get_gh_orgs() == ["org1", "org2", "org3"]

    def test_get_orgs_none(self) -> None:
        """Test when user has no organizations."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("setup.run_command", return_value=mock_result):
            assert get_gh_orgs() == []

    def test_get_orgs_failure(self) -> None:
        """Test when getting organizations fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("setup.run_command", return_value=mock_result):
            assert get_gh_orgs() == []


class TestRepoExists:
    """Tests for repo_exists function."""

    def test_repo_exists(self) -> None:
        """Test when repository exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("setup.run_command", return_value=mock_result):
            assert repo_exists("owner/repo") is True

    def test_repo_not_exists(self) -> None:
        """Test when repository does not exist."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("setup.run_command", return_value=mock_result):
            assert repo_exists("owner/repo") is False


class TestCreateRepo:
    """Tests for create_repo function."""

    def test_create_repo_private(self) -> None:
        """Test creating a private repository."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("setup.run_command", return_value=mock_result) as mock_run:
            result = create_repo("owner/repo", private=True)
            assert result is True
            # Verify --private flag was passed
            call_args = mock_run.call_args[0][0]
            assert "--private" in call_args

    def test_create_repo_public(self) -> None:
        """Test creating a public repository."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("setup.run_command", return_value=mock_result) as mock_run:
            result = create_repo("owner/repo", private=False)
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "--public" in call_args

    def test_create_repo_failure(self) -> None:
        """Test when repository creation fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("setup.run_command", return_value=mock_result):
            assert create_repo("owner/repo") is False


class TestUpdateEnvFile:
    """Tests for update_env_file function."""

    def test_create_new_env_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test creating a new .env file."""
        monkeypatch.chdir(tmp_path)

        update_env_file("TEST_KEY", "test_value")

        env_file = tmp_path / ".env"
        assert env_file.exists()
        assert "TEST_KEY=test_value" in env_file.read_text()

    def test_update_existing_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test updating an existing key in .env file."""
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=old_value\nOTHER_KEY=other\n")

        update_env_file("EXISTING_KEY", "new_value")

        content = env_file.read_text()
        assert "EXISTING_KEY=new_value" in content
        assert "OTHER_KEY=other" in content
        assert "old_value" not in content

    def test_update_commented_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test updating a commented-out key in .env file."""
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("# GITHUB_REPO=placeholder\nOTHER=value\n")

        update_env_file("GITHUB_REPO", "owner/repo")

        content = env_file.read_text()
        assert "GITHUB_REPO=owner/repo" in content
        assert "# GITHUB_REPO" not in content

    def test_append_new_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test appending a new key to existing .env file."""
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value\n")

        update_env_file("NEW_KEY", "new_value")

        content = env_file.read_text()
        assert "EXISTING=value" in content
        assert "NEW_KEY=new_value" in content

    def test_does_not_match_prefix_keys(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that updating a key doesn't affect keys with similar prefixes."""
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        # GITHUB_TOKEN_EXTRA should NOT be matched when updating GITHUB_TOKEN
        env_file.write_text("GITHUB_TOKEN_EXTRA=extra_value\nOTHER=value\n")

        update_env_file("GITHUB_TOKEN", "new_token")

        content = env_file.read_text()
        # Original key with longer name should be preserved
        assert "GITHUB_TOKEN_EXTRA=extra_value" in content
        # New key should be appended (not replace the prefix match)
        assert "GITHUB_TOKEN=new_token" in content
