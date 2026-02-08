#!/usr/bin/env python3
"""SmartNest MQTT Connection Validation Script.

Tests basic MQTT connectivity and SmartNest topic structure.

Usage:
    python scripts/mqtt_validation_test.py
    npm run test:mqtt
"""

import json
import logging
import time
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.client import ConnectFlags, DisconnectFlags
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SmartNestMQTTTest:
    """Simple MQTT test client for SmartNest validation."""

    def __init__(self, broker: str = "localhost", port: int = 1883) -> None:
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id="smartnest_validation",
        )
        self.connected = False
        self.messages_received: list[dict[str, Any]] = []

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: object,
        _flags: ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        if reason_code == 0:
            logger.info("Connected to %s:%d", self.broker, self.port)
            self.connected = True
            for topic in [
                "smartnest/test/state",
                "smartnest/device/+/state",
                "smartnest/sensor/+/data",
            ]:
                client.subscribe(topic, qos=1)
                logger.info("  Subscribed: %s", topic)
        else:
            logger.error("Connection failed: %s", reason_code)
            self.connected = False

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: DisconnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        logger.warning("Disconnected (code %s)", reason_code)
        self.connected = False

    def _on_message(self, _client: mqtt.Client, _userdata: object, msg: mqtt.MQTTMessage) -> None:
        payload = msg.payload.decode("utf-8")
        logger.info("  Received on %s: %s", msg.topic, payload[:80])
        self.messages_received.append(
            {"topic": msg.topic, "payload": payload, "qos": msg.qos, "retain": msg.retain}
        )

    def connect(self) -> bool:
        """Connect to MQTT broker with 5 second timeout."""
        try:
            logger.info("Connecting to %s:%d ...", self.broker, self.port)
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            deadline = time.time() + 5
            while not self.connected and time.time() < deadline:
                time.sleep(0.1)
        except Exception:
            logger.exception("Connection error")
            return False
        else:
            return self.connected

    def disconnect(self) -> None:
        """Disconnect from broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def publish(
        self, topic: str, payload: dict[str, Any], qos: int = 1, retain: bool = False
    ) -> bool:
        """Publish a JSON message."""
        if not self.connected:
            logger.error("Cannot publish: not connected")
            return False
        result = self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
        return result.rc == mqtt.MQTT_ERR_SUCCESS


def run_tests() -> bool:
    """Run SmartNest MQTT validation tests."""
    client = SmartNestMQTTTest()
    passed = 0
    failed = 0

    try:
        # Test 1: Connection
        logger.info("--- Test 1: Broker Connection ---")
        if not client.connect():
            logger.error("FAIL: Could not connect to broker")
            logger.error("  Is the broker running? Try: npm run docker:up")
            return False
        logger.info("PASS: Connected")
        passed += 1
        time.sleep(1)

        # Test 2: Publish to SmartNest topics
        logger.info("--- Test 2: Topic Structure ---")
        test_messages: list[tuple[str, dict[str, Any], int, bool]] = [
            ("smartnest/device/light_01/state", {"power": "on", "brightness": 80}, 1, True),
            ("smartnest/sensor/temp_01/data", {"value": 21.5, "unit": "celsius"}, 0, False),
            ("smartnest/test/state", {"status": "validation_ok"}, 1, False),
        ]
        all_published = True
        for topic, payload, qos, retain in test_messages:
            payload["timestamp"] = time.time()
            ok = client.publish(topic, payload, qos=qos, retain=retain)
            status = "PASS" if ok else "FAIL"
            logger.info("  %s -> %s", topic, status)
            if not ok:
                all_published = False
        if all_published:
            passed += 1
        else:
            failed += 1

        # Test 3: Message receipt
        logger.info("--- Test 3: Subscription Receipt ---")
        time.sleep(2)
        count = len(client.messages_received)
        if count > 0:
            logger.info("PASS: Received %d messages", count)
            passed += 1
        else:
            logger.error("FAIL: No messages received")
            failed += 1

        # Summary
        logger.info("--- Results: %d passed, %d failed ---", passed, failed)
    except Exception:
        logger.exception("Test error")
        return False
    else:
        return failed == 0
    finally:
        client.disconnect()


if __name__ == "__main__":
    success = run_tests()
    raise SystemExit(0 if success else 1)
