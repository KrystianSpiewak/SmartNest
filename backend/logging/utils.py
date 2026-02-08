"""Logging utilities — correlation tracking and catalog-aware helpers.

Provides three main capabilities:

1. **Correlation tracking** via ``start_operation()`` / ``end_operation()``.
   Binds a unique ``correlation_id`` plus arbitrary context into
   ``contextvars`` so that every log emitted within the scope automatically
   carries the correlation metadata.

2. **Catalog-aware logging** via ``log_with_code()``.  Looks up the human
   message from :mod:`backend.logging.catalog`, attaches the stable
   ``msg_id`` field, and forwards all context as structured key-value pairs.

3. **Scoped child loggers** — call ``get_logger(__name__).bind(device_id=…)``
   to create a child logger that automatically adds scope context to every
   subsequent log call (structlog's native bound-logger pattern).

Usage::

    from backend.logging import get_logger, log_with_code, MessageCode
    from backend.logging import start_operation, end_operation

    logger = get_logger(__name__)

    # Simple structured log
    logger.info("something_happened", detail="value")

    # Catalog-based log (stable msg_id)
    log_with_code(
        logger,
        "error",
        MessageCode.MQTT_PUBLISH_FAILED,
        topic="smartnest/device/light_01/command",
        rc=4,
    )

    # Correlated operation
    cid = start_operation("device_command", device_id="light_01")
    try:
        logger.info("processing_command")  # includes correlation_id
    finally:
        end_operation()
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from structlog.contextvars import bind_contextvars, unbind_contextvars

from backend.logging.catalog import MessageCode, format_message

if TYPE_CHECKING:
    import structlog


def generate_correlation_id() -> str:
    """Return a new UUID-4 correlation identifier."""
    return uuid.uuid4().hex[:12]


def start_operation(operation: str, **context: Any) -> str:
    """Begin a correlated operation.

    Generates a ``correlation_id`` and binds it — together with
    *operation* and any extra *context* — into ``contextvars``.
    All ``structlog`` loggers will automatically include these fields
    until :func:`end_operation` is called.

    Args:
        operation: Short label for the operation (e.g. ``"mqtt_publish"``).
        **context: Additional key-value pairs to bind.

    Returns:
        The generated correlation ID.
    """
    correlation_id = generate_correlation_id()
    bind_contextvars(
        correlation_id=correlation_id,
        operation=operation,
        **context,
    )
    return correlation_id


def end_operation(*extra_keys: str) -> None:
    """End a correlated operation started with :func:`start_operation`.

    Removes ``correlation_id``, ``operation``, and any *extra_keys*
    from ``contextvars`` to prevent context leakage.
    """
    keys_to_remove = ("correlation_id", "operation", *extra_keys)
    unbind_contextvars(*keys_to_remove)


def log_with_code(
    logger: structlog.stdlib.BoundLogger,
    level: str,
    code: MessageCode,
    **context: Any,
) -> None:
    """Emit a structured log entry using a message-catalog code.

    The rendered human message becomes the ``event`` field; the stable
    ``msg_id`` is attached so that operators can filter / search by code
    regardless of parameter values.

    Args:
        logger: A ``structlog`` bound logger.
        level: Log level name (``"debug"``, ``"info"``, ``"warning"``,
            ``"error"``, ``"critical"``).
        code: :class:`~backend.logging.catalog.MessageCode` member.
        **context: Values forwarded both to the message template **and**
            as structured key-value pairs in the log entry.

    Example::

        log_with_code(
            logger,
            "error",
            MessageCode.MQTT_CONNECTION_FAILED,
            broker="localhost",
            port=1883,
            attempt=1,
            max_attempts=3,
            error="Connection refused",
        )

    Produces (JSON renderer)::

        {
          "event": "Failed to connect to MQTT broker at localhost:1883 ...",
          "msg_id": "MQTT_003",
          "broker": "localhost",
          "port": 1883,
          ...
        }
    """
    message = format_message(code, **context)
    log_fn = getattr(logger, level)
    log_fn(message, msg_id=code.value, **context)
