"""Base device abstraction for SmartNest mock IoT devices.

Provides the ``BaseDevice`` abstract class that encapsulates the MQTT
lifecycle shared by all mock devices:

- Connect to broker and subscribe to command topics
- Publish discovery announcement on startup
- Route incoming commands to device-specific handlers
- Publish device state updates
- Clean disconnect with logging

Concrete devices (lights, sensors, switches) inherit from ``BaseDevice``
and implement ``_handle_command()`` and ``_get_discovery_payload()``.

Usage::

    class MockSmartLight(BaseDevice):
        def _handle_command(self, client, userdata, message, /):
            ...

        def _get_discovery_payload(self):
            return {"device_type": "light", ...}
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from backend.logging import MessageCode, get_logger, log_with_code, start_operation
from backend.mqtt import MQTTConfig, SmartNestMQTTClient, TopicBuilder
from backend.mqtt.topics import validate_device_id

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

logger = get_logger(__name__)


class BaseDevice(ABC):
    """Abstract base for all SmartNest mock IoT devices.

    Each device owns a :class:`SmartNestMQTTClient` instance and manages
    its MQTT lifecycle.  The ``start()`` / ``stop()`` methods handle
    connection, subscription, discovery, and teardown.

    Attributes:
        device_id: Unique device identifier (validated for MQTT safety).
        device_type: Human-readable type label (e.g. ``"smart_light"``).
        name: Display name for the device.

    Example::

        light = MockSmartLight(
            device_id="light_01",
            name="Living Room Light",
            config=MQTTConfig(broker="localhost", client_id="light_01"),
        )
        light.start()
        # device is now connected, subscribed, and discoverable
        light.stop()
    """

    def __init__(
        self,
        *,
        device_id: str,
        device_type: str,
        name: str,
        config: MQTTConfig,
    ) -> None:
        validate_device_id(device_id)

        self._device_id = device_id
        self._device_type = device_type
        self._name = name
        self._client = SmartNestMQTTClient(config)
        self._running = False

        # Child logger with permanent device context
        self._logger = logger.bind(device_id=device_id, device_type=device_type)

        log_with_code(
            self._logger,
            "info",
            MessageCode.DEVICE_REGISTERED,
            device_id=device_id,
            device_type=device_type,
        )

    # -- Properties ------------------------------------------------------------

    @property
    def device_id(self) -> str:
        """Return the unique device identifier."""
        return self._device_id

    @property
    def device_type(self) -> str:
        """Return the device type label."""
        return self._device_type

    @property
    def name(self) -> str:
        """Return the device display name."""
        return self._name

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the device is started and connected."""
        return self._running

    @property
    def client(self) -> SmartNestMQTTClient:
        """Return the underlying MQTT client (for testing)."""
        return self._client

    # -- Lifecycle -------------------------------------------------------------

    def start(self, timeout: float = 10.0) -> bool:
        """Connect to the broker, subscribe to commands, and announce discovery.

        Args:
            timeout: Maximum seconds to wait for broker connection.

        Returns:
            ``True`` if the device started successfully.
        """
        if self._running:
            self._logger.warning("device_already_running")
            return True

        start_operation("device_start", device_id=self._device_id)

        if not self._client.connect(timeout=timeout):
            log_with_code(
                self._logger,
                "error",
                MessageCode.DEVICE_REGISTRATION_FAILED,
                device_id=self._device_id,
                error="Failed to connect to MQTT broker",
            )
            return False

        log_with_code(
            self._logger,
            "info",
            MessageCode.DEVICE_CONNECTED,
            device_id=self._device_id,
        )

        # Subscribe to command topic and register handler
        command_topic = TopicBuilder.device_topic(self._device_id, "command")
        self._client.subscribe(command_topic)
        self._client.add_topic_handler(command_topic, self._handle_command)

        # Publish discovery announcement
        self._publish_discovery()

        self._running = True
        self._on_start()
        return True

    def stop(self, reason: str = "shutdown") -> None:
        """Disconnect from the broker and clean up resources.

        Args:
            reason: Human-readable reason for stopping.
        """
        if not self._running:
            return

        self._on_stop()
        self._running = False

        # Remove command handler before disconnecting
        command_topic = TopicBuilder.device_topic(self._device_id, "command")
        self._client.remove_topic_handler(command_topic)
        self._client.disconnect()

        log_with_code(
            self._logger,
            "info",
            MessageCode.DEVICE_DISCONNECTED,
            device_id=self._device_id,
            reason=reason,
        )

    # -- Discovery -------------------------------------------------------------

    def _publish_discovery(self) -> None:
        """Publish a discovery announcement to the broker."""
        payload = self._get_discovery_payload()
        topic = TopicBuilder.discovery_topic()
        success = self._client.publish(topic, payload, qos=1, retain=True)

        if success:
            log_with_code(
                self._logger,
                "info",
                MessageCode.DEVICE_DISCOVERY_ANNOUNCED,
                device_id=self._device_id,
            )

    # -- State publishing ------------------------------------------------------

    def _publish_state(self, state: dict[str, Any]) -> bool:
        """Publish device state (retained, QoS 1).

        Uses :meth:`SmartNestMQTTClient.publish_device_state` which
        auto-adds a ``timestamp`` field and publishes to the device
        state topic.

        Args:
            state: Device state dictionary.

        Returns:
            ``True`` if the state was published successfully.
        """
        success = self._client.publish_device_state(self._device_id, state)
        if success:
            topic = TopicBuilder.device_topic(self._device_id, "state")
            log_with_code(
                self._logger,
                "debug",
                MessageCode.DEVICE_STATE_PUBLISHED,
                device_id=self._device_id,
                topic=topic,
            )
        return success

    # -- Hooks for subclasses --------------------------------------------------

    def _on_start(self) -> None:
        """Called after the device is fully started.

        Override in subclasses to set up periodic tasks or publish
        initial state.  Default implementation is a no-op.
        """
        return

    def _on_stop(self) -> None:
        """Called before the device begins teardown.

        Override in subclasses to cancel timers or flush state.
        Default implementation is a no-op.
        """
        return

    # -- Abstract methods ------------------------------------------------------

    @abstractmethod
    def _handle_command(
        self,
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Process an incoming MQTT command message.

        Must match the :class:`MessageHandler` protocol signature
        (positional-only parameters).

        Args:
            client: The Paho MQTT client instance.
            userdata: User data set on the client.
            message: The received MQTT message.
        """

    @abstractmethod
    def _get_discovery_payload(self) -> dict[str, Any]:
        """Return the discovery announcement payload for this device.

        The payload is published to ``smartnest/discovery/announce``
        with ``retain=True`` so late-joining consumers see it.

        Must include at minimum:
            - ``device_id``
            - ``name``
            - ``device_type``
            - ``capabilities``
            - ``topics``
        """

    # -- Utility ---------------------------------------------------------------

    @staticmethod
    def parse_command_payload(message: mqtt.MQTTMessage) -> dict[str, Any] | None:
        """Parse a JSON command payload from an MQTT message.

        Args:
            message: The received MQTT message.

        Returns:
            Parsed dictionary, or ``None`` if the payload is not valid JSON.
        """
        try:
            return json.loads(message.payload.decode("utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
