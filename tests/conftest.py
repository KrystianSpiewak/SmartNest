"""Global test configuration.

Configures structured logging for all tests (JSON renderer for easy assertions).
"""

from __future__ import annotations

import contextlib

from backend.logging.config import configure_logging

# Wrap logging configuration to handle mutation testing scenarios
# where stdout/stderr may be closed or redirected improperly.
with contextlib.suppress(OSError, ValueError):
    # Configure once at import time so every test module gets consistent logging.
    # Use console renderer for human-readable test output.
    configure_logging(level="DEBUG", renderer="console")
