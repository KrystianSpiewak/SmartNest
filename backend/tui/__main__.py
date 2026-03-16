"""Entry point for running SmartNest TUI as a module.

Usage: python -m backend.tui
"""

from __future__ import annotations

import logging
import os

from backend.logging import configure_logging


def main() -> None:
    """Main entry point for TUI application.

    Configures logging and launches the TUI.
    """
    # Configure logging before importing the rest of the TUI stack.
    #
    # Some modules (e.g. MQTT client) create structlog loggers at import time.
    # If we configure logging after those imports, logger instances may be
    # cached with an overly-verbose level, and their output can interleave with
    # Rich Live rendering in terminals like Git Bash/mintty.
    log_level = os.getenv("SMARTNEST_TUI_LOG_LEVEL", "CRITICAL")

    # Redirect log output to a file (or devnull) to prevent log messages
    # from corrupting Rich Live display in TUI mode.
    log_file = os.getenv("SMARTNEST_LOG_FILE", os.devnull)
    with open(log_file, "a", encoding="utf-8", errors="replace") as log_stream:
        configure_logging(level=log_level, renderer="console", stream=log_stream)

        # Silence Paho's internal stdlib loggers in the TUI process. Even a small
        # amount of async logging can cause flicker / overlap with Live redraws.
        logging.getLogger("paho").setLevel(logging.CRITICAL)
        logging.getLogger("paho.mqtt").setLevel(logging.CRITICAL)
        logging.getLogger("paho.mqtt.client").setLevel(logging.CRITICAL)

        from backend.tui.app import main as tui_main  # noqa: PLC0415

        tui_main()


if __name__ == "__main__":
    main()
