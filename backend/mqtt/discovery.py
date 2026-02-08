"""SmartNest device discovery consumer.

Subscribes to ``smartnest/discovery/announce`` and maintains an in-memory
registry of discovered devices.  Each device publishes a JSON discovery
payload on startup; this consumer validates, stores, and indexes them.

The registry is intentionally in-memory for Phase 2; database persistence
will be added in Phase 3 (backend API).

Discovery payload schema::

    {
        "device_id": "light_01",
        "name": "Living Room Light",
        "device_type": "smart_light",
        "capabilities": ["power", "brightness", "color_temp"],
        "topics": {
            "command": "smartnest/device/light_01/command",
            "state": "smartnest/device/light_01/state",
        },
    }

Usage::

    consumer = DiscoveryConsumer(client)
    consumer.start()
    # ... devices publish discovery messages ...
    devices = consumer.get_discovered_devices()
    consumer.stop()
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.logging import MessageCode, get_logger, log_with_code
from backend.mqtt.topics import TopicBuilder, validate_device_id

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

    from backend.mqtt.client import SmartNestMQTTClient

logger = get_logger(__name__)


class DeviceDiscoveryMessage(BaseModel):
    """Validated discovery payload from a device announcement.

    Attributes:
        device_id: Unique device identifier.
        name: Human-readable device name.
        device_type: Device category (e.g. ``"smart_light"``).
        capabilities: List of supported capabilities.
        topics: MQTT topic map (at minimum ``command``).
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    device_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    topics: dict[str, str] = Field(default_factory=dict)

    @field_validator("device_id")
    @classmethod
    def _validate_device_id(cls, v: str) -> str:
        """Ensure device_id is valid for MQTT topics."""
        validate_device_id(v)
        return v


class DiscoveryConsumer:
    """Subscribes to discovery announcements and maintains a device registry.

    Thread-safe: the internal registry is protected by a lock so that
    concurrent MQTT callbacks and reader threads do not conflict.

    Args:
        client: A connected :class:`SmartNestMQTTClient` instance.

    Example::

        consumer = DiscoveryConsumer(client)
        consumer.start()
        devices = consumer.get_discovered_devices()
    """

    def __init__(self, client: SmartNestMQTTClient) -> None:
        self._client = client
        self._registry: dict[str, DeviceDiscoveryMessage] = {}
        self._lock = threading.Lock()
        self._started = False

    # -- Properties ------------------------------------------------------------

    @property
    def device_count(self) -> int:
        """Return the number of discovered devices."""
        with self._lock:
            return len(self._registry)

    # -- Lifecycle -------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to the discovery topic and begin processing announcements."""
        if self._started:
            return

        topic = TopicBuilder.discovery_topic()
        self._client.subscribe(topic)
        self._client.add_topic_handler(topic, self._on_discovery_message)
        self._started = True

    def stop(self) -> None:
        """Unsubscribe from the discovery topic."""
        if not self._started:
            return

        topic = TopicBuilder.discovery_topic()
        self._client.remove_topic_handler(topic)
        self._started = False

    # -- Registry access -------------------------------------------------------

    def get_discovered_devices(self) -> list[DeviceDiscoveryMessage]:
        """Return a list of all discovered devices.

        Returns:
            Snapshot of all registered devices (safe to iterate).
        """
        with self._lock:
            return list(self._registry.values())

    def get_device(self, device_id: str) -> DeviceDiscoveryMessage | None:
        """Look up a device by its identifier.

        Args:
            device_id: The device identifier to look up.

        Returns:
            The discovery message, or ``None`` if not found.
        """
        with self._lock:
            device = self._registry.get(device_id)

        if device is None:
            log_with_code(
                logger,
                "debug",
                MessageCode.DEVICE_NOT_FOUND,
                device_id=device_id,
            )

        return device

    # -- MQTT callback ---------------------------------------------------------

    def _on_discovery_message(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Handle an incoming discovery announcement.

        Validates the payload and registers the device.  Duplicate
        announcements for the same ``device_id`` update the existing
        entry.
        """
        try:
            raw = json.loads(message.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                "discovery_payload_invalid",
                error="Failed to decode JSON",
                topic=message.topic,
            )
            return

        self._register_device(raw)

    def _register_device(self, raw: dict[str, Any]) -> None:
        """Validate and store a discovery payload.

        Args:
            raw: Raw dictionary from the MQTT message payload.
        """
        try:
            discovery_msg = DeviceDiscoveryMessage(**raw)
        except (ValueError, TypeError) as exc:
            device_id = raw.get("device_id", "unknown")
            log_with_code(
                logger,
                "warning",
                MessageCode.DEVICE_REGISTRATION_FAILED,
                device_id=str(device_id),
                error=str(exc),
            )
            return

        with self._lock:
            is_update = discovery_msg.device_id in self._registry
            self._registry[discovery_msg.device_id] = discovery_msg

        log_with_code(
            logger,
            "info",
            MessageCode.DEVICE_REGISTERED,
            device_id=discovery_msg.device_id,
            device_type=discovery_msg.device_type,
        )

        if is_update:
            logger.debug(
                "discovery_updated",
                device_id=discovery_msg.device_id,
            )
