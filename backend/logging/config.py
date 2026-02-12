"""Structured logging configuration for SmartNest.

Configures ``structlog`` with environment-aware rendering:

- **Development:** Pretty console output with colors (human-friendly).
- **Testing / Production:** JSON lines (machine-parseable, cloud-ready).

Log levels follow RFC 5424 severity (mapped through Python ``logging``):

======== ======= ========================
RFC 5424 Numeric Python constant
======== ======= ========================
Critical 2       ``logging.CRITICAL`` (50)
Error    3       ``logging.ERROR``    (40)
Warning  4       ``logging.WARNING``  (30)
Info     6       ``logging.INFO``     (20)
Debug    7       ``logging.DEBUG``    (10)
======== ======= ========================

Usage::

    from backend.logging import configure_logging, get_logger

    # Call once at application startup
    configure_logging(level="DEBUG", renderer="console")

    logger = get_logger("backend.mqtt.client")
    logger.info("broker_connected", broker="localhost", port=1883)
"""

from __future__ import annotations

import logging
import sys

import structlog

# Sentinel to detect whether configure_logging has been called
_configured = False


def _add_app_context(
    _logger: structlog.types.WrappedLogger,
    _method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Processor: inject application-level context into every log entry."""
    event_dict.setdefault("app", "smartnest")
    return event_dict


def build_shared_processors(renderer: str) -> list[structlog.types.Processor]:
    """Build processor list based on renderer type (pure function).

    Extracting this as a pure function makes configuration testable
    and kills multiple mutation testing survivors.

    Args:
        renderer: Output format ("console" or "json").

    Returns:
        List of structlog processors including the final renderer.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_app_context,
    ]

    if renderer == "json":
        shared_processors.append(structlog.processors.format_exc_info)
        final_processor: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        final_processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )

    shared_processors.append(final_processor)
    return shared_processors


def configure_logging(
    *,
    level: str = "INFO",
    renderer: str = "console",
) -> None:
    """Configure ``structlog`` for the SmartNest application.

    Call **once** at application startup (``main()`` or ``conftest.py``).

    Args:
        level: Log level name — ``DEBUG``, ``INFO``, ``WARNING``,
            ``ERROR``, or ``CRITICAL``.
        renderer: Output format.
            ``"console"`` → coloured human-friendly output (dev).
            ``"json"`` → one JSON object per line (test / prod).
    """
    global _configured

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib root logger at WARNING to suppress third-party debug noise
    # (e.g., aiosqlite internal operations, paho.mqtt verbose logs)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=logging.WARNING,  # Root logger stays quiet
        force=True,
    )

    # Enable requested level only for SmartNest code (backend.* namespace)
    logging.getLogger("backend").setLevel(numeric_level)

    shared_processors = build_shared_processors(renderer)

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    """Return a bound ``structlog`` logger.

    If :func:`configure_logging` has not been called yet, a basic console
    configuration is applied automatically so that early-import loggers
    still produce output.

    Args:
        name: Logger name (typically ``__name__``).  Appears as
            ``logger`` in JSON output.
    """
    if not _configured:
        configure_logging(level="DEBUG", renderer="console")

    log: structlog.typing.FilteringBoundLogger = structlog.get_logger()
    if name:
        return log.bind(logger_name=name)
    return log


def reset_logging() -> None:
    """Reset logging configuration.  **For testing only.**"""
    global _configured
    _configured = False
    structlog.reset_defaults()
