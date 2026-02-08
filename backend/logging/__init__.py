"""SmartNest structured logging package.

Provides AIP-193-inspired structured JSON logging with message catalogs,
correlation tracking, and child loggers via contextvars.

Public API::

    from backend.logging import configure_logging, get_logger, MessageCode
    from backend.logging import log_with_code, start_operation, end_operation
"""

from backend.logging.catalog import MessageCode
from backend.logging.config import configure_logging, get_logger
from backend.logging.utils import end_operation, log_with_code, start_operation

__all__ = [
    "MessageCode",
    "configure_logging",
    "end_operation",
    "get_logger",
    "log_with_code",
    "start_operation",
]
