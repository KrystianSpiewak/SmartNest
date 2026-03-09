"""Global test configuration.

Configures structured logging for all tests (JSON renderer for easy assertions).
Provides shared test fixtures to avoid duplication across test modules.
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import MagicMock

import paho.mqtt.client as mqtt
import pytest
import structlog

from backend.logging.config import configure_logging
from backend.mqtt.config import MQTTConfig

# Wrap logging configuration to handle mutation testing scenarios
# where stdout/stderr may be closed or redirected improperly.
with contextlib.suppress(OSError, ValueError):
    # Configure once at import time so every test module gets consistent logging.
    # Use console renderer for human-readable test output.
    configure_logging(level="DEBUG", renderer="console")

# Redirect structlog output to a memory buffer so tests survive subprocess
# environments (e.g., mutmut) where stderr may be closed at runtime.
structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(file=io.StringIO()),
    cache_logger_on_first_use=False,
)


# ============================================================================
# MQTT Fixtures (Shared across unit and integration tests)
# ============================================================================


@pytest.fixture
def mqtt_config() -> MQTTConfig:
    """Default MQTT configuration for tests.

    Returns standard localhost configuration. Override client_id in individual
    tests if needed for isolation.
    """
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="test_client",
    )


@pytest.fixture
def mock_paho_client() -> MagicMock:
    """Mocked paho.mqtt.client.Client instance.

    Pre-configured with common return values for publish/subscribe operations.
    Tests can override specific behaviors as needed.
    """
    mock = MagicMock(spec=mqtt.Client)
    mock.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_SUCCESS)
    mock.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    mock.connect.return_value = mqtt.MQTT_ERR_SUCCESS
    mock.disconnect.return_value = mqtt.MQTT_ERR_SUCCESS
    return mock
