"""SmartNest Terminal User Interface Application.

Main TUI application class with lifespan management and graceful shutdown.
"""

from __future__ import annotations

import json
import signal
import sys
import time
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from rich.console import Console
from rich.live import Live

from backend.logging.catalog import MessageCode
from backend.logging.utils import log_with_code
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig
from backend.tui.screens.dashboard import DashboardScreen
from backend.tui.screens.device_detail import DeviceDetailScreen
from backend.tui.screens.device_list import DeviceListScreen
from backend.tui.screens.sensor_view import SensorViewScreen
from backend.tui.screens.settings import SettingsScreen

if TYPE_CHECKING:
    from types import FrameType

    import paho.mqtt.client as mqtt

logger = structlog.get_logger(__name__)


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
        # Rich auto-detects terminal capabilities correctly (Git Bash, PowerShell, etc.)
        self.console = Console()
        self.is_running = False
        self.api_base_url = api_base_url
        self.http_client = httpx.Client(base_url=api_base_url, timeout=5.0)

        # Initialize screens
        self.dashboard = DashboardScreen(self.console)
        self.device_list = DeviceListScreen(self.console, self.http_client)
        self.device_detail = DeviceDetailScreen(self.console, self.http_client)
        self.sensor_view = SensorViewScreen(self.console, self.http_client)
        self.settings = SettingsScreen(self.console, self.http_client)

        # Current screen tracking
        self.current_screen = "dashboard"

        # MQTT client for real-time updates
        self.mqtt_config = mqtt_config or MQTTConfig(client_id="smartnest_tui")
        self.mqtt_client = SmartNestMQTTClient(self.mqtt_config)

        # System status state (updated via MQTT)
        self.system_status: dict[str, Any] = {}

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

        log_with_code(logger, "debug", MessageCode.TUI_INITIALIZED)

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

        # Clear screen before rendering dashboard
        self.console.clear()

        # Connect to MQTT broker
        self.mqtt_client.connect()
        log_with_code(logger, "info", MessageCode.TUI_MQTT_CONNECTED)

        # Subscribe to system status updates
        self.mqtt_client.subscribe("smartnest/system/status")
        self.mqtt_client.add_topic_handler("smartnest/system/status", self._on_system_status)

        # Fetch device count from API
        device_count = self._fetch_device_count()

        # Render dashboard with device count
        self.dashboard.render(device_count=device_count)

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

    def run(self) -> None:
        """Run the TUI application.

        Main application loop with live dashboard updates via Rich Live.
        Refreshes at 4 FPS (250ms) to display real-time MQTT updates.
        """
        try:
            self.startup()

            # Fetch initial device count
            device_count = self._fetch_device_count()

            # Display help message
            self.console.print()
            self.console.print(
                "[dim]Dashboard loaded. Press Ctrl+C to exit.[/dim]", justify="center"
            )
            self.console.print()

            # Live update loop with Rich Live (4 FPS = 250ms refresh)
            with Live(
                self.dashboard.render_live(
                    device_count=device_count, system_status=self.system_status
                ),
                console=self.console,
                refresh_per_second=4,
                screen=False,
            ) as live:
                # Keep alive until Ctrl+C (cross-platform compatible)
                try:
                    signal.pause()  # type: ignore[attr-defined]  # Unix only, not available on Windows
                except AttributeError:
                    # Windows doesn't have signal.pause(), use alternative
                    while self.is_running:
                        # Update live display with latest state
                        live.update(
                            self.dashboard.render_live(
                                device_count=device_count, system_status=self.system_status
                            )
                        )
                        time.sleep(0.25)  # 4 FPS

        except KeyboardInterrupt:
            # Handled by _handle_sigint, but catch here for cleanliness
            pass
        finally:
            # Always call shutdown() to ensure clean exit (idempotent)
            self.shutdown()


def main() -> None:
    """Entry point for SmartNest TUI application."""
    tui = SmartNestTUI()
    tui.run()


if __name__ == "__main__":  # pragma: no cover
    main()
