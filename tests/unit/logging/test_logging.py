"""Unit tests for the structured logging subsystem."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import importlib
import inspect
import json
import logging
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import structlog
from structlog.contextvars import clear_contextvars

import backend.logging.config as _logging_config_mod
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
        # Verify colors=True explicitly to kill colors=None and colors=False mutations
        assert renderer._colors is True

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
        """Root logger at WARNING, backend.* namespace at INFO by default."""
        reset_logging()

        # Patch logging to verify root logger and backend namespace
        with (
            patch("backend.logging.config.logging.basicConfig") as mock_basic,
            patch("backend.logging.config.logging.getLogger") as mock_get_logger,
        ):
            mock_backend_logger = MagicMock()
            mock_get_logger.return_value = mock_backend_logger

            configure_logging()  # No args - use defaults

            # Root logger set to WARNING to suppress third-party debug noise
            mock_basic.assert_called_once()
            call_kwargs = mock_basic.call_args.kwargs
            assert call_kwargs["level"] == logging.WARNING
            assert call_kwargs["format"] == "%(message)s"
            assert call_kwargs["force"] is True

            # Backend namespace set to INFO (the requested default level)
            mock_get_logger.assert_called_once_with("backend")
            mock_backend_logger.setLevel.assert_called_once_with(logging.INFO)

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

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_default_level_is_info(self) -> None:
        """Backend namespace default must be INFO, root at WARNING."""
        reset_logging()
        with (
            patch("backend.logging.config.logging.basicConfig") as mock_basic,
            patch("backend.logging.config.logging.getLogger") as mock_get_logger,
        ):
            mock_backend_logger = MagicMock()
            mock_get_logger.return_value = mock_backend_logger

            configure_logging()  # No parameters

            # Root logger always WARNING to suppress third-party noise
            call_kwargs = mock_basic.call_args.kwargs
            assert call_kwargs["level"] == logging.WARNING
            # stream is sys.stderr (may be wrapped by colorama on Windows)
            assert call_kwargs["stream"] is not None  # Kills stream=None mutation
            assert call_kwargs["format"] == "%(message)s"

            # Backend namespace gets the requested level (INFO by default)
            mock_backend_logger.setLevel.assert_called_once_with(logging.INFO)

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_default_level_exact_string(self) -> None:
        """Default level parameter must be exact string 'INFO', not variations."""
        importlib.reload(_logging_config_mod)  # Re-execute def line for coverage attribution
        sig = inspect.signature(_logging_config_mod.configure_logging)
        # Verify exact default value - kills level="info", level="XXINFOXX" mutations
        assert sig.parameters["level"].default == "INFO"
        # Also call configure_logging so mutmut maps this test
        reset_logging()
        configure_logging()

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_default_renderer_exact_string(self) -> None:
        """Default renderer parameter must be exact string 'console', not variations."""
        importlib.reload(_logging_config_mod)  # Re-execute def line for coverage attribution
        sig = inspect.signature(_logging_config_mod.configure_logging)
        assert sig.parameters["renderer"].default == "console"
        # Also call configure_logging so mutmut maps this test
        reset_logging()
        configure_logging()

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_default_renderer_is_console(self) -> None:
        """Default renderer must be console for development."""
        reset_logging()
        with patch("backend.logging.config.build_shared_processors") as mock_build:
            mock_build.return_value = [structlog.processors.JSONRenderer()]
            configure_logging()  # No renderer parameter
            mock_build.assert_called_once_with("console")  # Kills renderer mutations

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_stderr_stream(self) -> None:
        """Logs must go to stderr, not stdout."""

        reset_logging()
        with patch("backend.logging.config.logging.basicConfig") as mock_basic:
            configure_logging()
            call_kwargs = mock_basic.call_args.kwargs
            # Verify stream parameter is set (not None, not removed)
            assert "stream" in call_kwargs
            assert call_kwargs["stream"] is not None  # Kills stream=None mutation
            # On Windows, sys.stderr may be wrapped by colorama, so check the attribute exists
            assert hasattr(call_kwargs["stream"], "write")  # Confirms it's a stream object
            assert call_kwargs["format"] == "%(message)s"
            assert call_kwargs["force"] is True

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_wrapper_class_is_filtering_bound_logger(self) -> None:
        """Wrapper class must filter by log level, not None."""
        reset_logging()
        configure_logging(level="WARNING")
        config = structlog.get_config()
        wrapper_class = config["wrapper_class"]
        # Verify it's a filtering bound logger class, not None
        assert wrapper_class is not None  # Kills wrapper_class=None mutation
        assert callable(wrapper_class)  # It should be a class
        # Verify it's a BoundLogger with filtering (structlog creates dynamic classes)
        assert "BoundLogger" in str(wrapper_class) or "Filtering" in str(wrapper_class)

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_passes_wrapper_class_kwarg(self) -> None:
        """structlog.configure must receive wrapper_class keyword argument."""
        reset_logging()
        with patch("backend.logging.config.structlog.configure") as mock_cfg:
            configure_logging()
            mock_cfg.assert_called_once()
            assert "wrapper_class" in mock_cfg.call_args.kwargs
            assert mock_cfg.call_args.kwargs["wrapper_class"] is not None

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_passes_context_class_kwarg(self) -> None:
        """structlog.configure must receive context_class=dict explicitly."""
        reset_logging()
        with patch("backend.logging.config.structlog.configure") as mock_cfg:
            configure_logging()
            mock_cfg.assert_called_once()
            assert "context_class" in mock_cfg.call_args.kwargs
            assert mock_cfg.call_args.kwargs["context_class"] is dict

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_context_class_is_dict(self) -> None:
        """Context class must be dict for JSON serialization."""
        reset_logging()
        configure_logging()
        config = structlog.get_config()
        assert config["context_class"] is dict  # Exact type, kills None mutation

    @pytest.mark.usefixtures("_reset_structlog")
    def test_invalid_level_falls_back_to_info(self) -> None:
        """Invalid log level must fall back to logging.INFO via getattr."""
        reset_logging()
        configure_logging(level="NONEXISTENT_LEVEL")
        assert logging.getLogger("backend").level == logging.INFO

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logger_factory_uses_stderr(self) -> None:
        """Logger factory must write to stderr."""
        reset_logging()
        configure_logging()
        config = structlog.get_config()
        factory = config["logger_factory"]
        assert isinstance(factory, structlog.PrintLoggerFactory)
        # Verify file parameter is set (not None)
        assert factory._file is not None  # Kills file=None mutation
        assert hasattr(factory._file, "write")  # Confirms it's a stream object

    @pytest.mark.usefixtures("_reset_structlog")
    def test_get_logger_auto_configures_with_exact_defaults(self) -> None:
        """get_logger() must configure with DEBUG + console when not configured."""
        reset_logging()
        with patch("backend.logging.config.configure_logging") as mock_config:
            get_logger("test")
            # Verify exact parameters - kills default mutations
            mock_config.assert_called_once_with(level="DEBUG", renderer="console")

    @pytest.mark.usefixtures("_reset_structlog")
    def test_get_logger_binds_name_not_none(self) -> None:
        """Logger name must be bound as provided, not None."""
        reset_logging()
        output = StringIO()
        configure_logging(renderer="json")
        structlog.configure(
            processors=structlog.get_config()["processors"],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )
        log = get_logger("test.module")  # Provide name
        log.info("test")
        data = json.loads(output.getvalue().strip())
        assert data["logger_name"] == "test.module"  # Kills logger_name=None mutation

    @pytest.mark.usefixtures("_reset_structlog")
    def test_reset_logging_sets_configured_to_false(self) -> None:
        """reset_logging() must set _configured to False, not None or True."""
        configure_logging()
        reset_logging()
        from backend.logging.config import _configured  # noqa: PLC0415

        assert _configured is False  # Exact value check

    @pytest.mark.usefixtures("_reset_structlog")
    def test_configure_logging_sets_configured_to_true(self) -> None:
        """configure_logging() must set _configured to True, not None or False."""
        reset_logging()
        configure_logging()
        from backend.logging.config import _configured  # noqa: PLC0415

        assert _configured is True  # Exact value check


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
