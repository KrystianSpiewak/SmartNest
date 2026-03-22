"""Unit tests for SmartNest TUI application."""

from __future__ import annotations

import inspect
import os
import signal
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest
from rich.console import Console

from backend.logging.catalog import MessageCode
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig
from backend.tui.app import ReauthHttpClient, SmartNestTUI
from backend.tui.screens.dashboard import DashboardScreen
from backend.tui.screens.device_detail import DeviceDetailScreen
from backend.tui.screens.device_list import DeviceListScreen
from backend.tui.screens.reports import ReportsScreen
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

    def test_creates_reports_screen(self) -> None:
        """TUI creates a ReportsScreen instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.reports, ReportsScreen)
        assert tui.reports.console is tui.console
        assert tui.reports.http_client is tui.http_client

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

    def test_api_base_url_default_signature(self) -> None:
        """api_base_url default must be exactly 'http://localhost:8000'."""
        sig = inspect.signature(SmartNestTUI.__init__)
        assert sig.parameters["api_base_url"].default == "http://localhost:8000"

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

    def test_initializes_pending_action_none(self) -> None:
        """TUI initializes _pending_action to None."""
        tui = SmartNestTUI()
        assert tui._pending_action is None


class TestSmartNestTUIStartup:
    """Tests for TUI startup."""

    def test_startup_sets_running_flag(self) -> None:
        """startup() sets is_running to True."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
        ):
            tui.startup()
        assert tui.is_running is True

    def test_startup_logs_with_code(self) -> None:
        """startup() logs TUI_STARTED and TUI_MQTT_CONNECTED message codes."""
        tui = SmartNestTUI()
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
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
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
        ):
            tui.startup()
            # Should clear console once
            mock_clear.assert_called_once()

    def test_startup_connects_mqtt_client(self) -> None:
        """startup() connects to MQTT broker."""
        tui = SmartNestTUI()
        with patch.object(tui.mqtt_client, "connect") as mock_connect:
            with patch.object(tui, "_fetch_dashboard_summary", return_value=None):
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
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
        ):
            tui.startup()
            # Should subscribe to system status topic
            mock_subscribe.assert_called_once_with("smartnest/system/status")

    def test_startup_adds_topic_handler_with_exact_args(self) -> None:
        """startup() must call add_topic_handler with exact topic and callback."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui.mqtt_client, "subscribe"),
            patch.object(tui.mqtt_client, "add_topic_handler") as mock_add_handler,
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
        ):
            tui.startup()
            # Verify exact topic string and callback method
            mock_add_handler.assert_called_once_with(
                "smartnest/system/status", tui._on_system_status
            )

    def test_startup_renders_dashboard(self) -> None:
        """startup() renders the dashboard screen."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.mqtt_client, "connect"),
            patch.object(tui.dashboard, "render") as mock_render,
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
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
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
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
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
            patch.object(tui.dashboard, "render") as mock_render,
        ):
            tui.startup()
            # Should pass device_count=7 to render()
            mock_render.assert_called_once_with(
                device_count=7,
                system_status=tui.system_status,
                summary=None,
            )

    def test_startup_stops_when_authentication_fails(self) -> None:
        """startup() aborts before MQTT connect when authentication fails."""
        tui = SmartNestTUI()
        with (
            patch.object(tui, "_authenticate_startup", return_value=False),
            patch.object(tui.mqtt_client, "connect") as mock_connect,
        ):
            tui.startup()
        assert tui.is_running is False
        mock_connect.assert_not_called()


class TestSmartNestTUIAuthentication:
    """Tests for startup authentication workflow."""

    def test_authenticate_startup_skips_under_pytest(self) -> None:
        """_authenticate_startup() returns True in pytest environment."""
        tui = SmartNestTUI()
        with patch.dict("os.environ", {"PYTEST_CURRENT_TEST": "tests::fake"}):
            assert tui._authenticate_startup() is True

    def test_authenticate_startup_success_sets_bearer_header(self) -> None:
        """_authenticate_startup() stores JWT token in Authorization header."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test-token"}

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(tui.console, "input", return_value="notarealadmin"),
            patch("backend.tui.app.getpass.getpass", return_value="notarealpassword123"),
            patch.object(tui.http_client, "post", return_value=mock_response),
            patch.object(tui.console, "print"),
        ):
            assert tui._authenticate_startup() is True

        assert tui.http_client.headers.get("Authorization") == "Bearer test-token"

    def test_authenticate_startup_uses_default_username_when_blank(self) -> None:
        """_authenticate_startup() falls back to env/default username on blank input."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test-token"}

        with (
            patch.dict("os.environ", {"SMARTNEST_ADMIN_USERNAME": "notarealadmin"}, clear=True),
            patch.object(tui.console, "input", return_value=""),
            patch("backend.tui.app.getpass.getpass", return_value="notarealpassword123"),
            patch.object(tui.http_client, "post", return_value=mock_response) as mock_post,
            patch.object(tui.console, "print"),
        ):
            assert tui._authenticate_startup() is True

        assert mock_post.call_args.kwargs["json"]["username"] == "notarealadmin"

    def test_authenticate_startup_fails_on_empty_password(self) -> None:
        """_authenticate_startup() rejects empty password without API call."""
        tui = SmartNestTUI()
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(tui.console, "input", return_value="notarealadmin"),
            patch("backend.tui.app.getpass.getpass", return_value=""),
            patch.object(tui.http_client, "post") as mock_post,
            patch.object(tui.console, "print"),
        ):
            assert tui._authenticate_startup() is False
        mock_post.assert_not_called()

    def test_authenticate_startup_fails_on_http_error(self) -> None:
        """_authenticate_startup() returns False when login endpoint rejects credentials."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(tui.console, "input", return_value="notarealadmin"),
            patch("backend.tui.app.getpass.getpass", return_value="wrong"),
            patch.object(tui.http_client, "post", return_value=mock_response),
            patch.object(tui.console, "print"),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            assert tui._authenticate_startup() is False

        assert any(call.args[2] == MessageCode.TUI_API_ERROR for call in mock_log.call_args_list)

    def test_authenticate_startup_fails_when_token_missing(self) -> None:
        """_authenticate_startup() returns False when access token is missing."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {}

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(tui.console, "input", return_value="notarealadmin"),
            patch("backend.tui.app.getpass.getpass", return_value="notarealpassword123"),
            patch.object(tui.http_client, "post", return_value=mock_response),
            patch.object(tui.console, "print"),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            assert tui._authenticate_startup() is False

        assert any(call.args[2] == MessageCode.TUI_API_ERROR for call in mock_log.call_args_list)

    def test_refresh_auth_token_success(self) -> None:
        """_refresh_auth_token() re-authenticates and updates Authorization header."""
        tui = SmartNestTUI()
        tui._auth_username = "notarealadmin"
        tui._auth_password = "notarealpassword123"

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new-token"}
        mock_response.raise_for_status.return_value = None

        with patch.object(tui.http_client, "post", return_value=mock_response):
            assert tui._refresh_auth_token() is True

        assert tui.http_client.headers.get("Authorization") == "Bearer new-token"

    def test_refresh_auth_token_fails_without_cached_credentials(self) -> None:
        """_refresh_auth_token() returns False when no cached credentials are available."""
        tui = SmartNestTUI()
        tui._auth_username = None
        tui._auth_password = None

        with patch.object(tui.http_client, "post") as mock_post:
            assert tui._refresh_auth_token() is False
            mock_post.assert_not_called()

    def test_refresh_auth_token_fails_on_http_error(self) -> None:
        """_refresh_auth_token() returns False when login retry fails."""
        tui = SmartNestTUI()
        tui._auth_username = "notarealadmin"
        tui._auth_password = "notarealpassword123"

        with patch.object(tui.http_client, "post", side_effect=httpx.HTTPError("401")):
            assert tui._refresh_auth_token() is False

    def test_refresh_auth_token_fails_when_access_token_missing(self) -> None:
        """_refresh_auth_token() returns False when response has no access_token."""
        tui = SmartNestTUI()
        tui._auth_username = "notarealadmin"
        tui._auth_password = "notarealpassword123"

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}

        with patch.object(tui.http_client, "post", return_value=mock_response):
            assert tui._refresh_auth_token() is False


class TestReauthHttpClient:
    """Tests for HTTP auto-reauth retry behavior."""

    def test_request_retries_once_after_successful_reauth(self) -> None:
        """request() retries the original request once when reauth callback succeeds."""
        client = ReauthHttpClient(base_url="http://localhost:8000", reauth_callback=lambda: True)

        first_response = MagicMock(spec=httpx.Response)
        first_response.status_code = 401
        second_response = MagicMock(spec=httpx.Response)
        second_response.status_code = 200

        with patch.object(httpx.Client, "request", side_effect=[first_response, second_response]):
            response = client.request("GET", "/api/devices")

        assert response.status_code == 200

    def test_request_returns_immediately_when_not_unauthorized(self) -> None:
        """request() returns immediately when first response is not 401."""
        callback = MagicMock(return_value=True)
        client = ReauthHttpClient(base_url="http://localhost:8000", reauth_callback=callback)

        response_200 = MagicMock(spec=httpx.Response)
        response_200.status_code = 200

        with patch.object(httpx.Client, "request", return_value=response_200) as mock_request:
            response = client.request("GET", "/api/devices")

        assert response.status_code == 200
        callback.assert_not_called()
        mock_request.assert_called_once()

    def test_request_does_not_retry_auth_login_endpoint(self) -> None:
        """request() does not recurse when 401 comes from login endpoint."""
        callback = MagicMock(return_value=True)
        client = ReauthHttpClient(base_url="http://localhost:8000", reauth_callback=callback)

        response_401 = MagicMock(spec=httpx.Response)
        response_401.status_code = 401

        with patch.object(httpx.Client, "request", return_value=response_401) as mock_request:
            response = client.request("POST", "/api/auth/login")

        assert response.status_code == 401
        callback.assert_not_called()
        mock_request.assert_called_once()

    def test_request_does_not_retry_while_refresh_in_progress(self) -> None:
        """request() returns 401 response if refresh is already in progress."""
        callback = MagicMock(return_value=True)
        client = ReauthHttpClient(base_url="http://localhost:8000", reauth_callback=callback)
        client._refresh_in_progress = True

        response_401 = MagicMock(spec=httpx.Response)
        response_401.status_code = 401

        with patch.object(httpx.Client, "request", return_value=response_401) as mock_request:
            response = client.request("GET", "/api/devices")

        assert response.status_code == 401
        callback.assert_not_called()
        mock_request.assert_called_once()

    def test_request_does_not_retry_when_callback_missing(self) -> None:
        """request() returns 401 response when no reauth callback is configured."""
        client = ReauthHttpClient(base_url="http://localhost:8000", reauth_callback=None)

        response_401 = MagicMock(spec=httpx.Response)
        response_401.status_code = 401

        with patch.object(httpx.Client, "request", return_value=response_401) as mock_request:
            response = client.request("GET", "/api/devices")

        assert response.status_code == 401
        mock_request.assert_called_once()

    def test_request_returns_401_when_reauth_callback_fails(self) -> None:
        """request() returns original 401 response when callback reports reauth failure."""
        callback = MagicMock(return_value=False)
        client = ReauthHttpClient(base_url="http://localhost:8000", reauth_callback=callback)

        response_401 = MagicMock(spec=httpx.Response)
        response_401.status_code = 401

        with patch.object(httpx.Client, "request", return_value=response_401) as mock_request:
            response = client.request("GET", "/api/devices")

        assert response.status_code == 401
        callback.assert_called_once()
        mock_request.assert_called_once()


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
        # Should log error with proper error string
        error_calls = [c for c in mock_log.call_args_list if c.args[2] == MessageCode.TUI_API_ERROR]
        assert len(error_calls) == 1
        call = error_calls[0]
        assert "error" in call.kwargs
        assert call.kwargs["error"] is not None
        assert isinstance(call.kwargs["error"], str)
        assert call.kwargs["error"] != "None"  # kills error=str(None)

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
        # Should log error with proper error string
        error_calls = [c for c in mock_log.call_args_list if c.args[2] == MessageCode.TUI_API_ERROR]
        assert len(error_calls) == 1
        call = error_calls[0]
        assert "error" in call.kwargs
        assert call.kwargs["error"] is not None
        assert isinstance(call.kwargs["error"], str)
        assert call.kwargs["error"] != "None"  # kills error=str(None)
        assert "Connection refused" in call.kwargs["error"]

    def test_fetch_device_count_timeout(self) -> None:
        """_fetch_device_count() returns None on timeout."""
        tui = SmartNestTUI()

        with (
            patch.object(tui.http_client, "get", side_effect=httpx.TimeoutException("Timeout")),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            count = tui._fetch_device_count()

        assert count is None
        # Should log error with proper error string
        error_calls = [c for c in mock_log.call_args_list if c.args[2] == MessageCode.TUI_API_ERROR]
        assert len(error_calls) == 1
        call = error_calls[0]
        assert "error" in call.kwargs
        assert call.kwargs["error"] is not None
        assert isinstance(call.kwargs["error"], str)
        assert call.kwargs["error"] != "None"  # kills error=str(None)
        tui = SmartNestTUI()
        tui.is_running = True
        with patch("sys.exit"):
            tui.shutdown()
            # Second call should be no-op
            tui.shutdown()
        assert tui.is_running is False


class TestSmartNestTUIFetchDashboardSummary:
    """Tests for _fetch_dashboard_summary() method."""

    def test_fetch_dashboard_summary_success(self) -> None:
        """Summary endpoint result is returned and cached on success."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {"online_devices": 2, "offline_devices": 1}

        with patch.object(tui.http_client, "get", return_value=mock_response) as mock_get:
            result = tui._fetch_dashboard_summary(force=True)

        assert result == {"online_devices": 2, "offline_devices": 1}
        assert tui._dashboard_summary_cache == result
        mock_get.assert_called_once_with("/api/reports/dashboard-summary")

    def test_fetch_dashboard_summary_uses_cache_within_ttl(self) -> None:
        """Cached summary is used when inside TTL and force=False."""
        tui = SmartNestTUI()
        tui._dashboard_summary_cache = {"online_devices": 3}
        tui._dashboard_summary_last_fetch = 10.0
        tui._dashboard_summary_ttl_seconds = 2.0

        with (
            patch("backend.tui.app.time.monotonic", return_value=11.0),
            patch.object(tui.http_client, "get") as mock_get,
        ):
            result = tui._fetch_dashboard_summary(force=False)

        assert result == {"online_devices": 3}
        mock_get.assert_not_called()

    def test_fetch_dashboard_summary_returns_cached_on_api_error(self) -> None:
        """On API failure, method returns cached summary and logs warning."""
        tui = SmartNestTUI()
        tui._dashboard_summary_cache = {"online_devices": 1}

        with (
            patch.object(tui.http_client, "get", side_effect=httpx.ConnectError("refused")),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            result = tui._fetch_dashboard_summary(force=True)

        assert result == {"online_devices": 1}
        assert any(call.args[2] == MessageCode.TUI_API_ERROR for call in mock_log.call_args_list)

    def test_fetch_dashboard_summary_handles_non_dict_payload(self) -> None:
        """Non-dict JSON payload returns current cache safely."""
        tui = SmartNestTUI()
        tui._dashboard_summary_cache = {"online_devices": 7}
        mock_response = MagicMock()
        mock_response.json.return_value = ["invalid"]

        with patch.object(tui.http_client, "get", return_value=mock_response):
            result = tui._fetch_dashboard_summary(force=True)

        assert result == {"online_devices": 7}

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
            # Verify exact message — kills "XX...XX" string mutations
            shutdown_prints = [
                call for call in mock_print.call_args_list if "Shutting down" in str(call.args[0])
            ]
            assert len(shutdown_prints) == 1
            assert shutdown_prints[0].args[0] == (
                "\n[bold yellow]Shutting down SmartNest TUI...[/bold yellow]"
            )


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

    def test_on_system_status_success_log_has_exact_kwargs(self) -> None:
        """_on_system_status() success log must include exact logger, level, topic, payload."""
        tui = SmartNestTUI()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b'{"status": "online"}'

        with patch("backend.tui.app.log_with_code") as mock_log:
            tui._on_system_status(mock_client, None, mock_message)

            received_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.TUI_MQTT_MESSAGE_RECEIVED
            ]
            assert len(received_calls) == 1
            call = received_calls[0]
            # Verify logger is not None - kills logger=None mutation
            assert call.args[0] is not None
            # Verify exact log level - kills "XXdebugXX" mutation
            assert call.args[1] == "debug"
            # Verify topic kwarg - kills topic=None and removal mutations
            assert "topic" in call.kwargs
            assert call.kwargs["topic"] == "smartnest/system/status"
            assert call.kwargs["topic"] is not None
            # Verify payload kwarg - kills payload=None and removal mutations
            assert "payload" in call.kwargs
            assert call.kwargs["payload"] == {"status": "online"}
            assert call.kwargs["payload"] is not None

    def test_on_system_status_error_log_has_exact_kwargs(self) -> None:
        """_on_system_status() error log must include exact logger, level, error, topic."""
        tui = SmartNestTUI()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.topic = "smartnest/system/status"
        mock_message.payload = b"not valid json"

        with patch("backend.tui.app.log_with_code") as mock_log:
            tui._on_system_status(mock_client, None, mock_message)

            error_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.TUI_MQTT_MESSAGE_PARSE_ERROR
            ]
            assert len(error_calls) == 1
            call = error_calls[0]
            # Verify logger is not None - kills logger=None mutation
            assert call.args[0] is not None
            # Verify exact log level - kills "XXwarningXX" mutation
            assert call.args[1] == "warning"
            # Verify error kwarg - kills error=None, error=str(None), removal
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None
            assert isinstance(call.kwargs["error"], str)
            assert len(call.kwargs["error"]) > 0
            assert call.kwargs["error"] != "None"  # kills error=str(None) mutation
            # Verify topic kwarg - kills topic=None and removal mutations
            assert "topic" in call.kwargs
            assert call.kwargs["topic"] == "smartnest/system/status"
            assert call.kwargs["topic"] is not None

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
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()
        with (
            patch.object(tui, "startup") as mock_startup,
            patch.object(app_module, "signal", MagicMock(spec=[])),  # No pause attr → Windows path
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch("backend.tui.app.Live"),
            patch("time.sleep", side_effect=KeyboardInterrupt),  # Exit loop immediately
            patch.object(tui, "shutdown"),
        ):
            tui.is_running = True  # Simulate startup setting this
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            mock_startup.assert_called_once()

    def test_run_returns_immediately_when_startup_not_running(self) -> None:
        """run() exits early when startup fails authentication and leaves app stopped."""
        tui = SmartNestTUI()

        with (
            patch.object(tui, "startup", return_value=None),
            patch.object(tui, "_start_input_reader") as mock_start_reader,
            patch.object(tui, "_fetch_device_count") as mock_fetch,
            patch.object(tui, "shutdown") as mock_shutdown,
            patch.object(tui.console, "clear"),
        ):
            tui.run()

        mock_start_reader.assert_not_called()
        mock_fetch.assert_not_called()
        mock_shutdown.assert_called_once()

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
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", MagicMock(spec=[])),  # No pause attr → Windows path
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch("backend.tui.app.Live"),
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

    def test_run_uses_polling_loop_on_all_platforms(self) -> None:
        """run() uses a uniform polling loop on all platforms; signal.pause() never called."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        # Mock signal WITH a pause attribute to verify it is never called
        mock_signal = MagicMock()
        mock_signal.SIGINT = signal.SIGINT
        mock_signal.SIGTERM = signal.SIGTERM
        mock_signal.signal = signal.signal

        sleep_count = 0

        def fake_sleep(_duration: float) -> None:
            nonlocal sleep_count
            sleep_count += 1
            tui.is_running = False  # exit after first sleep

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", mock_signal),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch("backend.tui.app.Live"),
            patch.object(
                app_module,
                "time",
                MagicMock(sleep=MagicMock(side_effect=fake_sleep)),
            ),
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear"),
        ):
            tui.run()
        # signal.pause() must NOT be called — uniform polling loop used on all platforms
        mock_signal.pause.assert_not_called()
        # time.sleep must be called (polling loop is active)
        assert sleep_count >= 1

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
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch("backend.tui.app.Live"),
            patch.object(app_module, "time", MagicMock(sleep=MagicMock(side_effect=fake_sleep))),
            patch.object(tui, "shutdown") as mock_shutdown,
        ):
            tui.run()
            # time.sleep() should have been called multiple times
            assert sleep_count >= 3
            # shutdown() should be called when loop exits
            mock_shutdown.assert_called_once()

    def test_poll_input_key_reads_from_queue(self) -> None:
        """_poll_input_key() returns queued character when msvcrt has no key."""
        tui = SmartNestTUI()
        tui._input_queue.put("2")
        assert tui._poll_input_key() == "2"

    def test_poll_input_key_ignores_newline(self) -> None:
        """_poll_input_key() ignores CR/LF characters from stdin queue."""
        tui = SmartNestTUI()
        tui._input_queue.put("\n")
        assert tui._poll_input_key() is None

    def test_start_input_reader_skips_under_pytest(self) -> None:
        """_start_input_reader() does not spawn thread in pytest environment."""
        tui = SmartNestTUI()
        with (
            patch.dict("os.environ", {"PYTEST_CURRENT_TEST": "tests::fake"}),
            patch.object(sys.stdin, "isatty", return_value=True),
        ):
            tui._start_input_reader()
        assert tui._input_thread_started is False

    def test_start_input_reader_returns_when_already_started(self) -> None:
        """_start_input_reader() is a no-op when thread already started."""
        tui = SmartNestTUI()
        tui._input_thread_started = True
        with patch.object(sys.stdin, "isatty", return_value=True):
            tui._start_input_reader()
        assert tui._input_thread_started is True

    def test_start_input_reader_starts_background_thread(self) -> None:
        """_start_input_reader() starts daemon thread when tty and not in pytest."""
        tui = SmartNestTUI()
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(sys.stdin, "isatty", return_value=True),
            patch("backend.tui.app.threading.Thread") as mock_thread,
        ):
            tui._start_input_reader()

        assert tui._input_thread_started is True
        mock_thread.assert_called_once_with(target=tui._stdin_reader_loop, daemon=True)
        mock_thread.return_value.start.assert_called_once_with()

    def test_stop_input_reader_closes_prompt_toolkit_input(self) -> None:
        """_stop_input_reader() stops reader and closes prompt_toolkit input handle."""
        tui = SmartNestTUI()
        mock_pt_input = MagicMock()
        tui._pt_input = mock_pt_input
        tui._input_thread_started = True

        tui._stop_input_reader()

        mock_pt_input.close.assert_called_once_with()
        assert tui._pt_input is None
        assert tui._input_thread_started is False

    def test_stop_input_reader_without_prompt_toolkit_handle(self) -> None:
        """_stop_input_reader() is safe when no prompt_toolkit input exists."""
        tui = SmartNestTUI()
        tui._pt_input = None
        tui._input_thread_started = True

        tui._stop_input_reader()

        assert tui._pt_input is None
        assert tui._input_thread_started is False

    def test_stdin_reader_loop_enqueues_char_and_exits_on_eof(self) -> None:
        """_stdin_reader_loop() enqueues chars and stops when stdin returns EOF."""
        tui = SmartNestTUI()
        with patch.object(sys.stdin, "read", side_effect=["x", ""]):
            tui._stdin_reader_loop()
        assert tui._input_queue.get_nowait() == "x"

    def test_stdin_reader_loop_exits_immediately_when_stop_is_set(self) -> None:
        """_stdin_reader_loop() exits without reading stdin if stop event is pre-set."""
        tui = SmartNestTUI()
        tui._input_stop.set()
        with patch.object(sys.stdin, "read") as mock_read:
            tui._stdin_reader_loop()
        mock_read.assert_not_called()

    def test_stdin_reader_loop_reads_prompt_toolkit_keys(self) -> None:
        """_stdin_reader_loop() enqueues single-char prompt_toolkit key data."""
        tui = SmartNestTUI()
        mock_pt_input = MagicMock()
        tui._pt_input = mock_pt_input

        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = None
        mock_ctx.__exit__.return_value = False
        mock_pt_input.raw_mode.return_value = mock_ctx

        key_single = MagicMock()
        key_single.data = "x"
        key_multi = MagicMock()
        key_multi.data = "\x1bOP"

        def fake_read_keys() -> list[MagicMock]:
            tui._input_stop.set()
            return [key_single, key_multi]

        mock_pt_input.read_keys.side_effect = fake_read_keys

        tui._stdin_reader_loop()

        assert tui._input_queue.get_nowait() == "x"
        assert tui._input_queue.empty()

    def test_stdin_reader_loop_handles_prompt_toolkit_eof(self) -> None:
        """_stdin_reader_loop() exits gracefully when prompt_toolkit raises EOFError."""
        tui = SmartNestTUI()
        mock_pt_input = MagicMock()
        tui._pt_input = mock_pt_input

        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = None
        mock_ctx.__exit__.return_value = False
        mock_pt_input.raw_mode.return_value = mock_ctx
        mock_pt_input.read_keys.side_effect = EOFError

        tui._stdin_reader_loop()

    def test_run_handles_key_from_queue_for_navigation(self) -> None:
        """run() processes queued key input and updates current_screen."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True
            tui._input_queue.put("2")

        def fake_sleep(_duration: float) -> None:
            tui.is_running = False

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(tui, "_start_input_reader"),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch("backend.tui.app.Live"),
            patch.object(app_module, "time", MagicMock(sleep=MagicMock(side_effect=fake_sleep))),
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear"),
        ):
            tui.run()

        assert tui.current_screen == "devices"

    def test_handle_key_ctrl_c_stops_running(self) -> None:
        """_handle_key() treats Ctrl+C byte as a quit signal in raw mode."""
        tui = SmartNestTUI()
        tui.is_running = True

        tui._handle_key("\x03")

        assert tui.is_running is False

    def test_run_closes_prompt_toolkit_input_on_exit(self) -> None:
        """run() closes prompt_toolkit input handle in finally block."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()
        mock_pt_input = MagicMock()
        tui._pt_input = mock_pt_input

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(tui, "_start_input_reader"),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch("backend.tui.app.Live"),
            patch("time.sleep", side_effect=KeyboardInterrupt),
            patch.object(
                app_module, "time", MagicMock(sleep=MagicMock(side_effect=KeyboardInterrupt))
            ),
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear"),
        ):
            tui.run()

        mock_pt_input.close.assert_called_once_with()

    def test_run_modal_action_stops_and_restarts_input_reader(self) -> None:
        """run() pauses key reader during modal actions and restarts it afterward."""
        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True
            tui._pending_action = "add_user"

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch.object(
                tui,
                "_execute_modal_action",
                side_effect=lambda _: setattr(tui, "is_running", False),
            ),
            patch.object(tui, "_start_input_reader") as mock_start,
            patch.object(tui, "_stop_input_reader") as mock_stop,
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear"),
        ):
            tui.run()

        assert mock_start.call_count == 1
        assert mock_stop.call_count >= 2


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


# ---------------------------------------------------------------------------
# Targeted mutation-killing tests for __init__, run(), shutdown(), _fetch
# ---------------------------------------------------------------------------


class TestSmartNestTUIInitConsole:
    """Tests for Console creation and SMARTNEST_TUI_FORCE_TERMINAL env var.

    Kills __init__ mutants:
      - force_terminal = None  (mutation 3)
      - os.getenv default "1" → None or mangled  (mutations 5-10, 12)
      - != "0" → == "0"  (mutation 11)
      - env var name mangled  (mutations 8, 9)
    """

    def test_force_terminal_false_when_env_not_set(self) -> None:
        """Console uses default mode when SMARTNEST_TUI_FORCE_TERMINAL is absent."""
        env_without_var = {
            k: v for k, v in os.environ.items() if k != "SMARTNEST_TUI_FORCE_TERMINAL"
        }
        with (
            patch.dict("os.environ", env_without_var, clear=True),
            patch("backend.tui.app.Console") as mock_console,
        ):
            SmartNestTUI()
        mock_console.assert_called_once_with()

    def test_force_terminal_false_when_env_is_zero(self) -> None:
        """Console created without forcing when SMARTNEST_TUI_FORCE_TERMINAL=0."""
        with (
            patch.dict("os.environ", {"SMARTNEST_TUI_FORCE_TERMINAL": "0"}),
            patch("backend.tui.app.Console") as mock_console,
        ):
            SmartNestTUI()
        mock_console.assert_called_once_with()  # No force_terminal=True

    def test_force_terminal_true_when_env_is_one(self) -> None:
        """Console forced when SMARTNEST_TUI_FORCE_TERMINAL=1."""
        with (
            patch.dict("os.environ", {"SMARTNEST_TUI_FORCE_TERMINAL": "1"}),
            patch("backend.tui.app.Console") as mock_console,
        ):
            SmartNestTUI()
        mock_console.assert_called_once_with(force_terminal=True, force_interactive=True)

    def test_force_terminal_false_for_non_one_value(self) -> None:
        """Console stays default for non-'1' env var value (e.g. 'yes')."""
        with (
            patch.dict("os.environ", {"SMARTNEST_TUI_FORCE_TERMINAL": "yes"}),
            patch("backend.tui.app.Console") as mock_console,
        ):
            SmartNestTUI()
        mock_console.assert_called_once_with()


class TestSmartNestTUIInitHttpClient:
    """Tests for HTTP client creation parameters.

    Kills __init__ mutants in the http_client construction block
    (timeout=5.0, base_url assignment).
    """

    def test_http_client_timeout_is_5_seconds(self) -> None:
        """ReauthHttpClient must be created with timeout=5.0."""
        with patch("backend.tui.app.ReauthHttpClient") as mock_client:
            SmartNestTUI()
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["timeout"] == 5.0

    def test_http_client_base_url_set_to_default(self) -> None:
        """ReauthHttpClient base_url defaults to 'http://localhost:8000'."""
        with patch("backend.tui.app.ReauthHttpClient") as mock_client:
            SmartNestTUI()
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["base_url"] == "http://localhost:8000"

    def test_http_client_base_url_reflects_custom_api_url(self) -> None:
        """ReauthHttpClient base_url matches the api_base_url argument."""
        custom_url = "http://api.example.com:9000"
        with patch("backend.tui.app.ReauthHttpClient") as mock_client:
            SmartNestTUI(api_base_url=custom_url)
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["base_url"] == custom_url


class TestSmartNestTUIInitMQTTClient:
    """Tests for SmartNestMQTTClient creation parameters.

    Kills __init__ mutants around enable_paho_logger and MQTTConfig defaults.
    """

    def test_mqtt_client_paho_logger_disabled(self) -> None:
        """SmartNestMQTTClient must be created with enable_paho_logger=False."""
        with patch("backend.tui.app.SmartNestMQTTClient") as mock_mqtt_class:
            SmartNestTUI()
        call_kwargs = mock_mqtt_class.call_args.kwargs
        assert call_kwargs.get("enable_paho_logger") is False

    def test_default_mqtt_config_uses_smartnest_tui_client_id(self) -> None:
        """Default MQTTConfig must use client_id='smartnest_tui' exactly."""
        # Create a real TUI so MQTTConfig is constructed normally — no mock
        # needed; just verify the resulting client_id.
        tui = SmartNestTUI()
        assert tui.mqtt_config.client_id == "smartnest_tui"


class TestSmartNestTUIRunLive:
    """Tests for run() Rich Live context manager arguments and loop behavior.

    Kills run() mutants 1-36 by verifying:
      - Live() constructor keyword args (screen=True, auto_refresh=False, console)
      - render_live() called with correct device_count and system_status
      - live.update() called with refresh=False
      - live.refresh() called each iteration
      - time.sleep(0.25) — exactly 0.25, not 0.5 or anything else
      - console.clear() called in the finally block
    """

    def _make_run_context(
        self,
        tui: SmartNestTUI,
        device_count: int | None = None,
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Set up and run() using the Windows time.sleep path.

        Returns (mock_live_class, mock_live_context, mock_time).
        All three retain call history after the with block exits.
        """
        import backend.tui.app as app_module  # noqa: PLC0415

        def fake_startup() -> None:
            tui.is_running = True

        mock_signal = MagicMock(spec=[])  # No .pause → AttributeError → Windows path
        mock_time = MagicMock()

        def exit_loop_after_one_sleep(_: float) -> None:
            tui.is_running = False

        mock_time.sleep = MagicMock(side_effect=exit_loop_after_one_sleep)

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", mock_signal),
            patch.object(tui, "_fetch_device_count", return_value=device_count),
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
            patch("backend.tui.app.Live") as mock_live_class,
            patch.object(app_module, "time", mock_time),
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear"),
        ):
            tui.run()

        return mock_live_class, mock_live_class.return_value.__enter__.return_value, mock_time

    def test_live_created_with_screen_true_by_default(self) -> None:
        """Live() must default to screen=True for full-screen TUI mode."""
        tui = SmartNestTUI()
        mock_live_class, _, _ = self._make_run_context(tui)
        assert mock_live_class.call_args.kwargs["screen"] is True

    def test_live_created_with_screen_false_when_env_disabled(self) -> None:
        """Live() disables alternate screen when SMARTNEST_TUI_ALT_SCREEN=0."""
        with patch.dict("os.environ", {"SMARTNEST_TUI_ALT_SCREEN": "0"}):
            tui = SmartNestTUI()
        mock_live_class, _, _ = self._make_run_context(tui)
        assert mock_live_class.call_args.kwargs["screen"] is False

    def test_live_created_with_auto_refresh_false(self) -> None:
        """Live() must use auto_refresh=False — app drives refresh manually."""
        tui = SmartNestTUI()
        mock_live_class, _, _ = self._make_run_context(tui)
        assert mock_live_class.call_args.kwargs["auto_refresh"] is False

    def test_live_created_with_tui_console(self) -> None:
        """Live() must receive the TUI's own console instance."""
        tui = SmartNestTUI()
        mock_live_class, _, _ = self._make_run_context(tui)
        assert mock_live_class.call_args.kwargs["console"] is tui.console

    def test_render_live_called_with_device_count(self) -> None:
        """render_live() receives the device_count returned by _fetch_device_count."""
        tui = SmartNestTUI()
        with patch.object(tui.dashboard, "render_live") as mock_render:
            self._make_run_context(tui, device_count=7)
        assert mock_render.call_count >= 1
        for call in mock_render.call_args_list:
            assert call.kwargs.get("device_count") == 7

    def test_render_live_called_with_system_status(self) -> None:
        """render_live() receives the current system_status dict."""
        tui = SmartNestTUI()
        tui.system_status = {"active": True}
        with patch.object(tui.dashboard, "render_live") as mock_render:
            self._make_run_context(tui)
        assert mock_render.call_count >= 1
        for call in mock_render.call_args_list:
            assert call.kwargs.get("system_status") == {"active": True}

    def test_live_update_called_with_refresh_false(self) -> None:
        """live.update() must pass refresh=False to suppress mid-frame flicker."""
        tui = SmartNestTUI()
        _, mock_live, _ = self._make_run_context(tui)
        mock_live.update.assert_called()
        for call in mock_live.update.call_args_list:
            assert call.kwargs.get("refresh") is False

    def test_live_refresh_called_each_iteration(self) -> None:
        """live.refresh() must be called to actually push the frame."""
        tui = SmartNestTUI()
        _, mock_live, _ = self._make_run_context(tui)
        mock_live.refresh.assert_called()

    def test_live_constructor_receives_render_live_result(self) -> None:
        """Live() must receive render_live() return value as first positional arg."""
        tui = SmartNestTUI()
        with patch.object(tui.dashboard, "render_live") as mock_render:
            mock_live_class, _, _ = self._make_run_context(tui)
        assert len(mock_live_class.call_args.args) >= 1
        assert mock_live_class.call_args.args[0] is mock_render.return_value

    def test_live_update_receives_render_live_result(self) -> None:
        """live.update() must receive render_live() return value as first positional arg."""
        tui = SmartNestTUI()
        with patch.object(tui.dashboard, "render_live") as mock_render:
            _, mock_live, _ = self._make_run_context(tui)
        mock_live.update.assert_called()
        for call in mock_live.update.call_args_list:
            assert len(call.args) >= 1
            assert call.args[0] is mock_render.return_value

    def test_render_live_called_for_both_init_and_update(self) -> None:
        """render_live() must be called for Live() init and each loop update (2 total)."""
        tui = SmartNestTUI()
        with patch.object(tui.dashboard, "render_live") as mock_render:
            self._make_run_context(tui)
        assert mock_render.call_count == 2

    def test_run_sleep_duration_is_exactly_250ms(self) -> None:
        """time.sleep() must be called with 0.25 seconds (4 FPS), not any other value."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        sleep_durations: list[float] = []

        def recording_sleep(duration: float) -> None:
            sleep_durations.append(duration)
            tui.is_running = False  # exit after first call

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", MagicMock(spec=[])),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
            patch("backend.tui.app.Live"),
            patch.object(
                app_module,
                "time",
                MagicMock(sleep=MagicMock(side_effect=recording_sleep)),
            ),
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear"),
        ):
            tui.run()

        assert sleep_durations == [0.25]

    def test_run_console_clear_called_in_finally(self) -> None:
        """console.clear() must be in the finally block so it always runs."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", MagicMock(spec=[])),
            patch.object(tui, "_fetch_device_count", return_value=None),
            patch.object(tui, "_fetch_dashboard_summary", return_value=None),
            patch("backend.tui.app.Live"),
            patch.object(
                app_module,
                "time",
                MagicMock(sleep=MagicMock(side_effect=lambda _: setattr(tui, "is_running", False))),
            ),
            patch.object(tui, "shutdown"),
            patch.object(tui.console, "clear") as mock_clear,
        ):
            tui.run()

        mock_clear.assert_called_once()


class TestSmartNestTUIShutdownDetails:
    """Precise shutdown() tests targeting exact argument values.

    Kills shutdown() mutants:
      - sys.exit(0) → sys.exit(1)  (mutation 19)
      - rc=0 → rc=1 in TUI_MQTT_DISCONNECTED log  (mutation 13)
    """

    def test_shutdown_sys_exit_code_is_zero(self) -> None:
        """shutdown() must call sys.exit(0), not sys.exit(1) or another value."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch("sys.exit") as mock_exit,
        ):
            tui.shutdown()
        mock_exit.assert_called_once_with(0)

    def test_shutdown_mqtt_disconnect_log_rc_is_zero(self) -> None:
        """TUI_MQTT_DISCONNECTED log must include rc=0, not 1 or None."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.mqtt_client, "disconnect"),
            patch("backend.tui.app.log_with_code") as mock_log,
            patch("sys.exit"),
        ):
            mock_log.reset_mock()
            tui.shutdown()
        disconnected_calls = [
            c
            for c in mock_log.call_args_list
            if len(c.args) >= 3 and c.args[2] == MessageCode.TUI_MQTT_DISCONNECTED
        ]
        assert len(disconnected_calls) == 1
        assert disconnected_calls[0].kwargs.get("rc") == 0


class TestSmartNestTUIFetchDeviceCountEdgeCases:
    """Edge case tests for _fetch_device_count().

    Kills _fetch_device_count() mutants:
      - count=0 should return 0, not None  (tests None-inversion mutation)
      - JSON null count should return None  (tests the else branch)
      - error log level must be 'warning'  (mutation 15/19 region)
      - error kwarg must be a non-empty string  (mutation 22 region)
    """

    def test_fetch_device_count_zero_returns_zero(self) -> None:
        """count=0 is a valid value and must not collapse to None."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {"count": 0}
        with patch.object(tui.http_client, "get", return_value=mock_response):
            result = tui._fetch_device_count()
        assert result == 0
        assert result is not None

    def test_fetch_device_count_null_count_returns_none(self) -> None:
        """JSON count=null must return None without raising."""
        tui = SmartNestTUI()
        mock_response = MagicMock()
        mock_response.json.return_value = {"count": None}
        with patch.object(tui.http_client, "get", return_value=mock_response):
            result = tui._fetch_device_count()
        assert result is None

    def test_fetch_device_count_error_logged_at_warning_level(self) -> None:
        """API error must be logged at 'warning' level, not 'error' or 'debug'."""
        tui = SmartNestTUI()
        with (
            patch.object(tui.http_client, "get", side_effect=httpx.ConnectError("refused")),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            tui._fetch_device_count()
        api_error_calls = [
            c
            for c in mock_log.call_args_list
            if len(c.args) >= 3 and c.args[2] == MessageCode.TUI_API_ERROR
        ]
        assert len(api_error_calls) == 1
        assert api_error_calls[0].args[1] == "warning"

    def test_fetch_device_count_error_kwarg_is_non_empty_string(self) -> None:
        """Error log must include a non-empty error= kwarg with the exception message."""
        tui = SmartNestTUI()
        with (
            patch.object(
                tui.http_client, "get", side_effect=httpx.ConnectError("Connection refused")
            ),
            patch("backend.tui.app.log_with_code") as mock_log,
        ):
            tui._fetch_device_count()
        api_error_calls = [
            c
            for c in mock_log.call_args_list
            if len(c.args) >= 3 and c.args[2] == MessageCode.TUI_API_ERROR
        ]
        assert len(api_error_calls) == 1
        error_kwarg = api_error_calls[0].kwargs.get("error")
        assert isinstance(error_kwarg, str)
        assert len(error_kwarg) > 0

    class TestSmartNestTUIRenderCurrentScreen:
        """Tests for _render_current_screen() routing method."""

        def test_renders_dashboard_when_current_screen_is_dashboard(self) -> None:
            """_render_current_screen() delegates to dashboard.render_live for dashboard screen."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            with patch.object(tui.dashboard, "render_live") as mock_render:
                result = tui._render_current_screen(device_count=5)
            mock_render.assert_called_once_with(
                device_count=5,
                system_status=tui.system_status,
                summary=tui._dashboard_summary_cache,
            )
            assert result is mock_render.return_value

        def test_renders_device_list_when_current_screen_is_devices(self) -> None:
            """_render_current_screen() delegates to device_list.render_live for devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "devices"
            with patch.object(tui.device_list, "render_live") as mock_render:
                result = tui._render_current_screen(device_count=3)
            mock_render.assert_called_once_with()
            assert result is mock_render.return_value

        def test_renders_device_detail_when_current_screen_is_device_detail(self) -> None:
            """_render_current_screen() delegates to device_detail.render_live."""
            tui = SmartNestTUI()
            tui.current_screen = "device_detail"
            with patch.object(tui.device_detail, "render_live") as mock_render:
                result = tui._render_current_screen()
            mock_render.assert_called_once_with()
            assert result is mock_render.return_value

        def test_renders_settings_when_current_screen_is_settings(self) -> None:
            """_render_current_screen() delegates to settings.render_live for settings screen."""
            tui = SmartNestTUI()
            tui.current_screen = "settings"
            with patch.object(tui.settings, "render_live") as mock_render:
                result = tui._render_current_screen()
            mock_render.assert_called_once_with()
            assert result is mock_render.return_value

        def test_renders_sensor_view_when_current_screen_is_sensors(self) -> None:
            """_render_current_screen() delegates to sensor_view.render_live."""
            tui = SmartNestTUI()
            tui.current_screen = "sensors"
            with patch.object(tui.sensor_view, "render_live") as mock_render:
                result = tui._render_current_screen()
            mock_render.assert_called_once_with()
            assert result is mock_render.return_value

        def test_renders_reports_when_current_screen_is_reports(self) -> None:
            """_render_current_screen() delegates to reports.render_live."""
            tui = SmartNestTUI()
            tui.current_screen = "reports"
            with patch.object(tui.reports, "render_live") as mock_render:
                result = tui._render_current_screen()
            mock_render.assert_called_once_with()
            assert result is mock_render.return_value

        def test_falls_back_to_dashboard_for_unknown_screen(self) -> None:
            """_render_current_screen() falls back to dashboard for unknown screen names."""
            tui = SmartNestTUI()
            tui.current_screen = "unknown_screen"
            with patch.object(tui.dashboard, "render_live") as mock_render:
                result = tui._render_current_screen(device_count=None)
            mock_render.assert_called_once_with(
                device_count=None,
                system_status=tui.system_status,
                summary=tui._dashboard_summary_cache,
            )
            assert result is mock_render.return_value

        def test_passes_system_status_to_dashboard(self) -> None:
            """_render_current_screen() passes current system_status dict to dashboard."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui.system_status = {"status": "online"}
            with patch.object(tui.dashboard, "render_live") as mock_render:
                tui._render_current_screen(device_count=2)
            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["system_status"] == {"status": "online"}
            assert "summary" in call_kwargs

        def test_formats_mqtt_uptime_in_seconds_when_under_one_minute(self) -> None:
            """_render_current_screen() formats uptime as seconds for sub-minute uptime."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui.system_status = {"connected": True, "status": "online"}
            tui._mqtt_connected_since = 100.0

            with (
                patch("backend.tui.app.time.monotonic", return_value=145.0),
                patch.object(tui.dashboard, "render_live") as mock_render,
            ):
                tui._render_current_screen(device_count=1)

            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["system_status"]["uptime"] == "45s"

        def test_formats_mqtt_uptime_in_minutes_when_over_one_minute(self) -> None:
            """_render_current_screen() formats uptime as Xm Ys for minute+ uptime."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui.system_status = {"connected": True, "status": "online"}
            tui._mqtt_connected_since = 100.0

            with (
                patch("backend.tui.app.time.monotonic", return_value=225.0),
                patch.object(tui.dashboard, "render_live") as mock_render,
            ):
                tui._render_current_screen(device_count=1)

            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["system_status"]["uptime"] == "2m 5s"

    class TestSmartNestTUIHandleKey:
        """Tests for _handle_key() navigation and action dispatch."""

        def test_q_sets_is_running_false(self) -> None:
            """'q' key sets is_running to False."""
            tui = SmartNestTUI()
            tui.is_running = True
            tui._handle_key("q")
            assert tui.is_running is False

        def test_q_uppercase_sets_is_running_false(self) -> None:
            """'Q' key (uppercase) also sets is_running to False."""
            tui = SmartNestTUI()
            tui.is_running = True
            tui._handle_key("Q")
            assert tui.is_running is False

        def test_key_1_navigates_to_dashboard(self) -> None:
            """'1' key sets current_screen to 'dashboard'."""
            tui = SmartNestTUI()
            tui.current_screen = "settings"
            tui._handle_key("1")
            assert tui.current_screen == "dashboard"

        def test_key_2_navigates_to_devices(self) -> None:
            """'2' key sets current_screen to 'devices'."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui._handle_key("2")
            assert tui.current_screen == "devices"

        def test_key_3_navigates_to_settings(self) -> None:
            """'3' key sets current_screen to 'settings'."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui._handle_key("3")
            assert tui.current_screen == "settings"

        def test_key_4_navigates_to_sensors(self) -> None:
            """'4' key sets current_screen to 'sensors'."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui._handle_key("4")
            assert tui.current_screen == "sensors"

        def test_key_5_navigates_to_reports(self) -> None:
            """'5' key sets current_screen to 'reports'."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui._handle_key("5")
            assert tui.current_screen == "reports"

        def test_l_key_sets_lights_filter_on_devices_screen(self) -> None:
            """'l' key filters device_list to 'lights' when on devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "devices"
            with patch.object(tui.device_list, "set_filter") as mock_filter:
                tui._handle_key("l")
            mock_filter.assert_called_once_with("lights")

        def test_s_key_sets_sensors_filter_on_devices_screen(self) -> None:
            """'s' key filters device_list to 'sensors' when on devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "devices"
            with patch.object(tui.device_list, "set_filter") as mock_filter:
                tui._handle_key("s")
            mock_filter.assert_called_once_with("sensors")

        def test_w_key_sets_switches_filter_on_devices_screen(self) -> None:
            """'w' key filters device_list to 'switches' when on devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "devices"
            with patch.object(tui.device_list, "set_filter") as mock_filter:
                tui._handle_key("w")
            mock_filter.assert_called_once_with("switches")

        def test_a_key_sets_all_filter_on_devices_screen(self) -> None:
            """'a' key filters device_list to 'all' when on devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "devices"
            with patch.object(tui.device_list, "set_filter") as mock_filter:
                tui._handle_key("a")
            mock_filter.assert_called_once_with("all")

        def test_slash_sets_pending_search_action_on_devices_screen(self) -> None:
            """'/' key queues search modal action when on devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "devices"

            tui._handle_key("/")

            assert tui._pending_action == "search_devices"

        def test_r_refreshes_sensor_screen(self) -> None:
            """'r' triggers sensor refresh on sensors screen."""
            tui = SmartNestTUI()
            tui.current_screen = "sensors"
            with patch.object(tui.sensor_view, "refresh_now") as mock_refresh:
                tui._handle_key("r")
            mock_refresh.assert_called_once_with()

        def test_e_exports_sensor_csv_on_sensors_screen(self) -> None:
            """'e' triggers sensor CSV export on sensors screen."""
            tui = SmartNestTUI()
            tui.current_screen = "sensors"
            with patch.object(tui.sensor_view, "export_csv") as mock_export:
                tui._handle_key("e")
            mock_export.assert_called_once_with()

        def test_r_refreshes_reports_screen(self) -> None:
            """'r' triggers report summary refresh on reports screen."""
            tui = SmartNestTUI()
            tui.current_screen = "reports"
            with patch.object(tui.reports, "refresh_now") as mock_refresh:
                tui._handle_key("r")
            mock_refresh.assert_called_once_with()

        def test_a_key_sets_pending_action_add_user_on_settings_screen(self) -> None:
            """'a' key sets _pending_action to 'add_user' when on settings screen."""
            tui = SmartNestTUI()
            tui.current_screen = "settings"
            tui._handle_key("a")
            assert tui._pending_action == "add_user"

        def test_d_key_sets_pending_action_delete_user_on_settings_screen(self) -> None:
            """'d' key sets _pending_action to 'delete_user' when on settings screen."""
            tui = SmartNestTUI()
            tui.current_screen = "settings"
            tui._handle_key("d")
            assert tui._pending_action == "delete_user"

        def test_l_key_ignored_on_dashboard_screen(self) -> None:
            """'l' key has no effect when not on devices screen."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            with patch.object(tui.device_list, "set_filter") as mock_filter:
                tui._handle_key("l")
            mock_filter.assert_not_called()

        def test_a_key_ignored_on_dashboard_screen(self) -> None:
            """'a' key has no effect when not on devices or settings screen."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            tui._handle_key("a")
            assert tui._pending_action is None

        def test_handle_navigation_key_unknown_returns_false(self) -> None:
            """Unknown navigation key returns False and leaves screen unchanged."""
            tui = SmartNestTUI()
            tui.current_screen = "dashboard"
            handled = tui._handle_navigation_key("x")
            assert handled is False
            assert tui.current_screen == "dashboard"

        def test_handle_devices_key_unknown_returns_false(self) -> None:
            """Unknown devices key returns False and does not call set_filter."""
            tui = SmartNestTUI()
            with patch.object(tui.device_list, "set_filter") as mock_filter:
                handled = tui._handle_devices_key("x")
            assert handled is False
            mock_filter.assert_not_called()

        def test_handle_settings_key_unknown_returns_false(self) -> None:
            """Unknown settings key returns False and does not set pending action."""
            tui = SmartNestTUI()
            handled = tui._handle_settings_key("x")
            assert handled is False
            assert tui._pending_action is None

        def test_handle_sensor_key_unknown_returns_false(self) -> None:
            """Unknown sensor key returns False and does not invoke sensor actions."""
            tui = SmartNestTUI()
            with (
                patch.object(tui.sensor_view, "refresh_now") as mock_refresh,
                patch.object(tui.sensor_view, "export_csv") as mock_export,
            ):
                handled = tui._handle_sensor_key("x")
            assert handled is False
            mock_refresh.assert_not_called()
            mock_export.assert_not_called()

        def test_handle_reports_key_unknown_returns_false(self) -> None:
            """Unknown reports key returns False and does not refresh reports."""
            tui = SmartNestTUI()
            with patch.object(tui.reports, "refresh_now") as mock_refresh:
                handled = tui._handle_reports_key("x")
            assert handled is False
            mock_refresh.assert_not_called()

    class TestSmartNestTUIExecuteModalAction:
        """Tests for _execute_modal_action() method."""

        def test_add_user_calls_settings_prompt_add_user(self) -> None:
            """'add_user' action calls settings.prompt_add_user()."""
            tui = SmartNestTUI()
            with patch.object(tui.settings, "prompt_add_user") as mock_prompt:
                tui._execute_modal_action("add_user")
            mock_prompt.assert_called_once_with()

        def test_delete_user_calls_settings_prompt_delete_user(self) -> None:
            """'delete_user' action calls settings.prompt_delete_user()."""
            tui = SmartNestTUI()
            with patch.object(tui.settings, "prompt_delete_user") as mock_prompt:
                tui._execute_modal_action("delete_user")
            mock_prompt.assert_called_once_with()

        def test_search_devices_calls_device_list_prompt_search(self) -> None:
            """'search_devices' action calls device_list.prompt_search()."""
            tui = SmartNestTUI()
            with patch.object(tui.device_list, "prompt_search") as mock_prompt:
                tui._execute_modal_action("search_devices")
            mock_prompt.assert_called_once_with()

        def test_unknown_action_is_a_noop(self) -> None:
            """Unknown action strings do not raise and do not call any method."""
            tui = SmartNestTUI()
            with (
                patch.object(tui.settings, "prompt_add_user") as mock_add,
                patch.object(tui.settings, "prompt_delete_user") as mock_del,
            ):
                tui._execute_modal_action("not_a_real_action")
            mock_add.assert_not_called()
            mock_del.assert_not_called()

    class TestSmartNestTUIRunPendingActionFlow:
        """Focused tests for run() outer-loop pending action behavior."""

        def test_run_breaks_after_pending_action_sets_not_running(self) -> None:
            """run() exits before entering Live when pending action causes shutdown."""
            tui = SmartNestTUI()
            tui._pending_action = "add_user"

            def fake_startup() -> None:
                tui.is_running = True

            def fake_execute(_action: str) -> None:
                tui.is_running = False

            with (
                patch.object(tui, "startup", side_effect=fake_startup),
                patch.object(tui, "_fetch_device_count", return_value=None),
                patch.object(tui, "_execute_modal_action", side_effect=fake_execute) as mock_exec,
                patch("backend.tui.app.Live") as mock_live,
                patch.object(tui, "shutdown"),
                patch.object(tui.console, "clear"),
            ):
                tui.run()

            mock_exec.assert_called_once_with("add_user")
            mock_live.assert_not_called()

        def test_run_enters_live_after_pending_action_when_still_running(self) -> None:
            """run() continues into Live when pending action completes without stopping app."""
            import backend.tui.app as app_module  # noqa: PLC0415

            tui = SmartNestTUI()
            tui._pending_action = "add_user"

            def fake_startup() -> None:
                tui.is_running = True

            sleep_calls = 0

            def fake_sleep(_duration: float) -> None:
                nonlocal sleep_calls
                sleep_calls += 1
                tui.is_running = False

            with (
                patch.object(tui, "startup", side_effect=fake_startup),
                patch.object(tui, "_fetch_device_count", return_value=None),
                patch.object(tui, "_execute_modal_action") as mock_exec,
                patch("backend.tui.app.Live") as mock_live,
                patch.object(
                    app_module, "time", MagicMock(sleep=MagicMock(side_effect=fake_sleep))
                ),
                patch.object(tui, "shutdown"),
                patch.object(tui.console, "clear"),
            ):
                tui.run()

            mock_exec.assert_called_once_with("add_user")
            assert sleep_calls >= 1
            mock_live.assert_called_once()
