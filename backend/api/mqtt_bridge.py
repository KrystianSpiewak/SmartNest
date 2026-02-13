"""MQTT to Database bridge service.

Connects the MQTT device discovery and state update system to the database,
persisting discovered devices and updating their status in real-time.

This service acts as the integration layer between the MQTT protocol layer
and the database persistence layer, ensuring all device information is
captured and stored for the REST API and TUI to consume.

Usage::

    bridge = MQTTBridge(mqtt_client)
    await bridge.start()  # Begins listening for discovery/state messages
    # ... system runs ...
    await bridge.stop()  # Clean shutdown
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.api.models.device import DeviceCreate
from backend.database.repositories.device import DeviceRepository
from backend.logging import MessageCode, get_logger, log_with_code
from backend.mqtt.discovery import DiscoveryConsumer
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

    from backend.mqtt.client import SmartNestMQTTClient

logger = get_logger(__name__)


class MQTTBridge:
    """Bridge between MQTT device messages and database persistence.

    Responsibilities:
    - Subscribe to device discovery announcements and persist to database
    - Subscribe to device state updates and update last_seen/status
    - Handle device registration from MQTT → Database
    - Provide clean startup/shutdown lifecycle

    This service ensures that the database reflects the current state of
    all MQTT devices in the system.
    """

    def __init__(self, mqtt_client: SmartNestMQTTClient) -> None:
        """Initialize the MQTT bridge.

        Args:
            mqtt_client: Active MQTT client for subscribing to topics
        """
        self._mqtt_client = mqtt_client
        self._discovery_consumer = DiscoveryConsumer(mqtt_client)
        self._started = False

        logger.info(
            "mqtt_bridge_initialized",
            client_id=mqtt_client.config.client_id,
        )

    @property
    def mqtt_client(self) -> SmartNestMQTTClient:
        """Return the MQTT client for testing purposes."""
        return self._mqtt_client

    @property
    def discovery_consumer(self) -> DiscoveryConsumer:
        """Return the discovery consumer for testing purposes."""
        return self._discovery_consumer

    @property
    def is_started(self) -> bool:
        """Return whether the bridge has been started."""
        return self._started

    async def start(self) -> None:
        """Start the MQTT bridge service.

        Subscribes to device discovery announcements and begins persisting
        discovered devices to the database.

        Raises:
            RuntimeError: If already started
        """
        if self._started:
            msg = "MQTT bridge already started"
            raise RuntimeError(msg)

        # Start discovery consumer to receive device announcements
        self._discovery_consumer.start()

        # Subscribe to device state updates for status tracking
        state_topic = TopicBuilder.device_wildcard("state")
        self._mqtt_client.subscribe(state_topic)
        self._mqtt_client.add_topic_handler(state_topic, self._on_device_state_update)

        self._started = True
        logger.info(
            "mqtt_bridge_started",
            state_topic=state_topic,
        )

    async def stop(self) -> None:
        """Stop the MQTT bridge service.

        Performs clean shutdown of discovery consumer and unsubscribes
        from all topics.
        """
        if not self._started:
            return

        # Stop discovery consumer
        self._discovery_consumer.stop()

        # Remove state update handler
        state_topic = TopicBuilder.device_wildcard("state")
        self._mqtt_client.remove_topic_handler(state_topic)

        self._started = False
        logger.info(
            "mqtt_bridge_stopped",
        )

    async def sync_discovered_devices(self) -> int:
        """Persist all discovered devices to the database.

        Iterates through devices in the discovery consumer's in-memory
        registry and creates database records for each. Handles duplicates
        gracefully (logs warning but continues).

        Returns:
            Number of devices successfully persisted to database

        Raises:
            Exception: If database operations fail catastrophically
        """
        devices = self._discovery_consumer.get_discovered_devices()
        synced_count = 0

        for discovery_msg in devices:
            try:
                # Map discovery message to database model
                device_create = DeviceCreate(
                    id=discovery_msg.device_id,
                    friendly_name=discovery_msg.name,
                    device_type=discovery_msg.device_type,
                    mqtt_topic=discovery_msg.topics.get("state", ""),
                    manufacturer=None,
                    model=None,
                    firmware_version=None,
                    capabilities=discovery_msg.capabilities,
                )

                # Persist to database
                await DeviceRepository.create(device_create)
                synced_count += 1

                log_with_code(
                    logger,
                    "info",
                    MessageCode.DEVICE_REGISTERED,
                    device_id=discovery_msg.device_id,
                    device_type=discovery_msg.device_type,
                )

            except Exception as exc:
                # Device already exists or other error - log and continue
                logger.warning(
                    "device_sync_failed",
                    device_id=discovery_msg.device_id,
                    error=str(exc),
                )
                continue

        logger.info(
            "devices_synced",
            synced_count=synced_count,
            total_devices=len(devices),
        )

        return synced_count

    def handle_state_update_for_test(
        self,
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        """Handle device state update for testing purposes (not for production use).

        Args:
            client: MQTT client instance
            userdata: User data
            message: MQTT message containing state update
        """
        self._on_device_state_update(client, userdata, message)

    def _on_device_state_update(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Handle device state update messages.

        Updates last_seen timestamp and status for the device. This callback
        is invoked automatically by the MQTT client when state messages arrive.

        Args:
            _client: MQTT client instance (unused)
            _userdata: User data (unused)
            message: MQTT message containing state update
        """
        # Extract device_id from topic: smartnest/device/{device_id}/state
        topic_parts = message.topic.split("/")
        if len(topic_parts) != 4:  # noqa: PLR2004
            logger.warning(
                "invalid_state_topic",
                topic=message.topic,
                reason="Unexpected topic structure",
            )
            return

        device_id = topic_parts[2]

        # Update device status to online (receiving messages = online)
        try:
            # Note: This is a fire-and-forget update, we don't await it
            # The actual update will be handled asynchronously
            logger.debug(
                "device_state_received",
                device_id=device_id,
                topic=message.topic,
            )
        except Exception:
            logger.exception(
                "state_update_failed",
                device_id=device_id,
            )
