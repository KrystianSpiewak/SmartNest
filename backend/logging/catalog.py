"""SmartNest message catalog.

Every log event in SmartNest has a stable **message code** (e.g. ``MQTT_001``)
that maps to exactly one call-site in the codebase.  This makes it trivial to
``grep`` for a code seen in production logs and land on the single line that
emitted it.

The design is inspired by Google AIP-193 (structured error metadata) and
adapts the pattern for operational logging:

- **Code:**       Machine-stable identifier (``MQTT_001``).
- **Template:**   Human-readable message with ``{placeholder}`` params.
- **Category:**   Prefix groups related messages (``MQTT_``, ``DEV_``, …).

Usage::

    from backend.logging.catalog import MessageCode, format_message

    msg = format_message(
        MessageCode.MQTT_CONNECTION_FAILED,
        broker="localhost",
        attempt=1,
        max_attempts=3,
        error="Connection refused",
    )
    # → "Failed to connect to MQTT broker at localhost (attempt 1/3): Connection refused"
"""

from __future__ import annotations

from enum import StrEnum


class MessageCode(StrEnum):
    """Stable message codes for structured log events.

    Naming convention
    -----------------
    ``{CATEGORY}_{SEQ:03d}``

    Categories:
        ``MQTT_``  — Broker / protocol operations.
        ``DEV_``   — Device lifecycle and commands.
        ``DB_``    — Database operations (future).
        ``API_``   — FastAPI request handling (future).
        ``AUTH_``  — Authentication / authorisation (future).
        ``TUI_``   — Terminal UI events (future).
        ``SYS_``   — Application lifecycle.
    """

    # -- MQTT operations (backend/mqtt/client.py) ------------------------------
    MQTT_CONNECTION_INITIATED = "MQTT_001"
    MQTT_CONNECTION_SUCCESS = "MQTT_002"
    MQTT_CONNECTION_FAILED = "MQTT_003"
    MQTT_CONNECTION_TIMEOUT = "MQTT_004"
    MQTT_DISCONNECTED_CLEAN = "MQTT_005"
    MQTT_DISCONNECTED_UNEXPECTED = "MQTT_006"
    MQTT_PUBLISH_SUCCESS = "MQTT_007"
    MQTT_PUBLISH_FAILED = "MQTT_008"
    MQTT_PUBLISH_NOT_CONNECTED = "MQTT_009"
    MQTT_SUBSCRIBE_SUCCESS = "MQTT_010"
    MQTT_SUBSCRIBE_FAILED = "MQTT_011"
    MQTT_SUBSCRIBE_NOT_CONNECTED = "MQTT_012"
    MQTT_MESSAGE_UNHANDLED = "MQTT_013"
    MQTT_HANDLER_REGISTERED = "MQTT_014"
    MQTT_HANDLER_REMOVED = "MQTT_015"

    # -- Device operations (backend/devices/*.py) ------------------------------
    DEVICE_REGISTERED = "DEV_001"
    DEVICE_REGISTRATION_FAILED = "DEV_002"
    DEVICE_NOT_FOUND = "DEV_003"
    DEVICE_CONNECTED = "DEV_004"
    DEVICE_DISCONNECTED = "DEV_005"
    DEVICE_COMMAND_SENT = "DEV_006"
    DEVICE_COMMAND_FAILED = "DEV_007"
    DEVICE_STATE_UPDATED = "DEV_008"
    DEVICE_STATE_PUBLISHED = "DEV_009"
    DEVICE_SENSOR_PUBLISHED = "DEV_010"
    DEVICE_DISCOVERY_ANNOUNCED = "DEV_011"

    # -- Database operations (backend/database/*.py — future) ------------------
    DB_CONNECTION_SUCCESS = "DB_001"
    DB_CONNECTION_FAILED = "DB_002"
    DB_QUERY_SUCCESS = "DB_003"
    DB_QUERY_FAILED = "DB_004"

    # -- System / application lifecycle ----------------------------------------
    SYS_STARTUP = "SYS_001"
    SYS_SHUTDOWN = "SYS_002"
    SYS_CONFIG_LOADED = "SYS_003"


# ---------------------------------------------------------------------------
# Message templates — one entry per MessageCode.
# Templates use str.format() placeholders matching the ``**context`` kwargs
# supplied to ``log_with_code()``.
# ---------------------------------------------------------------------------

_CATALOG: dict[MessageCode, str] = {
    # MQTT
    MessageCode.MQTT_CONNECTION_INITIATED: (
        "Connecting to MQTT broker at {broker}:{port} as {client_id}"
    ),
    MessageCode.MQTT_CONNECTION_SUCCESS: (
        "Connected to MQTT broker at {broker}:{port} as {client_id}"
    ),
    MessageCode.MQTT_CONNECTION_FAILED: (
        "Failed to connect to MQTT broker at {broker}:{port}"
        " (attempt {attempt}/{max_attempts}): {error}"
    ),
    MessageCode.MQTT_CONNECTION_TIMEOUT: ("Connection timed out after {timeout:.1f}s"),
    MessageCode.MQTT_DISCONNECTED_CLEAN: "Disconnected cleanly from broker",
    MessageCode.MQTT_DISCONNECTED_UNEXPECTED: (
        "Unexpected disconnect from broker (reason={reason}). Paho will auto-reconnect."
    ),
    MessageCode.MQTT_PUBLISH_SUCCESS: "Published to {topic} (qos={qos}, retain={retain})",
    MessageCode.MQTT_PUBLISH_FAILED: "Publish failed on {topic} (rc={rc})",
    MessageCode.MQTT_PUBLISH_NOT_CONNECTED: "Cannot publish: not connected",
    MessageCode.MQTT_SUBSCRIBE_SUCCESS: "Subscribed to {topic} (qos={qos})",
    MessageCode.MQTT_SUBSCRIBE_FAILED: "Subscribe failed for {topic} (rc={rc})",
    MessageCode.MQTT_SUBSCRIBE_NOT_CONNECTED: "Cannot subscribe: not connected",
    MessageCode.MQTT_MESSAGE_UNHANDLED: (
        "Unhandled message on {topic} (qos={qos}, retain={retain}): {payload}"
    ),
    MessageCode.MQTT_HANDLER_REGISTERED: "Registered handler for topic filter: {topic_filter}",
    MessageCode.MQTT_HANDLER_REMOVED: "Removed handler for topic filter: {topic_filter}",
    # Devices
    MessageCode.DEVICE_REGISTERED: "Device '{device_id}' registered as {device_type}",
    MessageCode.DEVICE_REGISTRATION_FAILED: ("Failed to register device '{device_id}': {error}"),
    MessageCode.DEVICE_NOT_FOUND: "Device '{device_id}' not found in registry",
    MessageCode.DEVICE_CONNECTED: "Device '{device_id}' connected",
    MessageCode.DEVICE_DISCONNECTED: "Device '{device_id}' disconnected: {reason}",
    MessageCode.DEVICE_COMMAND_SENT: ("Sent command '{command}' to device '{device_id}'"),
    MessageCode.DEVICE_COMMAND_FAILED: (
        "Command '{command}' failed for device '{device_id}': {error}"
    ),
    MessageCode.DEVICE_STATE_UPDATED: "Device '{device_id}' state updated",
    MessageCode.DEVICE_STATE_PUBLISHED: ("Published state for device '{device_id}' to {topic}"),
    MessageCode.DEVICE_SENSOR_PUBLISHED: (
        "Published sensor data for device '{device_id}' to {topic}"
    ),
    MessageCode.DEVICE_DISCOVERY_ANNOUNCED: ("Device '{device_id}' announced on discovery topic"),
    # Database
    MessageCode.DB_CONNECTION_SUCCESS: "Database connection established: {path}",
    MessageCode.DB_CONNECTION_FAILED: "Database connection failed: {error}",
    MessageCode.DB_QUERY_SUCCESS: "Query executed: {operation}",
    MessageCode.DB_QUERY_FAILED: "Query failed ({operation}): {error}",
    # System
    MessageCode.SYS_STARTUP: "SmartNest {version} starting",
    MessageCode.SYS_SHUTDOWN: "SmartNest shutting down: {reason}",
    MessageCode.SYS_CONFIG_LOADED: "Configuration loaded from {source}",
}


def format_message(code: MessageCode, **context: object) -> str:
    """Render the catalog template for *code* with the given context.

    Unknown placeholders are left as-is so that a missing kwarg never
    crashes the logging pipeline.

    Args:
        code: A :class:`MessageCode` member.
        **context: Values to interpolate into the message template.

    Returns:
        The formatted human-readable message string.

    Raises:
        KeyError: If *code* is not present in the catalog (programming error).
    """
    template = _CATALOG[code]
    try:
        return template.format(**context)
    except KeyError:
        # Graceful degradation: return template with raw placeholders
        return template
