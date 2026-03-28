"""SmartNest Terminal User Interface Application.

Main TUI application class with lifespan management and graceful shutdown.
"""

from __future__ import annotations

import getpass
import json
import os
import queue
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from prompt_toolkit.input import create_input
from rich.console import Console
from rich.live import Live

from backend.auth.client import login_and_get_access_token, set_bearer_token
from backend.logging.catalog import MessageCode
from backend.logging.utils import log_with_code
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig
from backend.tui.screens.dashboard import DashboardScreen
from backend.tui.screens.device_detail import DeviceDetailScreen
from backend.tui.screens.device_list import DeviceListScreen
from backend.tui.screens.reports import ReportsScreen
from backend.tui.screens.sensor_view import SensorViewScreen
from backend.tui.screens.settings import SettingsScreen

if sys.platform == "win32":  # pragma: no cover - imported only on Windows
    try:
        import msvcrt
    except ImportError:  # pragma: no cover - extremely unlikely on Windows
        msvcrt = None  # type: ignore[assignment]
else:
    msvcrt = None

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

    import paho.mqtt.client as mqtt
    from prompt_toolkit.input.base import Input

logger = structlog.get_logger(__name__)
_HTTP_STATUS_UNAUTHORIZED = 401
_SECONDS_PER_MINUTE = 60


class ReauthHttpClient(httpx.Client):
    """HTTP client that retries once after refreshing auth on 401."""

    def __init__(
        self,
        *args: Any,
        reauth_callback: Callable[[], bool] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._reauth_callback = reauth_callback
        self._refresh_in_progress = False

    def request(self, method: str, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        response = super().request(method, url, **kwargs)
        if response.status_code != _HTTP_STATUS_UNAUTHORIZED:
            return response

        # Skip refresh for auth endpoint itself and while already refreshing.
        target = str(url)
        if target.startswith("/api/auth/login") or target.endswith("/api/auth/login"):
            return response
        if self._refresh_in_progress:
            return response
        if self._reauth_callback is None:
            return response

        self._refresh_in_progress = True
        try:
            if not self._reauth_callback():
                return response
        finally:
            self._refresh_in_progress = False

        return super().request(method, url, **kwargs)


class SmartNestTUI:
    """SmartNest Terminal User Interface.

    Rich-based TUI for managing SmartNest home automation system.
    Provides dashboard, device management, and real-time monitoring.

    Attributes:
        console: Rich Console instance for rendering.
        is_running: Flag indicating if TUI is active.
        api_base_url: Base URL for backend API.
        http_client: HTTP client for API requests.
        mqtt_client: MQTT client for real-time device updates.
        mqtt_config: MQTT broker configuration.
        dashboard: Dashboard screen instance.
        device_list: Device list screen instance.
        device_detail: Device detail screen instance.
        sensor_view: Sensor view screen instance.
        settings: Settings screen instance.
        current_screen: Currently displayed screen name.
        system_status: Current system status from MQTT messages.
    """

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        mqtt_config: MQTTConfig | None = None,
    ) -> None:
        """Initialize SmartNest TUI.

        Creates Rich Console, sets up signal handlers, and initializes screens.

        Args:
            api_base_url: Base URL for backend API (default: http://localhost:8000)
            mqtt_config: MQTT configuration (default: localhost:1883)
        """
        # Use conservative terminal defaults for terminal capability forcing,
        # but keep alternate-screen mode enabled by default for a clean
        # full-screen TUI that doesn't append frames to terminal history.
        #
        # Optional overrides:
        # - SMARTNEST_TUI_FORCE_TERMINAL=1 to force Rich interactive terminal mode.
        # - SMARTNEST_TUI_ALT_SCREEN=0 to disable alternate-screen mode.
        force_terminal = os.getenv("SMARTNEST_TUI_FORCE_TERMINAL", "0") == "1"
        self.console = (
            Console(force_terminal=True, force_interactive=True) if force_terminal else Console()
        )
        self._live_alt_screen = os.getenv("SMARTNEST_TUI_ALT_SCREEN", "1") != "0"
        self.is_running = False
        self.api_base_url = api_base_url
        self._auth_username: str | None = None
        self._auth_password: str | None = None
        self.http_client = ReauthHttpClient(
            base_url=api_base_url,
            timeout=5.0,
            reauth_callback=self._refresh_auth_token,
        )

        # Initialize screens
        self.dashboard = DashboardScreen(self.console)
        self.device_list = DeviceListScreen(self.console, self.http_client)
        self.device_detail = DeviceDetailScreen(self.console, self.http_client)
        self.sensor_view = SensorViewScreen(self.console, self.http_client)
        self.reports = ReportsScreen(self.console, self.http_client)
        self.settings = SettingsScreen(self.console, self.http_client)

        # Current screen tracking
        self.current_screen = "dashboard"

        # MQTT client for real-time updates
        self.mqtt_config = mqtt_config or MQTTConfig(client_id="smartnest_tui")
        # Disable Paho internal debug logging for the TUI to avoid interleaving
        # with Rich Live rendering in terminals with imperfect ANSI support.
        self.mqtt_client = SmartNestMQTTClient(self.mqtt_config, enable_paho_logger=False)

        # System status state (updated via MQTT)
        self.system_status: dict[str, Any] = {}
        self._input_queue: queue.Queue[str] = queue.Queue()
        self._input_stop = threading.Event()
        self._input_thread_started = False
        self._pt_input: Input | None = None

        self._pending_action: str | None = None
        self._dashboard_summary_cache: dict[str, Any] | None = None
        self._dashboard_summary_last_fetch = 0.0
        self._dashboard_summary_ttl_seconds = 2.0
        self._mqtt_connected_since = 0.0

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

        log_with_code(logger, "debug", MessageCode.TUI_INITIALIZED)

    def _stdin_reader_loop(self) -> None:
        """Read stdin chars and enqueue for non-blocking key handling.

        This is used as a fallback for terminals where msvcrt key polling
        does not work reliably (e.g., Git Bash PTY on Windows).
        """
        if self._pt_input is None:
            # Safety fallback if prompt_toolkit input wasn't initialized.
            while not self._input_stop.is_set():
                char = sys.stdin.read(1)
                if not char:
                    return
                self._input_queue.put(char)
            return

        try:
            with self._pt_input.raw_mode():
                while not self._input_stop.is_set():
                    for key_press in self._pt_input.read_keys():
                        data = key_press.data
                        if data and len(data) == 1:
                            self._input_queue.put(data)
        except (EOFError, OSError):
            return

    def _start_input_reader(self) -> None:
        """Start background stdin reader once for fallback key input."""
        if self._input_thread_started:
            return
        if not sys.stdin.isatty():
            return
        # Avoid background stdin threads in pytest.
        if "PYTEST_CURRENT_TEST" in os.environ:
            return

        self._input_stop = threading.Event()
        self._input_thread_started = True
        self._pt_input = create_input()
        thread = threading.Thread(target=self._stdin_reader_loop, daemon=True)
        thread.start()

    def _stop_input_reader(self) -> None:
        """Stop and reset background stdin reader used for single-key polling."""
        self._input_stop.set()
        if self._pt_input is not None:
            self._pt_input.close()
            self._pt_input = None
        self._input_thread_started = False

    def _poll_input_key(self) -> str | None:
        """Poll one key press from available input sources.

        Returns:
            Single-character key if available, otherwise None.
        """
        if msvcrt is not None and msvcrt.kbhit():  # pragma: no cover
            return msvcrt.getwch()  # pragma: no cover
        try:
            char = self._input_queue.get_nowait()
        except queue.Empty:
            return None
        if char in ("\r", "\n"):
            return None
        return char

    def _fetch_device_count(self) -> int | None:
        """Fetch device count from backend API.

        Returns:
            Device count, or None if API unavailable/error
        """
        try:
            response = self.http_client.get("/api/devices/count")
            response.raise_for_status()
            data = response.json()
            count = data.get("count")
            return int(count) if count is not None else None
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException) as e:
            log_with_code(
                logger,
                "warning",
                MessageCode.TUI_API_ERROR,
                error=str(e),
            )
            return None

    def _fetch_dashboard_summary(self, force: bool = False) -> dict[str, Any] | None:
        """Fetch dashboard summary from API with lightweight caching.

        Args:
            force: When True, bypasses cache and fetches immediately.

        Returns:
            Dashboard summary payload, cached payload, or None on error.
        """
        now = time.monotonic()
        if (
            not force
            and self._dashboard_summary_cache is not None
            and now - self._dashboard_summary_last_fetch < self._dashboard_summary_ttl_seconds
        ):
            return self._dashboard_summary_cache

        try:
            response = self.http_client.get("/api/reports/dashboard-summary")
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                self._dashboard_summary_cache = data
                self._dashboard_summary_last_fetch = now
                return data
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError) as e:
            log_with_code(
                logger,
                "warning",
                MessageCode.TUI_API_ERROR,
                error=str(e),
            )
            return self._dashboard_summary_cache
        else:
            return self._dashboard_summary_cache

    def _authenticate_startup(self) -> bool:
        """Authenticate TUI user and configure API bearer token.

        Returns:
            True when login succeeds, False otherwise.
        """
        # Keep existing tests non-interactive; dedicated auth tests override this.
        if "PYTEST_CURRENT_TEST" in os.environ:
            return True

        default_username = os.getenv("SMARTNEST_ADMIN_USERNAME", "admin").strip() or "admin"

        self.console.print("[bold cyan]SmartNest Login[/bold cyan]")
        username_prompt = f"[bold]Username (default: {default_username}):[/bold] "
        username = self.console.input(username_prompt).strip() or default_username
        password = getpass.getpass("Password: ")

        return self._authenticate_with_credentials(username, password)

    def _authenticate_with_credentials(self, username: str, password: str) -> bool:
        """Authenticate and store credentials for token refresh retries."""
        self._auth_username = username
        self._auth_password = password

        if not password:
            self.console.print("[bold red]Password cannot be empty.[/bold red]")
            return False

        try:
            token = login_and_get_access_token(self.http_client, username, password)
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException) as e:
            log_with_code(
                logger,
                "warning",
                MessageCode.TUI_API_ERROR,
                error=f"Authentication failed: {e}",
            )
            self.console.print("[bold red]Login failed. Please check credentials.[/bold red]")
            return False

        if not token:
            log_with_code(
                logger,
                "warning",
                MessageCode.TUI_API_ERROR,
                error="Authentication failed: missing access token",
            )
            self.console.print("[bold red]Login failed. Please check credentials.[/bold red]")
            return False

        set_bearer_token(self.http_client, token)
        self.console.print(f"[bold green]Logged in as {username}[/bold green]")
        return True

    def _refresh_auth_token(self) -> bool:
        """Refresh JWT by re-authenticating with cached startup credentials."""
        if not self._auth_username or not self._auth_password:
            return False

        try:
            token = login_and_get_access_token(
                self.http_client,
                self._auth_username,
                self._auth_password,
            )
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException):
            return False

        if not token:
            return False

        set_bearer_token(self.http_client, token)
        log_with_code(
            logger,
            "info",
            MessageCode.TUI_API_ERROR,
            error="Auth token expired; successfully re-authenticated",
        )
        return True

    def _on_system_status(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Handle system status MQTT messages.

        Callback for smartnest/system/status topic.
        Updates system_status state with parsed JSON payload.

        Args:
            _client: Paho MQTT client instance (unused)
            _userdata: User data from client (unused)
            message: MQTT message object
        """
        try:
            payload = json.loads(message.payload.decode())
            self.system_status = payload
            log_with_code(
                logger,
                "debug",
                MessageCode.TUI_MQTT_MESSAGE_RECEIVED,
                topic=message.topic,
                payload=payload,
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log_with_code(
                logger,
                "warning",
                MessageCode.TUI_MQTT_MESSAGE_PARSE_ERROR,
                error=str(e),
                topic=message.topic,
            )

    def _handle_sigint(self, _signum: int, _frame: FrameType | None) -> None:
        """Handle SIGINT (Ctrl+C) for graceful shutdown.

        Args:
            signum: Signal number.
            frame: Current stack frame.
        """
        log_with_code(
            logger,
            "info",
            MessageCode.TUI_SHUTDOWN_REQUESTED,
            signal="SIGINT",
        )
        self.shutdown()

    def _handle_sigterm(self, _signum: int, _frame: FrameType | None) -> None:
        """Handle SIGTERM for graceful shutdown.

        Args:
            signum: Signal number.
            frame: Current stack frame.
        """
        log_with_code(
            logger,
            "info",
            MessageCode.TUI_SHUTDOWN_REQUESTED,
            signal="SIGTERM",
        )
        self.shutdown()

    def startup(self) -> None:
        """Perform startup initialization.

        Sets running flag, connects MQTT, subscribes to topics, and renders dashboard.
        """
        self.is_running = True
        log_with_code(logger, "info", MessageCode.TUI_STARTED)

        if not self._authenticate_startup():
            self.is_running = False
            return

        # Clear screen before rendering dashboard
        self.console.clear()

        # Connect to MQTT broker
        self.mqtt_client.connect()
        log_with_code(logger, "info", MessageCode.TUI_MQTT_CONNECTED)
        self._mqtt_connected_since = time.monotonic()
        self.system_status = {
            "connected": True,
            "status": "online",
            "uptime": "0s",
        }

        # Subscribe to system status updates
        self.mqtt_client.subscribe("smartnest/system/status")
        self.mqtt_client.add_topic_handler("smartnest/system/status", self._on_system_status)

        # Fetch device count from API
        device_count = self._fetch_device_count()
        dashboard_summary = self._fetch_dashboard_summary(force=True)

        # Render dashboard with device count
        self.dashboard.render(
            device_count=device_count,
            system_status=self.system_status,
            summary=dashboard_summary,
        )

    def shutdown(self) -> None:
        """Perform graceful shutdown.

        Disconnects MQTT, closes HTTP client, and exits application.
        """
        if not self.is_running:
            return

        self.is_running = False
        log_with_code(logger, "info", MessageCode.TUI_SHUTDOWN)
        self.console.print("\n[bold yellow]Shutting down SmartNest TUI...[/bold yellow]")

        # Disconnect MQTT client
        self.mqtt_client.disconnect()
        log_with_code(logger, "info", MessageCode.TUI_MQTT_DISCONNECTED, rc=0)

        # Close HTTP client
        self.http_client.close()
        sys.exit(0)

    def _render_current_screen(self, device_count: int | None = None) -> Any:
        """Render the current screen for Rich Live display.

        Routes to the active screen's render_live() method.

        Args:
            device_count: Current device count (passed to dashboard only).

        Returns:
            Renderable object for Rich Live.
        """
        if self.current_screen == "devices":
            return self.device_list.render_live()
        if self.current_screen == "device_detail":
            return self.device_detail.render_live()
        if self.current_screen == "sensors":
            return self.sensor_view.render_live()
        if self.current_screen == "reports":
            return self.reports.render_live()
        if self.current_screen == "settings":
            return self.settings.render_live()
        mqtt_status = dict(self.system_status)
        if mqtt_status.get("connected"):
            uptime_seconds = max(0, int(time.monotonic() - self._mqtt_connected_since))
            if uptime_seconds < _SECONDS_PER_MINUTE:
                mqtt_status["uptime"] = f"{uptime_seconds}s"
            else:
                minutes, seconds = divmod(uptime_seconds, _SECONDS_PER_MINUTE)
                mqtt_status["uptime"] = f"{minutes}m {seconds}s"
        dashboard_summary = self._fetch_dashboard_summary()
        # Default: dashboard
        return self.dashboard.render_live(
            device_count=device_count,
            system_status=mqtt_status,
            summary=dashboard_summary,
        )

    def _handle_navigation_key(self, key: str) -> bool:
        """Handle global navigation keys.

        Args:
            key: Raw key input.

        Returns:
            True if key was handled, False otherwise.
        """
        if key == "1":
            self.current_screen = "dashboard"
            return True
        if key == "2":
            self.current_screen = "devices"
            return True
        if key == "3":
            self.current_screen = "settings"
            return True
        if key == "4":
            self.current_screen = "sensors"
            return True
        if key == "5":
            self.current_screen = "reports"
            return True
        return False

    def _handle_devices_key(self, key_lower: str) -> bool:
        """Handle device-list screen keys.

        Args:
            key_lower: Lower-cased key input.

        Returns:
            True if key was handled, False otherwise.
        """
        filters = {
            "l": "lights",
            "s": "sensors",
            "w": "switches",
            "a": "all",
        }
        if key_lower == "/":
            self._pending_action = "search_devices"
            return True
        filter_type = filters.get(key_lower)
        if filter_type is None:
            return False
        self.device_list.set_filter(filter_type)
        return True

    def _handle_sensor_key(self, key_lower: str) -> bool:
        """Handle sensor screen action keys.

        Args:
            key_lower: Lower-cased key input.

        Returns:
            True if key was handled, False otherwise.
        """
        if key_lower == "r":
            self.sensor_view.refresh_now()
            return True
        if key_lower == "e":
            self.sensor_view.export_csv()
            return True
        return False

    def _handle_reports_key(self, key_lower: str) -> bool:
        """Handle reports screen action keys.

        Args:
            key_lower: Lower-cased key input.

        Returns:
            True if key was handled, False otherwise.
        """
        if key_lower == "r":
            self.reports.refresh_now()
            return True
        return False

    def _handle_settings_key(self, key_lower: str) -> bool:
        """Handle settings screen keys.

        Args:
            key_lower: Lower-cased key input.

        Returns:
            True if key was handled, False otherwise.
        """
        if key_lower == "a":
            self._pending_action = "add_user"
            return True
        if key_lower == "d":
            self._pending_action = "delete_user"
            return True
        return False

    def _handle_key(self, key: str) -> None:
        """Handle keyboard input for navigation and screen actions.

        Args:
            key: Single character key pressed by the user.
        """
        key_lower = key.lower()
        if key == "\x03":
            self.is_running = False
            return
        if key_lower == "q":
            self.is_running = False
            return
        if self._handle_navigation_key(key):
            return
        if self.current_screen == "devices":
            self._handle_devices_key(key_lower)
            return
        if self.current_screen == "sensors":
            self._handle_sensor_key(key_lower)
            return
        if self.current_screen == "reports":
            self._handle_reports_key(key_lower)
            return
        if self.current_screen == "settings":
            self._handle_settings_key(key_lower)

    def _execute_modal_action(self, action: str) -> None:
        """Execute a modal action outside the Rich Live context.

        Called by the outer run() loop after the Live context has exited,
        so that console.input() prompts render without corruption.

        Args:
            action: Action identifier ("add_user" or "delete_user").
        """
        if action == "add_user":
            self.settings.prompt_add_user()
        elif action == "delete_user":
            self.settings.prompt_delete_user()
        elif action == "search_devices":
            self.device_list.prompt_search()

    def run(self) -> None:
        """Run the TUI application.

        Main application loop with live display via Rich Live.
        Outer loop handles modal actions (prompts that run outside Live).
        Inner loop drives cross-platform polling refresh at 4 FPS (250ms).
        """
        try:
            self.startup()
            if not self.is_running:
                return
            self._start_input_reader()

            # Fetch initial device count
            device_count = self._fetch_device_count()

            # Outer loop: re-enters Live after each modal action
            while self.is_running or self._pending_action is not None:
                # Execute any pending modal action outside the Live context
                if self._pending_action is not None:
                    action = self._pending_action
                    self._pending_action = None
                    self._stop_input_reader()
                    self._execute_modal_action(action)
                    if not self.is_running:
                        break
                    self._start_input_reader()

                # Inner loop: live-refresh current screen at 4 FPS
                with Live(
                    self._render_current_screen(device_count=device_count),
                    console=self.console,
                    screen=self._live_alt_screen,
                    auto_refresh=False,
                ) as live:
                    while self.is_running and self._pending_action is None:
                        key = self._poll_input_key()
                        if key is not None:
                            self._handle_key(key)
                        live.update(
                            self._render_current_screen(device_count=device_count),
                            refresh=False,
                        )
                        live.refresh()
                        time.sleep(0.25)  # 4 FPS

        except KeyboardInterrupt:
            # Handled by _handle_sigint, but catch here for cleanliness
            pass
        finally:
            # Always restore terminal and perform clean exit
            self._stop_input_reader()
            self.console.clear()
            self.shutdown()


def main() -> None:
    """Entry point for SmartNest TUI application."""
    tui = SmartNestTUI()
    tui.run()


if __name__ == "__main__":  # pragma: no cover
    main()
