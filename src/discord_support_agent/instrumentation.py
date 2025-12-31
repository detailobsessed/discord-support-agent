"""OpenTelemetry instrumentation using Logfire SDK with local backend."""

import logging

import logfire

from discord_support_agent.config import Settings

logger = logging.getLogger(__name__)


def configure_instrumentation(settings: Settings) -> None:
    """Configure Logfire instrumentation for Pydantic AI with local OTel backend.

    This uses the Logfire SDK but sends data to a local OpenTelemetry collector
    instead of the Logfire cloud service. By default, it exports to otel-tui
    or any OTLP-compatible backend at the configured endpoint.

    The OTEL_EXPORTER_OTLP_ENDPOINT environment variable (set from
    settings.otel_exporter_endpoint in main.py) controls where traces
    are sent (default: http://localhost:4318).

    Args:
        settings: Application settings containing instrumentation configuration.
    """
    if not settings.otel_enabled:
        logger.debug("OpenTelemetry instrumentation disabled")
        return

    # Configure Logfire to NOT send to Logfire cloud
    logfire.configure(
        send_to_logfire=False,
        service_name="discord-support-agent",
    )

    # Instrument Pydantic AI agents
    logfire.instrument_pydantic_ai()

    # Optionally instrument HTTPX for raw request visibility
    if settings.otel_instrument_httpx:
        logfire.instrument_httpx(capture_all=True)

    logger.info(
        "OpenTelemetry instrumentation enabled, exporting to %s",
        settings.otel_exporter_endpoint,
    )
