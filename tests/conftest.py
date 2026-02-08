"""Global test configuration.

Configures structured logging for all tests (JSON renderer for easy assertions).
"""

from __future__ import annotations

from backend.logging.config import configure_logging

# Configure once at import time so every test module gets consistent logging.
# Use JSON so log output is machine-parseable if needed; level DEBUG to
# capture all events during test runs.
configure_logging(level="DEBUG", renderer="console")
