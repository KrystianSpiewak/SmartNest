"""Integration test: SmartNest MQTT client against live broker.

Requires a running HiveMQ broker on localhost:1883.
Skips automatically when the broker is unavailable.

Run with:
    npm run test -- -m integration
"""

from __future__ import annotations

import json
import socket
import time
from typing import TYPE_CHECKING, Any

import pytest

from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    from collections.abc import Generator

    import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883


def _broker_available() -> bool:
    """Check if the MQTT broker is reachable."""
    try:
        with socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _broker_available(),
    reason=f"MQTT broker not reachable at {BROKER_HOST}:{BROKER_PORT}",
)


@pytest.fixture
def mqtt_client() -> Generator[SmartNestMQTTClient]:
    """Create and connect a SmartNest MQTT client for testing."""
    config = MQTTConfig(
        broker=BROKER_HOST,
        port=BROKER_PORT,
        client_id=f"integration_test_{int(time.time())}",
    )
    client = SmartNestMQTTClient(config)
    yield client
    client.disconnect()


class TestBrokerIntegration:
    """Integration tests against a live MQTT broker."""

    def test_connect_and_disconnect(self, mqtt_client: SmartNestMQTTClient) -> None:
        """Verify basic connect/disconnect lifecycle."""
        assert mqtt_client.connect(timeout=5.0)
        assert mqtt_client.is_connected
        mqtt_client.disconnect()
        assert not mqtt_client.is_connected

    def test_publish_and_receive(self, mqtt_client: SmartNestMQTTClient) -> None:
        """Publish a message and verify it arrives via subscription."""
        assert mqtt_client.connect(timeout=5.0)

        received: list[dict[str, Any]] = []

        def handler(
            _client: mqtt.Client,
            _userdata: object,
            message: mqtt.MQTTMessage,
        ) -> None:
            payload = json.loads(message.payload.decode("utf-8"))
            received.append(payload)

        topic = TopicBuilder.device_topic("integ_test_01", "state")
        mqtt_client.add_topic_handler(
            TopicBuilder.device_wildcard("state"),
            handler,
        )
        mqtt_client.subscribe(TopicBuilder.device_wildcard("state"))

        # Allow subscription to propagate
        time.sleep(0.5)

        test_payload = {"power": "on", "source": "integration_test"}
        mqtt_client.publish(topic, test_payload, qos=1, retain=False)

        # Wait for our specific message (ignore stale retained messages)
        deadline = time.time() + 5.0
        matching: list[dict[str, Any]] = []
        while not matching and time.time() < deadline:
            time.sleep(0.1)
            matching = [m for m in received if m.get("source") == "integration_test"]

        assert len(matching) >= 1
        assert matching[0]["power"] == "on"

    def test_publish_device_state_convenience(self, mqtt_client: SmartNestMQTTClient) -> None:
        """Verify publish_device_state() convenience method."""
        assert mqtt_client.connect(timeout=5.0)

        received: list[dict[str, Any]] = []

        def handler(
            _client: mqtt.Client,
            _userdata: object,
            message: mqtt.MQTTMessage,
        ) -> None:
            received.append(json.loads(message.payload.decode("utf-8")))

        mqtt_client.add_topic_handler(TopicBuilder.device_wildcard("state"), handler)
        mqtt_client.subscribe(TopicBuilder.device_wildcard("state"))
        time.sleep(0.5)

        mqtt_client.publish_device_state("integ_light", {"brightness": 75})

        # Wait for our specific message (ignore stale retained messages)
        deadline = time.time() + 5.0
        matching: list[dict[str, Any]] = []
        while not matching and time.time() < deadline:
            time.sleep(0.1)
            matching = [m for m in received if m.get("brightness") == 75]

        assert len(matching) >= 1
        assert "timestamp" in matching[0]

    def test_sensor_data_convenience(self, mqtt_client: SmartNestMQTTClient) -> None:
        """Verify publish_sensor_data() convenience method."""
        assert mqtt_client.connect(timeout=5.0)

        received: list[dict[str, Any]] = []

        def handler(
            _client: mqtt.Client,
            _userdata: object,
            message: mqtt.MQTTMessage,
        ) -> None:
            received.append(json.loads(message.payload.decode("utf-8")))

        mqtt_client.add_topic_handler(TopicBuilder.sensor_wildcard(), handler)
        mqtt_client.subscribe(TopicBuilder.sensor_wildcard())
        time.sleep(0.5)

        mqtt_client.publish_sensor_data("integ_temp", {"value": 22.3, "unit": "celsius"})

        deadline = time.time() + 5.0
        while not received and time.time() < deadline:
            time.sleep(0.1)

        assert len(received) >= 1
        assert received[0]["value"] == 22.3
        assert received[0]["unit"] == "celsius"
