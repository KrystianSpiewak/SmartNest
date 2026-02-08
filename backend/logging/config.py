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
    global _configured  # noqa: PLW0603

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib root logger so Paho and other libs flow through
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=numeric_level,
        force=True,
    )

    # Shared processors (order matters)
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

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:  # type: ignore[type-arg]
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

    log: structlog.stdlib.BoundLogger = structlog.get_logger()  # type: ignore[assignment]
    if name:
        return log.bind(logger_name=name)  # type: ignore[return-value]
    return log


def reset_logging() -> None:
    """Reset logging configuration.  **For testing only.**"""
    global _configured  # noqa: PLW0603
    _configured = False
    structlog.reset_defaults()
