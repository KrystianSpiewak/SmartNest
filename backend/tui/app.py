"""SmartNest Terminal User Interface Application.

Main TUI application class with lifespan management and graceful shutdown.
"""

from __future__ import annotations

import signal
import sys
import time
from typing import TYPE_CHECKING

import httpx
import structlog
from rich.console import Console

from backend.logging.catalog import MessageCode
from backend.logging.utils import log_with_code
from backend.tui.screens.dashboard import DashboardScreen

if TYPE_CHECKING:
    from types import FrameType

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
    """

    def __init__(self, api_base_url: str = "http://localhost:8000") -> None:
        """Initialize SmartNest TUI.

        Creates Rich Console, sets up signal handlers, and initializes screens.

        Args:
            api_base_url: Base URL for backend API (default: http://localhost:8000)
        """
        # Rich auto-detects terminal capabilities correctly (Git Bash, PowerShell, etc.)
        self.console = Console()
        self.is_running = False
        self.api_base_url = api_base_url
        self.http_client = httpx.Client(base_url=api_base_url, timeout=5.0)
        self.dashboard = DashboardScreen(self.console)

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

        Sets running flag, displays welcome message, and renders dashboard.
        """
        self.is_running = True
        log_with_code(logger, "info", MessageCode.TUI_STARTED)

        # Clear screen before rendering dashboard
        self.console.clear()

        # Fetch device count from API
        device_count = self._fetch_device_count()

        # Render dashboard with device count
        self.dashboard.render(device_count=device_count)

    def shutdown(self) -> None:
        """Perform graceful shutdown.

        Clears running flag and displays goodbye message.
        """
        if not self.is_running:
            return

        self.is_running = False
        log_with_code(logger, "info", MessageCode.TUI_SHUTDOWN)
        self.console.print("\n[bold yellow]Shutting down SmartNest TUI...[/bold yellow]")
        # Close HTTP client
        self.http_client.close()
        sys.exit(0)

    def run(self) -> None:
        """Run the TUI application.

        Main application loop. Currently displays welcome message and waits.
        Future: Will implement screen navigation and event loop.
        """
        try:
            self.startup()
            # TODO: Implement main event loop with screen navigation
            # For now, just wait for Ctrl+C
            self.console.print()
            self.console.print(
                "[dim]Dashboard loaded. Press Ctrl+C to exit.[/dim]", justify="center"
            )
            # Keep alive until Ctrl+C (cross-platform compatible)
            try:
                signal.pause()  # type: ignore[attr-defined]  # Unix only, not available on Windows
            except AttributeError:
                # Windows doesn't have signal.pause(), use alternative
                while self.is_running:
                    time.sleep(0.1)
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
