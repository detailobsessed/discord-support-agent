"""Tests for OpenTelemetry instrumentation."""

from unittest.mock import patch

from discord_support_agent.config import Settings
from discord_support_agent.instrumentation import configure_instrumentation


class TestConfigureInstrumentation:
    """Tests for configure_instrumentation function."""

    def test_disabled_by_default(self) -> None:
        """Instrumentation should be disabled by default."""
        settings = Settings(discord_token="test-token")  # noqa: S106

        with patch("discord_support_agent.instrumentation.logfire") as mock_logfire:
            configure_instrumentation(settings)

            mock_logfire.configure.assert_not_called()
            mock_logfire.instrument_pydantic_ai.assert_not_called()

    def test_enabled_configures_logfire(self) -> None:
        """When enabled, should configure logfire with send_to_logfire=False."""
        settings = Settings(discord_token="test-token", otel_enabled=True)  # noqa: S106

        with patch("discord_support_agent.instrumentation.logfire") as mock_logfire:
            configure_instrumentation(settings)

            mock_logfire.configure.assert_called_once_with(
                send_to_logfire=False,
                service_name="discord-support-agent",
            )
            mock_logfire.instrument_pydantic_ai.assert_called_once()

    def test_httpx_instrumentation_disabled_by_default(self) -> None:
        """HTTPX instrumentation should be disabled by default."""
        settings = Settings(discord_token="test-token", otel_enabled=True)  # noqa: S106

        with patch("discord_support_agent.instrumentation.logfire") as mock_logfire:
            configure_instrumentation(settings)

            mock_logfire.instrument_httpx.assert_not_called()

    def test_httpx_instrumentation_when_enabled(self) -> None:
        """HTTPX instrumentation should be enabled when configured."""
        settings = Settings(
            discord_token="test-token",  # noqa: S106
            otel_enabled=True,
            otel_instrument_httpx=True,
        )

        with patch("discord_support_agent.instrumentation.logfire") as mock_logfire:
            configure_instrumentation(settings)

            mock_logfire.instrument_httpx.assert_called_once_with(capture_all=True)

    def test_custom_endpoint_in_settings(self) -> None:
        """Custom OTEL endpoint should be stored in settings."""
        settings = Settings(
            discord_token="test-token",  # noqa: S106
            otel_enabled=True,
            otel_exporter_endpoint="http://custom:4317",
        )

        assert settings.otel_exporter_endpoint == "http://custom:4317"
