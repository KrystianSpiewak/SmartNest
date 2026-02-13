"""SmartNest MQTT Client.

Synchronous MQTT client wrapping Paho MQTT v2.  Provides:

- Automatic reconnection via Paho's ``reconnect_delay_set()``
- Last Will and Testament (LWT) for device status
- Per-topic callback routing via ``message_callback_add()``
- Structured JSON logging via ``structlog`` with message catalog codes
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Protocol

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from backend.logging import MessageCode, get_logger, log_with_code
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    from paho.mqtt.client import ConnectFlags, DisconnectFlags
    from paho.mqtt.properties import Properties
    from paho.mqtt.reasoncodes import ReasonCode

    from backend.mqtt.config import MQTTConfig

logger = get_logger(__name__)

# stdlib logger kept for Paho's internal enable_logger()
_paho_logger = logging.getLogger(f"{__name__}.paho")

# Default connect timeout in seconds
_CONNECT_TIMEOUT = 10.0

# LWT (Last Will Testament) message constants - public for testing
LWT_EVENT_TYPE = "client_offline"
LWT_EVENT_KEY = "event"
LWT_CLIENT_ID_KEY = "client_id"


class MessageHandler(Protocol):
    """Callback signature for per-topic message handlers."""

    def __call__(
        self,
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None: ...


class SmartNestMQTTClient:
    """Synchronous MQTT client for the SmartNest automation system.

    Uses ``connect()`` + ``loop_start()`` for background network processing.
    Thread-safe publish via ``paho.mqtt.client.Client.publish()``.

    Example::

        config = MQTTConfig(broker="localhost")
        client = SmartNestMQTTClient(config)
        client.connect()
        client.publish("smartnest/device/light_01/command", {"power": "on"})
        client.disconnect()
    """

    def __init__(self, config: MQTTConfig) -> None:
        self._config = config
        self._connected = threading.Event()
        self._paho = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
        )

        # Wire Paho callbacks
        self._paho.on_connect = self._on_connect
        self._paho.on_disconnect = self._on_disconnect
        self._paho.on_message = self._on_message

        # Route Paho internal logs through stdlib logging
        self._paho.enable_logger(_paho_logger)

        # Configure native exponential-backoff reconnection
        self._paho.reconnect_delay_set(
            min_delay=config.reconnect_min_delay,
            max_delay=config.reconnect_max_delay,
        )

        # Credentials
        if config.username is not None:
            self._paho.username_pw_set(config.username, config.password)

        # LWT: mark this client offline if it drops unexpectedly
        self._paho.will_set(
            topic=TopicBuilder.system_topic(),  # Uses default "event" topic
            payload=json.dumps(
                {
                    LWT_EVENT_KEY: LWT_EVENT_TYPE,
                    LWT_CLIENT_ID_KEY: config.client_id,
                }
            ),
            qos=1,
            retain=False,
        )

    # -- Properties ------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the client is currently connected."""
        return self._connected.is_set()

    def set_connected_for_test(self, connected: bool = True) -> None:
        """Set connection state for testing. NOT for production use."""
        if connected:
            self._connected.set()
        else:
            self._connected.clear()

    @property
    def config(self) -> MQTTConfig:
        """Return the current MQTT configuration (read-only)."""
        return self._config

    @property
    def paho_client(self) -> mqtt.Client:
        """Return the internal Paho MQTT client for testing purposes."""
        return self._paho

    # -- Paho callbacks --------------------------------------------------------

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        """Handle successful or failed connection."""
        if reason_code == 0:
            log_with_code(
                logger,
                "info",
                MessageCode.MQTT_CONNECTION_SUCCESS,
                broker=self._config.broker,
                port=self._config.port,
                client_id=self._config.client_id,
            )
            self._connected.set()
        else:
            # Clear state first (critical path)
            self._connected.clear()
            # Then attempt logging (may fail during shutdown)
            try:
                logger.error("connection_refused", reason_code=str(reason_code))
            except (OSError, ValueError):
                # Suppress logging errors during shutdown - state already cleared
                pass

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: DisconnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        """Handle broker disconnection."""
        self._connected.clear()
        if reason_code == 0:
            log_with_code(logger, "info", MessageCode.MQTT_DISCONNECTED_CLEAN)
        else:
            log_with_code(
                logger,
                "warning",
                MessageCode.MQTT_DISCONNECTED_UNEXPECTED,
                reason=str(reason_code),
            )

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        """Catch-all handler for messages without a per-topic callback."""
        log_with_code(
            logger,
            "debug",
            MessageCode.MQTT_MESSAGE_UNHANDLED,
            topic=message.topic,
            qos=message.qos,
            retain=message.retain,
            payload=message.payload.decode("utf-8", errors="replace")[:200],
        )

    # -- Public API ------------------------------------------------------------

    def connect(self, timeout: float = _CONNECT_TIMEOUT) -> bool:
        """Connect to the MQTT broker and start the network loop.

        Blocks up to *timeout* seconds waiting for ``CONNACK``.

        Returns:
            ``True`` if connected within the timeout, ``False`` otherwise.
        """
        log_with_code(
            logger,
            "info",
            MessageCode.MQTT_CONNECTION_INITIATED,
            broker=self._config.broker,
            port=self._config.port,
            client_id=self._config.client_id,
        )
        try:
            self._paho.connect(
                self._config.broker,
                self._config.port,
                keepalive=self._config.keepalive,
            )
        except OSError:
            # Log error for troubleshooting, but suppress logging failures
            try:
                logger.exception("connection_initiation_failed")
            except (OSError, ValueError):
                # Suppress logging errors - connection already failed
                pass
            return False

        self._paho.loop_start()

        # NOTE: Mutation testing - timeout=None mutant is expected survivor
        # Testing timeout=None would cause tests to hang indefinitely
        # This is defensive code that prevents infinite blocking
        if not self._connected.wait(timeout=timeout):
            log_with_code(
                logger,
                "error",
                MessageCode.MQTT_CONNECTION_TIMEOUT,
                timeout=timeout,
            )
            self._paho.loop_stop()
            return False

        return True

    def disconnect(self) -> None:
        """Disconnect from broker and stop the network loop."""
        # Log before stopping (may fail if logging infrastructure shutting down)
        try:
            logger.info("disconnecting")
        except (OSError, ValueError):
            # Suppress logging errors during shutdown
            pass

        self._paho.loop_stop()
        self._paho.disconnect()
        self._connected.clear()

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        """Publish a JSON-serialized message.

        Args:
            topic: MQTT topic string.
            payload: Dictionary to be JSON-serialized.
            qos: Quality-of-Service level (0, 1, or 2).
            retain: Whether the broker should retain the message.

        Returns:
            ``True`` if the message was enqueued successfully.
        """
        if not self.is_connected:
            log_with_code(logger, "error", MessageCode.MQTT_PUBLISH_NOT_CONNECTED)
            return False

        data = json.dumps(payload)
        result = self._paho.publish(topic, data, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log_with_code(
                logger,
                "error",
                MessageCode.MQTT_PUBLISH_FAILED,
                topic=topic,
                rc=result.rc,
            )
            return False

        log_with_code(
            logger,
            "debug",
            MessageCode.MQTT_PUBLISH_SUCCESS,
            topic=topic,
            qos=qos,
            retain=retain,
        )
        return True

    def subscribe(self, topic: str, qos: int = 1) -> bool:
        """Subscribe to a topic.

        Args:
            topic: MQTT topic or wildcard pattern.
            qos: Maximum QoS level for delivery.

        Returns:
            ``True`` if the subscription was enqueued.
        """
        if not self.is_connected:
            log_with_code(logger, "error", MessageCode.MQTT_SUBSCRIBE_NOT_CONNECTED)
            return False

        result, _mid = self._paho.subscribe(topic, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            log_with_code(
                logger,
                "error",
                MessageCode.MQTT_SUBSCRIBE_FAILED,
                topic=topic,
                rc=result,
            )
            return False

        log_with_code(
            logger,
            "info",
            MessageCode.MQTT_SUBSCRIBE_SUCCESS,
            topic=topic,
            qos=qos,
        )
        return True

    def add_topic_handler(self, topic_filter: str, handler: MessageHandler) -> None:
        """Register a per-topic message callback.

        Uses Paho's native ``message_callback_add()`` for efficient
        topic-based routing.  Wildcard patterns (``+`` / ``#``) are supported.

        Args:
            topic_filter: MQTT topic filter (may contain wildcards).
            handler: Callback matching the ``MessageHandler`` protocol.
        """
        self._paho.message_callback_add(topic_filter, handler)
        log_with_code(
            logger,
            "info",
            MessageCode.MQTT_HANDLER_REGISTERED,
            topic_filter=topic_filter,
        )

    def remove_topic_handler(self, topic_filter: str) -> None:
        """Remove a previously registered per-topic callback.

        Args:
            topic_filter: The exact filter string passed to
                :meth:`add_topic_handler`.
        """
        self._paho.message_callback_remove(topic_filter)
        log_with_code(
            logger,
            "debug",
            MessageCode.MQTT_HANDLER_REMOVED,
            topic_filter=topic_filter,
        )

    def publish_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
    ) -> bool:
        """Convenience: publish a device state update (retained, QoS 1).

        Adds a ``timestamp`` field automatically.
        """
        state["timestamp"] = time.time()
        topic = TopicBuilder.device_topic(device_id, "state")
        return self.publish(topic, state, qos=1, retain=True)

    def publish_sensor_data(
        self,
        device_id: str,
        data: dict[str, Any],
    ) -> bool:
        """Convenience: publish sensor data (non-retained, QoS 0)."""
        data["timestamp"] = time.time()
        topic = TopicBuilder.sensor_topic(device_id)
        return self.publish(topic, data, qos=0, retain=False)
