"""Unit tests for the structured logging subsystem."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import logging
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import structlog
from structlog.contextvars import clear_contextvars

from backend.logging.catalog import MessageCode, format_message
from backend.logging.config import configure_logging, get_logger, reset_logging

if TYPE_CHECKING:
    from collections.abc import Generator
from backend.logging.utils import (
    end_operation,
    generate_correlation_id,
    log_with_code,
    start_operation,
)


@pytest.fixture(autouse=True)
def _clean_contextvars() -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure no contextvars leak between tests."""
    clear_contextvars()


@pytest.fixture
def _reset_structlog() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Reset structlog config after test (used by config tests)."""
    yield
    reset_logging()


# ---------------------------------------------------------------------------
# Message Catalog tests
# ---------------------------------------------------------------------------


class TestMessageCatalog:
    """Tests for backend.logging.catalog."""

    def test_all_codes_have_templates(self) -> None:
        """Every MessageCode member must appear in the catalog."""
        from backend.logging.catalog import (  # noqa: PLC0415
            _CATALOG,
        )

        for code in MessageCode:
            assert code in _CATALOG, f"Missing catalog template for {code.name}"

    def test_format_message_basic(self) -> None:
        msg = format_message(
            MessageCode.MQTT_CONNECTION_SUCCESS,
            broker="localhost",
            port=1883,
            client_id="test",
        )
        assert "localhost" in msg
        assert "1883" in msg
        assert "test" in msg

    def test_format_message_with_attempt_counter(self) -> None:
        msg = format_message(
            MessageCode.MQTT_CONNECTION_FAILED,
            broker="192.168.1.1",
            port=1883,
            attempt=2,
            max_attempts=5,
            error="Connection refused",
        )
        assert "2/5" in msg
        assert "Connection refused" in msg
        assert "192.168.1.1" in msg

    def test_format_message_missing_kwargs_returns_template(self) -> None:
        """Graceful degradation: missing kwargs return raw template."""
        msg = format_message(MessageCode.MQTT_CONNECTION_FAILED)
        # Should not raise — returns the un-interpolated template
        assert "{broker}" in msg

    def test_format_message_device_registered(self) -> None:
        msg = format_message(
            MessageCode.DEVICE_REGISTERED,
            device_id="light_01",
            device_type="smart_light",
        )
        assert "light_01" in msg
        assert "smart_light" in msg

    def test_message_code_values_are_unique(self) -> None:
        values = [c.value for c in MessageCode]
        assert len(values) == len(set(values)), "Duplicate code values found"

    def test_message_code_string_representation(self) -> None:
        assert MessageCode.MQTT_CONNECTION_INITIATED.value == "MQTT_001"
        assert MessageCode.DEVICE_REGISTERED.value == "DEV_001"
        assert MessageCode.DB_CONNECTION_SUCCESS.value == "DB_001"
        assert MessageCode.SYS_STARTUP.value == "SYS_001"


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestLoggingConfig:
    """Tests for backend.logging.config."""

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_json_renderer(self) -> None:
        """JSON renderer produces parseable output."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")

        # Reconfigure to write to our StringIO
        processors = structlog.get_config()["processors"]
        structlog.configure(
            processors=processors,
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        log = structlog.get_logger()
        log.info("test_event", key="value")

        raw = output.getvalue().strip()
        data = json.loads(raw)
        assert data["event"] == "test_event"
        assert data["key"] == "value"
        assert data["level"] == "info"
        assert "timestamp" in data

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_console_renderer(self) -> None:
        """Console renderer produces human-readable output (no crash)."""
        output = StringIO()
        reset_logging()
        configure_logging(level="INFO", renderer="console")

        processors = structlog.get_config()["processors"]
        structlog.configure(
            processors=processors,
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        log = structlog.get_logger()
        log.info("human_readable_test", device="light_01")

        raw = output.getvalue()
        assert "human_readable_test" in raw

    @pytest.mark.usefixtures("_reset_structlog")
    def test_get_logger_auto_configures(self) -> None:
        """get_logger() applies default config if not yet configured."""
        reset_logging()
        log = get_logger("auto_test")
        # Should not raise
        log.info("auto_configured_event")

    @pytest.mark.usefixtures("_reset_structlog")
    def test_get_logger_without_name(self) -> None:
        """get_logger() without a name returns a logger without logger_name binding."""
        reset_logging()
        log = get_logger()
        assert log is not None
        # Should not raise
        log.info("unnamed_logger_event")

    @pytest.mark.usefixtures("_reset_structlog")
    def test_app_context_injected(self) -> None:
        """Every log entry contains app='smartnest'."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        log = structlog.get_logger()
        log.info("check_app")

        data = json.loads(output.getvalue().strip())
        assert data["app"] == "smartnest"

    def test_build_processors_console_has_color_renderer(self) -> None:
        """Console renderer must have colors enabled for readability."""
        from backend.logging.config import build_shared_processors  # noqa: PLC0415

        processors = build_shared_processors("console")

        # Last processor should be ConsoleRenderer (colors enabled by default)
        renderer = processors[-1]
        assert isinstance(renderer, structlog.dev.ConsoleRenderer)
        # Note: Not checking _colors (protected attribute). Integration tests
        # verify colored output behavior instead.

    def test_build_processors_json_has_json_renderer(self) -> None:
        """JSON renderer must be used for machine-parseable logs."""
        from backend.logging.config import build_shared_processors  # noqa: PLC0415

        processors = build_shared_processors("json")

        # Last processor should be JSONRenderer
        renderer = processors[-1]
        assert isinstance(renderer, structlog.processors.JSONRenderer)

        # Must include format_exc_info before JSONRenderer
        assert structlog.processors.format_exc_info in processors

    def test_build_processors_has_timestamp_processor(self) -> None:
        """Timestamp processor must be included with ISO format."""
        from backend.logging.config import build_shared_processors  # noqa: PLC0415

        processors = build_shared_processors("console")

        # Find TimeStamper processor and verify ISO format
        timestampers = [p for p in processors if isinstance(p, structlog.processors.TimeStamper)]
        assert len(timestampers) == 1
        # Verify the TimeStamper uses "iso" format
        assert timestampers[0].fmt == "iso"

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_defaults(self) -> None:
        """Default level must be INFO for production safety."""
        reset_logging()

        # Patch logging.basicConfig to verify default level
        with patch("backend.logging.config.logging.basicConfig") as mock_basic:
            configure_logging()  # No args - use defaults

            # Verify INFO level was used (not DEBUG)
            mock_basic.assert_called_once()
            call_kwargs = mock_basic.call_args.kwargs
            assert call_kwargs["level"] == logging.INFO
            assert call_kwargs["format"] == "%(message)s"
            assert call_kwargs["force"] is True

        config = structlog.get_config()
        # Verify cache is enabled
        assert config["cache_logger_on_first_use"] is True

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_level_case_insensitive(self) -> None:
        """Level string must be normalized to uppercase."""
        output = StringIO()
        reset_logging()
        configure_logging(level="debug")  # lowercase

        # Should work - getattr with .upper() handles it
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        log = structlog.get_logger()
        log.debug("test_lowercase_level")

        # Verify debug log was emitted
        assert "test_lowercase_level" in output.getvalue()


# ---------------------------------------------------------------------------
# Utilities tests
# ---------------------------------------------------------------------------


class TestCorrelationTracking:
    """Tests for start_operation / end_operation."""

    def test_start_operation_returns_correlation_id(self) -> None:
        cid = start_operation("test_op")
        assert isinstance(cid, str)
        assert len(cid) == 12  # hex UUID fragment
        end_operation()

    def test_correlation_id_uniqueness(self) -> None:
        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100

    @pytest.mark.usefixtures("_reset_structlog")
    def test_context_appears_in_logs(self) -> None:
        """Bound context from start_operation flows into log output."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        cid = start_operation("device_cmd", device_id="light_01")
        log = structlog.get_logger()
        log.info("test_correlated")
        end_operation("device_id")

        data = json.loads(output.getvalue().strip())
        assert data["correlation_id"] == cid
        assert data["operation"] == "device_cmd"
        assert data["device_id"] == "light_01"

    @pytest.mark.usefixtures("_reset_structlog")
    def test_end_operation_clears_context(self) -> None:
        """After end_operation, correlation context is gone."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        start_operation("op1")
        end_operation()

        # Clear buffer
        output.truncate(0)
        output.seek(0)

        log = structlog.get_logger()
        log.info("after_end")

        data = json.loads(output.getvalue().strip())
        assert "correlation_id" not in data
        assert "operation" not in data


class TestLogWithCode:
    """Tests for catalog-aware log_with_code helper."""

    @pytest.mark.usefixtures("_reset_structlog")
    def test_log_with_code_json_output(self) -> None:
        """log_with_code emits msg_id and formatted message."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        log = structlog.get_logger()
        log_with_code(
            log,
            "info",
            MessageCode.MQTT_SUBSCRIBE_SUCCESS,
            topic="smartnest/device/+/state",
            qos=1,
        )

        data = json.loads(output.getvalue().strip())
        assert data["msg_id"] == "MQTT_010"
        assert "smartnest/device/+/state" in data["event"]
        assert data["topic"] == "smartnest/device/+/state"
        assert data["qos"] == 1

    @pytest.mark.usefixtures("_reset_structlog")
    def test_log_with_code_error_level(self) -> None:
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        log = structlog.get_logger()
        log_with_code(
            log,
            "error",
            MessageCode.MQTT_PUBLISH_FAILED,
            topic="smartnest/test",
            rc=4,
        )

        data = json.loads(output.getvalue().strip())
        assert data["level"] == "error"
        assert data["msg_id"] == "MQTT_008"

    def test_log_with_code_suppresses_os_error(self) -> None:
        """log_with_code gracefully handles OSError during logging."""
        log = MagicMock()
        # Simulate logging failure with OSError (e.g., closed file descriptor)
        log.info.side_effect = OSError("Bad file descriptor")

        # Should not raise - error is suppressed
        log_with_code(
            log,
            "info",
            MessageCode.MQTT_SUBSCRIBE_SUCCESS,
            topic="smartnest/test",
        )

        # Verify the log attempt was made
        log.info.assert_called_once()


class TestChildLoggerPattern:
    """Tests for bound (child) logger pattern with automatic scope context."""

    @pytest.mark.usefixtures("_reset_structlog")
    def test_bound_logger_carries_context(self) -> None:
        """Binding device_id to a logger makes it appear in all subsequent logs."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        parent = structlog.get_logger()
        child = parent.bind(device_id="temp_sensor_01", device_type="sensor")
        child.info("sensor_reading", value=21.5, unit="celsius")

        data = json.loads(output.getvalue().strip())
        assert data["device_id"] == "temp_sensor_01"
        assert data["device_type"] == "sensor"
        assert data["value"] == 21.5

    @pytest.mark.usefixtures("_reset_structlog")
    def test_bound_logger_does_not_pollute_parent(self) -> None:
        """Parent logger should not carry child bindings."""
        output = StringIO()
        reset_logging()
        configure_logging(level="DEBUG", renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        parent = structlog.get_logger()
        _child = parent.bind(device_id="light_01")

        # Clear buffer
        output.truncate(0)
        output.seek(0)

        parent.info("parent_only_event")
        data = json.loads(output.getvalue().strip())
        assert "device_id" not in data
