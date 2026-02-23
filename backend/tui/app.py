"""SmartNest Terminal User Interface Application.

Main TUI application class with lifespan management and graceful shutdown.
"""

from __future__ import annotations

import signal
import sys
import time
from typing import TYPE_CHECKING

import structlog
from rich.console import Console

from backend.logging.catalog import MessageCode
from backend.logging.utils import log_with_code

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
    """

    def __init__(self) -> None:
        """Initialize SmartNest TUI.

        Creates Rich Console and sets up signal handlers for graceful shutdown.
        """
        self.console = Console()
        self.is_running = False

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

        log_with_code(logger, "debug", MessageCode.TUI_INITIALIZED)

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

        Sets running flag and displays welcome message.
        """
        self.is_running = True
        log_with_code(logger, "info", MessageCode.TUI_STARTED)
        self.console.print("[bold green]SmartNest TUI[/bold green] - Home Automation Management")
        self.console.print("Press [bold]Ctrl+C[/bold] to exit\n")

    def shutdown(self) -> None:
        """Perform graceful shutdown.

        Clears running flag and displays goodbye message.
        """
        if not self.is_running:
            return

        self.is_running = False
        log_with_code(logger, "info", MessageCode.TUI_SHUTDOWN)
        self.console.print("\n[bold yellow]Shutting down SmartNest TUI...[/bold yellow]")
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
            self.console.print(
                "[dim]TUI framework ready. Screen implementation coming soon...[/dim]"
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
