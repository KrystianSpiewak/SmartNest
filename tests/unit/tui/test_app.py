"""Unit tests for SmartNest TUI application."""

from __future__ import annotations

import signal
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest
from rich.console import Console

from backend.logging.catalog import MessageCode
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig
from backend.tui.app import SmartNestTUI
from backend.tui.screens.dashboard import DashboardScreen
from backend.tui.screens.device_detail import DeviceDetailScreen
from backend.tui.screens.device_list import DeviceListScreen
from backend.tui.screens.sensor_view import SensorViewScreen
from backend.tui.screens.settings import SettingsScreen


class TestSmartNestTUIInit:
    """Tests for SmartNestTUI initialization."""

    def test_creates_console(self) -> None:
        """TUI creates Rich Console instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.console, Console)

    def test_creates_dashboard(self) -> None:
        """TUI creates a DashboardScreen instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.dashboard, DashboardScreen)
        assert tui.dashboard.console is tui.console

    def test_creates_device_list_screen(self) -> None:
        """TUI creates a DeviceListScreen instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.device_list, DeviceListScreen)
        assert tui.device_list.console is tui.console
        assert tui.device_list.http_client is tui.http_client

    def test_creates_device_detail_screen(self) -> None:
        """TUI creates a DeviceDetailScreen instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.device_detail, DeviceDetailScreen)
        assert tui.device_detail.console is tui.console
        assert tui.device_detail.http_client is tui.http_client

    def test_creates_sensor_view_screen(self) -> None:
        """TUI creates a SensorViewScreen instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.sensor_view, SensorViewScreen)
        assert tui.sensor_view.console is tui.console
        assert tui.sensor_view.http_client is tui.http_client

    def test_creates_settings_screen(self) -> None:
        """TUI creates a SettingsScreen instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.settings, SettingsScreen)
        assert tui.settings.console is tui.console
        assert tui.settings.http_client is tui.http_client

    def test_current_screen_defaults_to_dashboard(self) -> None:
        """TUI initializes with dashboard as current screen."""
        tui = SmartNestTUI()
        assert tui.current_screen == "dashboard"

    def test_initially_not_running(self) -> None:
        """TUI is not running before startup() called."""
        tui = SmartNestTUI()
        assert tui.is_running is False

    def test_creates_http_client(self) -> None:
        """TUI creates HTTP client with default base URL."""
        tui = SmartNestTUI()
        assert isinstance(tui.http_client, httpx.Client)
        assert tui.api_base_url == "http://localhost:8000"

    def test_accepts_custom_api_url(self) -> None:
        """TUI accepts custom API base URL."""
        tui = SmartNestTUI(api_base_url="http://example.com:9000")
        assert tui.api_base_url == "http://example.com:9000"

    def test_creates_mqtt_client(self) -> None:
        """TUI creates MQTT client with default config."""
        tui = SmartNestTUI()
        assert isinstance(tui.mqtt_client, SmartNestMQTTClient)
        assert isinstance(tui.mqtt_config, MQTTConfig)
        assert tui.mqtt_config.client_id == "smartnest_tui"

    def test_accepts_custom_mqtt_config(self) -> None:
        """TUI accepts custom MQTT configuration."""
        custom_config = MQTTConfig(broker="mqtt.example.com", port=8883, client_id="custom_tui")
        tui = SmartNestTUI(mqtt_config=custom_config)
        assert tui.mqtt_config is custom_config
        assert tui.mqtt_config.broker == "mqtt.example.com"

    def test_initializes_system_status_dict(self) -> None:
        """TUI initializes empty system_status dict."""
        tui = SmartNestTUI()
        assert tui.system_status == {}

    def test_logs_initialization(self) -> None:
        """TUI logs initialization with correct message code."""
        with patch("backend.tui.app.log_with_code") as mock_log:
            SmartNestTUI()
            # Verify log_with_code was called with TUI_INITIALIZED
            assert mock_log.call_count == 1
            call_args = mock_log.call_args
            # Check message code (3rd positional argument)
            assert call_args.args[2] == MessageCode.TUI_INITIALIZED
            # Check log level (2nd positional argument)
            assert call_args.args[1] == "debug"


class TestSmartNestTUIStartup:
    """Tests for TUI startup."""

    def test_startup_sets_running_flag(self) -> None:
        """startup() sets is_running to True."""
        tui = SmartNestTUI()
        with patch.object(tui.mqtt_client, "connect"):
            tui.startup()
        assert tui.is_running is True

    def test_startup_logs_with_code(self) -> None:
        """startup() logs TUI_STARTED and TUI_MQTT_CONNECTED message codes."""
        tui = SmartNestTUI()
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch.object(tui.mqtt_client, "connect"),
        ):
            # Clear initialization log call
            mock_log.reset_mock()
            tui.startup()
            # Should log TUI_STARTED
            assert any(call.args[2] == MessageCode.TUI_STARTED for call in mock_log.call_args_list)
            # Should log TUI_MQTT_CONNECTED
            assert any(
                call.args[2] == MessageCode.TUI_MQTT_CONNECTED for call in mock_log.call_args_list
            )

    def test_startup_clears_console(self) -> None:
        """startup() clears the console before rendering."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.console, "clear") as mock_clear,
            patch.object(tui.mqtt_client, "connect"),
        ):
            tui.startup()
            # Should clear console once
            mock_clear.assert_called_once()

    def test_startup_connects_mqtt_client(self) -> None:
        """startup() connects to MQTT broker."""
        tui = SmartNestTUI()
        with patch.object(tui.mqtt_client, "connect") as mock_connect:
            tui.startup()
            # Should connect to MQTT broker
            mock_connect.assert_called_once()

    def test_startup_subscribes_to_system_status(self) -> None:
        """startup() subscribes to smartnest/system/status topic."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui.mqtt_client, "subscribe") as mock_subscribe,
            patch.object(tui.mqtt_client, "add_topic_handler"),
        ):
            tui.startup()
            # Should subscribe to system status topic
            mock_subscribe.assert_called_once_with("smartnest/system/status")

    def test_startup_renders_dashboard(self) -> None:
        """startup() renders the dashboard screen."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui.dashboard, "render") as mock_render,
        ):
            tui.startup()
            # Should render dashboard once
            mock_render.assert_called_once()

    def test_startup_fetches_device_count(self) -> None:
        """startup() fetches device count from API."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui, "_fetch_device_count", return_value=5) as mock_fetch,
        ):
            tui.startup()
            # Should call _fetch_device_count once
            mock_fetch.assert_called_once()

    def test_startup_passes_device_count_to_dashboard(self) -> None:
        """startup() passes device count to dashboard.render()."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui, "_fetch_device_count", return_value=7),
            patch.object(tui.dashboard, "render") as mock_render,
        ):
            tui.startup()
            # Should pass device_count=7 to render()
            mock_render.assert_called_once_with(device_count=7)


class TestSmartNestTUIShutdown:
    """Tests for TUI shutdown."""

    def test_shutdown_clears_running_flag(self) -> None:
        """shutdown() sets is_running to False."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch("sys.exit"),
        ):
            tui.shutdown()
        assert tui.is_running is False

    def test_shutdown_disconnects_mqtt_client(self) -> None:
        """shutdown() disconnects from MQTT broker."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect") as mock_disconnect,
            patch("sys.exit"),
        ):
            tui.shutdown()
            # Should disconnect MQTT client
            mock_disconnect.assert_called_once()

    def test_shutdown_closes_http_client(self) -> None:
        """shutdown() closes the HTTP client."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch.object(tui.http_client, "close") as mock_close,
            patch("sys.exit"),
        ):
            tui.shutdown()
            # Should close HTTP client
            mock_close.assert_called_once()

    def test_shutdown_idempotent(self) -> None:
        """shutdown() can be called multiple times safely."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch("sys.exit"),
        ):
            tui.shutdown()
            # Second call should be no-op (is_running already False)
            tui.shutdown()


class TestSmartNestTUIFetchDeviceCount:
    """Tests for _fetch_device_count() method."""

    def test_fetch_device_count_success(self) -> None:
        """_fetch_device_count() returns count on successful API call."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {"count": 42}

        with patch.object(tui.http_client, "get", return_value=mock_response) as mock_get:
            count = tui._fetch_device_count()

        assert count == 42
        mock_get.assert_called_once_with("/api/devices/count")
        mock_response.raise_for_status.assert_called_once()

    def test_fetch_device_count_http_error(self) -> None:
        """_fetch_device_count() returns None on HTTP error."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        with (
            patch.object(tui.http_client, "get", return_value=mock_response),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            count = tui._fetch_device_count()

        assert count is None
        # Should log error
        assert any(call.args[2] == MessageCode.TUI_API_ERROR for call in mock_log.call_args_list)

    def test_fetch_device_count_connection_error(self) -> None:
        """_fetch_device_count() returns None on connection error."""
        tui = SmartNestTUI()

        with (
            patch.object(
                tui.http_client, "get", side_effect=httpx.ConnectError("Connection refused")
            ),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            count = tui._fetch_device_count()

        assert count is None
        # Should log error
        assert any(call.args[2] == MessageCode.TUI_API_ERROR for call in mock_log.call_args_list)

    def test_fetch_device_count_timeout(self) -> None:
        """_fetch_device_count() returns None on timeout."""
        tui = SmartNestTUI()

        with (
            patch.object(tui.http_client, "get", side_effect=httpx.TimeoutException("Timeout")),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            count = tui._fetch_device_count()

        assert count is None
        # Should log error
        assert any(call.args[2] == MessageCode.TUI_API_ERROR for call in mock_log.call_args_list)
        tui = SmartNestTUI()
        tui.is_running = True
        with patch("sys.exit"):
            tui.shutdown()
            # Second call should be no-op
            tui.shutdown()
        assert tui.is_running is False

    def test_shutdown_logs_with_code(self) -> None:
        """shutdown() logs TUI_SHUTDOWN message code."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch("sys.exit"),
        ):
            # Clear initialization log call
            mock_log.reset_mock()
            tui.shutdown()
            # Should log TUI_SHUTDOWN
            assert any(call.args[2] == MessageCode.TUI_SHUTDOWN for call in mock_log.call_args_list)

    def test_shutdown_logs_mqtt_disconnection(self) -> None:
        """shutdown() logs MQTT disconnection with message code."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch("backend.tui.app.log_with_code") as mock_log,
            patch("sys.exit"),
        ):
            mock_log.reset_mock()
            tui.shutdown()
            # Should log TUI_MQTT_DISCONNECTED
            assert any(
                call.args[2] == MessageCode.TUI_MQTT_DISCONNECTED
                for call in mock_log.call_args_list
            )

    def test_shutdown_prints_goodbye(self) -> None:
        """shutdown() prints goodbye message to console."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch.object(tui.console, "print") as mock_print,
            patch("sys.exit"),
        ):
            tui.shutdown()
            # Should print shutdown message
            assert mock_print.call_count >= 1
            # Should contain "Shutting down"
            printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
            assert "Shutting down" in printed_text


class TestSmartNestTUIMQTTCallbacks:
    """Tests for MQTT callback handlers."""

    def test_on_system_status_parses_json_payload(self) -> None:
        """_on_system_status() parses JSON payload and updates system_status."""
        tui = SmartNestTUI()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b'{"status": "online", "devices": 5}'

        with patch("backend.tui.app.log_with_code"):
            tui._on_system_status(mock_client, None, mock_message)

        # Should update system_status with parsed payload
        assert tui.system_status == {"status": "online", "devices": 5}

    def test_on_system_status_logs_message_received(self) -> None:
        """_on_system_status() logs message received with topic."""
        tui = SmartNestTUI()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b'{"status": "online"}'

        with patch("backend.tui.app.log_with_code") as mock_log:
            tui._on_system_status(mock_client, None, mock_message)

        # Should log TUI_MQTT_MESSAGE_RECEIVED
        assert any(
            call.args[2] == MessageCode.TUI_MQTT_MESSAGE_RECEIVED
            for call in mock_log.call_args_list
        )

    def test_on_system_status_handles_invalid_json(self) -> None:
        """_on_system_status() handles invalid JSON gracefully."""
        tui = SmartNestTUI()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b"not valid json"

        with patch("backend.tui.app.log_with_code") as mock_log:
            tui._on_system_status(mock_client, None, mock_message)

        # Should log TUI_MQTT_MESSAGE_PARSE_ERROR
        assert any(
            call.args[2] == MessageCode.TUI_MQTT_MESSAGE_PARSE_ERROR
            for call in mock_log.call_args_list
        )
        # system_status should remain unchanged (empty)
        assert tui.system_status == {}

    def test_on_system_status_handles_unicode_decode_error(self) -> None:
        """_on_system_status() handles unicode decode errors."""
        tui = SmartNestTUI()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b"\xff\xfe"  # Invalid UTF-8

        with patch("backend.tui.app.log_with_code") as mock_log:
            tui._on_system_status(mock_client, None, mock_message)

        # Should log TUI_MQTT_MESSAGE_PARSE_ERROR
        assert any(
            call.args[2] == MessageCode.TUI_MQTT_MESSAGE_PARSE_ERROR
            for call in mock_log.call_args_list
        )

    def test_on_system_status_updates_existing_state(self) -> None:
        """_on_system_status() replaces existing system_status."""
        tui = SmartNestTUI()
        tui.system_status = {"old": "data"}

        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b'{"status": "offline"}'

        with patch("backend.tui.app.log_with_code"):
            tui._on_system_status(mock_client, None, mock_message)

        # Should replace old data with new
        assert tui.system_status == {"status": "offline"}
        assert "old" not in tui.system_status


class TestSmartNestTUISignalHandlers:
    """Tests for signal handler registration."""

    def test_sigint_handler_registered(self) -> None:
        """SIGINT handler is registered during initialization."""
        with patch("signal.signal") as mock_signal:
            tui = SmartNestTUI()
            # Should register SIGINT handler
            sigint_calls = [
                call for call in mock_signal.call_args_list if call.args[0] == signal.SIGINT
            ]
            assert len(sigint_calls) == 1
            assert sigint_calls[0].args[1] == tui._handle_sigint

    def test_sigterm_handler_registered(self) -> None:
        """SIGTERM handler is registered during initialization."""
        with patch("signal.signal") as mock_signal:
            tui = SmartNestTUI()
            # Should register SIGTERM handler
            sigterm_calls = [
                call for call in mock_signal.call_args_list if call.args[0] == signal.SIGTERM
            ]
            assert len(sigterm_calls) == 1
            assert sigterm_calls[0].args[1] == tui._handle_sigterm

    def test_sigint_handler_logs_signal(self) -> None:
        """SIGINT handler logs shutdown request with signal name."""
        tui = SmartNestTUI()
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch.object(tui, "shutdown"),
        ):
            mock_log.reset_mock()
            tui._handle_sigint(2, None)  # SIGINT = 2
            # Should log with signal name
            assert any(
                call.args[2] == MessageCode.TUI_SHUTDOWN_REQUESTED
                and "signal" in call.kwargs
                and call.kwargs["signal"] == "SIGINT"
                for call in mock_log.call_args_list
            )

    def test_sigterm_handler_logs_signal(self) -> None:
        """SIGTERM handler logs shutdown request with signal name."""
        tui = SmartNestTUI()
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch.object(tui, "shutdown"),
        ):
            mock_log.reset_mock()
            tui._handle_sigterm(15, None)  # SIGTERM = 15
            # Should log with signal name
            assert any(
                call.args[2] == MessageCode.TUI_SHUTDOWN_REQUESTED
                and "signal" in call.kwargs
                and call.kwargs["signal"] == "SIGTERM"
                for call in mock_log.call_args_list
            )

    def test_sigint_handler_calls_shutdown(self) -> None:
        """SIGINT handler calls shutdown()."""
        tui = SmartNestTUI()
        with patch.object(tui, "shutdown") as mock_shutdown:
            tui._handle_sigint(2, None)
            mock_shutdown.assert_called_once()

    def test_sigterm_handler_calls_shutdown(self) -> None:
        """SIGTERM handler calls shutdown()."""
        tui = SmartNestTUI()
        with patch.object(tui, "shutdown") as mock_shutdown:
            tui._handle_sigterm(15, None)
            mock_shutdown.assert_called_once()


class TestSmartNestTUIRun:
    """Tests for TUI run() method."""

    def test_run_calls_startup(self) -> None:
        """run() calls startup() before main loop."""
        tui = SmartNestTUI()
        with (
            patch.object(tui, "startup") as mock_startup,
            patch("time.sleep", side_effect=KeyboardInterrupt),  # Exit loop immediately
            patch.object(tui, "shutdown"),
        ):
            tui.is_running = True  # Simulate startup setting this
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            mock_startup.assert_called_once()

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="Windows-specific Ctrl+C behavior (signal.pause missing)",
    )
    def test_run_calls_shutdown_on_keyboard_interrupt(self) -> None:
        """run() calls shutdown() when KeyboardInterrupt raised."""
        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch("time.sleep", side_effect=KeyboardInterrupt),
            patch.object(tui, "shutdown") as mock_shutdown,
        ):
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            # shutdown() called in finally block
            mock_shutdown.assert_called_once()

    def test_run_handles_graceful_shutdown(self) -> None:
        """run() handles graceful shutdown in finally block."""
        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch("time.sleep", side_effect=KeyboardInterrupt),
            patch("sys.exit") as mock_exit,
            patch.object(tui.console, "print"),
        ):
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            # shutdown() should have been called, which calls sys.exit(0)
            assert tui.is_running is False
            mock_exit.assert_called_once_with(0)

    def test_run_uses_signal_pause_on_unix(self) -> None:
        """run() uses signal.pause() on Unix systems."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        # Mock signal to have pause method
        mock_signal = MagicMock()
        mock_signal.pause = MagicMock(side_effect=KeyboardInterrupt)
        mock_signal.SIGINT = signal.SIGINT
        mock_signal.SIGTERM = signal.SIGTERM
        mock_signal.signal = signal.signal

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", mock_signal),
            patch.object(tui, "shutdown"),
        ):
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            # signal.pause() should have been called
            mock_signal.pause.assert_called_once()

    def test_run_uses_time_sleep_on_windows(self) -> None:
        """run() uses time.sleep() loop when signal.pause() not available."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        # Mock signal to not have pause method (like Windows)
        mock_signal = MagicMock(spec=[])  # Empty spec = no attributes
        mock_signal.SIGINT = signal.SIGINT
        mock_signal.SIGTERM = signal.SIGTERM
        mock_signal.signal = signal.signal

        sleep_count = 0

        def fake_sleep(_duration: float) -> None:
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 3:  # Run a few iterations then stop
                tui.is_running = False  # Exit cleanly

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", mock_signal),
            patch.object(app_module, "time", MagicMock(sleep=MagicMock(side_effect=fake_sleep))),
            patch.object(tui, "shutdown") as mock_shutdown,
        ):
            tui.run()
            # time.sleep() should have been called multiple times
            assert sleep_count >= 3
            # shutdown() should be called when loop exits
            mock_shutdown.assert_called_once()


class TestMain:
    """Tests for main() entry point."""

    def test_main_creates_tui_and_runs(self) -> None:
        """main() creates SmartNestTUI instance and calls run()."""
        from backend.tui.app import main  # noqa: PLC0415

        with (
            patch("backend.tui.app.SmartNestTUI") as mock_tui_class,
        ):
            mock_tui_instance = MagicMock()
            mock_tui_class.return_value = mock_tui_instance

            main()

            # Should create TUI instance
            mock_tui_class.assert_called_once()
            # Should call run() on instance
            mock_tui_instance.run.assert_called_once()

    @patch("sys.platform", "linux")
    def test_init_on_non_windows_platform(self) -> None:
        """TUI initializes correctly on non-Windows platforms."""
        # This test ensures the else branch (msvcrt = None) is covered
        # by forcing a module reload with patched sys.platform
        import backend.tui.app as app_module  # noqa: PLC0415, I001
        import importlib  # noqa: PLC0415

        # Reload module to trigger platform checks with patched sys.platform
        importlib.reload(app_module)

        # Verify it still initializes (msvcrt should be None on non-Windows)
        tui = app_module.SmartNestTUI()
        assert isinstance(tui, app_module.SmartNestTUI)
