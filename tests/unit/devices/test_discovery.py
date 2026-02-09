"""Unit tests for DiscoveryConsumer and DeviceDiscoveryMessage."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest
from pydantic import ValidationError

from backend.logging.catalog import MessageCode
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig
from backend.mqtt.discovery import DeviceDiscoveryMessage, DiscoveryConsumer

# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def config() -> MQTTConfig:
    """Default test configuration."""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="smartnest_discovery",
    )


@pytest.fixture
def mock_paho() -> MagicMock:
    """Mocked paho.mqtt.client.Client instance."""
    mock = MagicMock(spec=mqtt.Client)
    mock.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_SUCCESS)
    mock.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    return mock


@pytest.fixture
def mqtt_client(config: MQTTConfig, mock_paho: MagicMock) -> SmartNestMQTTClient:
    """SmartNestMQTTClient with mocked Paho client."""
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
        client = SmartNestMQTTClient(config)
    return client


@pytest.fixture
def consumer(mqtt_client: MagicMock) -> DiscoveryConsumer:
    """DiscoveryConsumer with mocked MQTT client."""
    return DiscoveryConsumer(mqtt_client)


def _make_discovery_message(payload: dict[str, Any]) -> MagicMock:
    """Create a mock discovery MQTT message."""
    msg = MagicMock(spec=mqtt.MQTTMessage)
    msg.payload = json.dumps(payload).encode("utf-8")
    msg.topic = "smartnest/discovery/announce"
    return msg


def _valid_payload(device_id: str = "light_01") -> dict[str, Any]:
    """Return a minimal valid discovery payload."""
    return {
        "device_id": device_id,
        "name": "Test Device",
        "device_type": "smart_light",
        "capabilities": ["power", "brightness"],
        "topics": {
            "command": f"smartnest/device/{device_id}/command",
            "state": f"smartnest/device/{device_id}/state",
        },
    }


# -- Tests: DeviceDiscoveryMessage model ---------------------------------------


class TestDeviceDiscoveryMessageModel:
    """Tests for Pydantic validation of DeviceDiscoveryMessage."""

    def test_valid_payload(self) -> None:
        """Valid payload creates model successfully."""
        msg = DeviceDiscoveryMessage(**_valid_payload())
        assert msg.device_id == "light_01"
        assert msg.name == "Test Device"
        assert msg.device_type == "smart_light"
        assert msg.capabilities == ["power", "brightness"]

    def test_frozen_model(self) -> None:
        """Model is frozen (immutable)."""
        msg = DeviceDiscoveryMessage(**_valid_payload())
        with pytest.raises(ValidationError):
            msg.device_id = "new_id"

    def test_extra_fields_allowed(self) -> None:
        """Extra fields are accepted and accessible."""
        payload: dict[str, Any] = {**_valid_payload(), "firmware": "1.0.0"}
        msg = DeviceDiscoveryMessage(**payload)
        assert msg.firmware == "1.0.0"  # type: ignore[attr-defined]

    def test_empty_device_id_rejected(self) -> None:
        """Empty device_id fails validation."""
        payload: dict[str, Any] = {**_valid_payload(), "device_id": ""}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_whitespace_device_id_rejected(self) -> None:
        """Whitespace-only device_id fails validation (via validate_device_id)."""
        payload: dict[str, Any] = {**_valid_payload(), "device_id": "   "}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_device_id_with_wildcard_rejected(self) -> None:
        """Device ID containing MQTT wildcard is rejected."""
        payload: dict[str, Any] = {**_valid_payload(), "device_id": "light+01"}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_device_id_with_hash_rejected(self) -> None:
        """Device ID containing '#' is rejected."""
        payload: dict[str, Any] = {**_valid_payload(), "device_id": "light#01"}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_device_id_with_slash_rejected(self) -> None:
        """Device ID containing '/' is rejected."""
        payload: dict[str, Any] = {**_valid_payload(), "device_id": "light/01"}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_empty_name_rejected(self) -> None:
        """Empty name fails validation."""
        payload: dict[str, Any] = {**_valid_payload(), "name": ""}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_empty_device_type_rejected(self) -> None:
        """Empty device_type fails validation."""
        payload: dict[str, Any] = {**_valid_payload(), "device_type": ""}
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_missing_device_id_rejected(self) -> None:
        """Missing device_id field fails validation."""
        payload = _valid_payload()
        del payload["device_id"]
        with pytest.raises(ValidationError):
            DeviceDiscoveryMessage(**payload)

    def test_default_capabilities(self) -> None:
        """Capabilities defaults to empty list."""
        payload = _valid_payload()
        del payload["capabilities"]
        msg = DeviceDiscoveryMessage(**payload)
        assert msg.capabilities == []

    def test_default_topics(self) -> None:
        """Topics defaults to empty dict."""
        payload = _valid_payload()
        del payload["topics"]
        msg = DeviceDiscoveryMessage(**payload)
        assert msg.topics == {}


# -- Tests: Consumer lifecycle -------------------------------------------------


class TestDiscoveryConsumerLifecycle:
    """Tests for start() and stop() lifecycle."""

    def test_start_subscribes(self, consumer: DiscoveryConsumer) -> None:
        """start() subscribes to the discovery topic."""
        with patch.object(consumer._client, "subscribe") as mock_sub:
            consumer.start()
            mock_sub.assert_called_once_with("smartnest/discovery/announce")

    def test_start_adds_handler(self, consumer: DiscoveryConsumer) -> None:
        """start() adds topic handler for discovery topic."""
        with patch.object(consumer._client, "add_topic_handler") as mock_add:
            consumer.start()
            mock_add.assert_called_once_with(
                "smartnest/discovery/announce",
                consumer._on_discovery_message,
            )

    def test_start_idempotent(self, consumer: DiscoveryConsumer) -> None:
        """Calling start() twice does not duplicate subscriptions."""
        with (
            patch.object(consumer._client, "subscribe") as mock_sub,
            patch.object(consumer._client, "add_topic_handler"),
        ):
            consumer.start()
            consumer.start()  # second call should be a no-op
            mock_sub.assert_called_once()

    def test_stop_removes_handler(self, consumer: DiscoveryConsumer) -> None:
        """stop() removes the topic handler."""
        with (
            patch.object(consumer._client, "subscribe"),
            patch.object(consumer._client, "add_topic_handler"),
        ):
            consumer.start()
        with patch.object(consumer._client, "remove_topic_handler") as mock_rm:
            consumer.stop()
            mock_rm.assert_called_once_with("smartnest/discovery/announce")

    def test_stop_idempotent(self, consumer: DiscoveryConsumer) -> None:
        """Calling stop() without start() is a no-op."""
        with patch.object(consumer._client, "remove_topic_handler") as mock_rm:
            consumer.stop()
            mock_rm.assert_not_called()


# -- Tests: Registry access ----------------------------------------------------


class TestDiscoveryConsumerRegistry:
    """Tests for device registry operations."""

    def test_initially_empty(self, consumer: DiscoveryConsumer) -> None:
        """Registry starts empty."""
        assert consumer.get_discovered_devices() == []
        assert consumer.device_count == 0

    def test_register_device(self, consumer: DiscoveryConsumer) -> None:
        """_register_device() adds device to registry."""
        consumer._register_device(_valid_payload())
        assert consumer.device_count == 1

    def test_get_discovered_devices(self, consumer: DiscoveryConsumer) -> None:
        """get_discovered_devices() returns all registered devices."""
        consumer._register_device(_valid_payload("light_01"))
        consumer._register_device(_valid_payload("light_02"))
        devices = consumer.get_discovered_devices()
        assert len(devices) == 2

    def test_get_device_found(self, consumer: DiscoveryConsumer) -> None:
        """get_device() returns device when found."""
        consumer._register_device(_valid_payload())
        device = consumer.get_device("light_01")
        assert device is not None
        assert device.device_id == "light_01"

    def test_get_device_not_found(self, consumer: DiscoveryConsumer) -> None:
        """get_device() returns None when not found."""
        device = consumer.get_device("nonexistent")
        assert device is None

    def test_get_device_not_found_logs_debug(self, consumer: DiscoveryConsumer) -> None:
        """get_device() must log DEVICE_NOT_FOUND with exact device_id."""
        with patch("backend.mqtt.discovery.log_with_code") as mock_log:
            consumer.get_device("nonexistent")
            not_found_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_NOT_FOUND
            ]
            assert len(not_found_calls) == 1
            call = not_found_calls[0]
            # Verify logger is not None and exact parameters
            assert call.args[0] is not None
            assert call.args[1] == "debug"
            assert call.kwargs["device_id"] == "nonexistent"  # Exact value

    def test_duplicate_announcement_updates_entry(self, consumer: DiscoveryConsumer) -> None:
        """Second announcement for same device_id updates the entry."""
        consumer._register_device(_valid_payload())
        updated_payload: dict[str, Any] = {**_valid_payload(), "name": "Updated Light"}
        with patch("backend.mqtt.discovery.logger"):
            consumer._register_device(updated_payload)
        assert consumer.device_count == 1
        device = consumer.get_device("light_01")
        assert device is not None
        assert device.name == "Updated Light"

    def test_get_discovered_devices_returns_snapshot(self, consumer: DiscoveryConsumer) -> None:
        """get_discovered_devices() returns a copy, not a reference."""
        consumer._register_device(_valid_payload())
        devices = consumer.get_discovered_devices()
        devices.clear()  # modifying the returned list
        assert consumer.device_count == 1  # original registry unchanged


# -- Tests: MQTT callback ------------------------------------------------------


class TestDiscoveryConsumerCallback:
    """Tests for _on_discovery_message() callback."""

    def test_valid_message_registers_device(self, consumer: DiscoveryConsumer) -> None:
        """Valid discovery message is registered."""
        msg = _make_discovery_message(_valid_payload())
        consumer._on_discovery_message(MagicMock(), None, msg)
        assert consumer.device_count == 1

    def test_invalid_json_logs_warning(self, consumer: DiscoveryConsumer) -> None:
        """Invalid JSON must log warning with exact error message."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"not-json"
        msg.topic = "smartnest/discovery/announce"
        with patch("backend.mqtt.discovery.logger") as mock_logger:
            consumer._on_discovery_message(MagicMock(), None, msg)
            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args.kwargs
            # Verify exact parameters - kills string and field mutations
            assert call_kwargs["error"] == "Failed to decode JSON"
            assert call_kwargs["topic"] == "smartnest/discovery/announce"
        assert consumer.device_count == 0

    def test_invalid_unicode_logs_warning(self, consumer: DiscoveryConsumer) -> None:
        """Invalid unicode must log warning with exact error message."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"\x80\x81\x82"
        msg.topic = "smartnest/discovery/announce"
        with patch("backend.mqtt.discovery.logger") as mock_logger:
            consumer._on_discovery_message(MagicMock(), None, msg)
            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args.kwargs
            # Verify exact parameters - kills string mutations
            assert call_kwargs["error"] == "Failed to decode JSON"
            assert call_kwargs["topic"] == "smartnest/discovery/announce"
        assert consumer.device_count == 0


# -- Tests: Registration validation -------------------------------------------


class TestDiscoveryConsumerRegistration:
    """Tests for _register_device() validation paths."""

    def test_invalid_payload_logs_failure(self, consumer: DiscoveryConsumer) -> None:
        """Invalid payload must log with exact logger, device_id, and error."""
        with patch("backend.mqtt.discovery.log_with_code") as mock_log:
            consumer._register_device({"device_id": "x"})  # missing name, type
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_REGISTRATION_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger is not None and exact parameters
            assert call.args[0] is not None
            assert call.args[1] == "warning"
            assert call.kwargs["device_id"] == "x"  # Exact device_id from payload
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None

    def test_valid_registration_logs_success(self, consumer: DiscoveryConsumer) -> None:
        """Device registration must log with exact logger and parameters."""
        with patch("backend.mqtt.discovery.log_with_code") as mock_log:
            consumer._register_device(_valid_payload())
            registered_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_REGISTERED
            ]
            assert len(registered_calls) == 1
            call = registered_calls[0]
            # Verify logger is not None and exact parameters
            assert call.args[0] is not None
            assert call.args[1] == "info"
            assert call.kwargs["device_id"] == "light_01"  # Exact value
            assert call.kwargs["device_type"] == "smart_light"  # Exact value

    def test_update_registration_logs_debug(self, consumer: DiscoveryConsumer) -> None:
        """Updated registration must emit debug log with exact device_id."""
        consumer._register_device(_valid_payload())
        with patch("backend.mqtt.discovery.logger") as mock_logger:
            consumer._register_device({**_valid_payload(), "name": "Updated"})
            mock_logger.debug.assert_called_once()
            call_kwargs = mock_logger.debug.call_args.kwargs
            # Verify exact parameters - kills device_id=None mutation
            assert call_kwargs["device_id"] == "light_01"
            assert call_kwargs["device_id"] is not None

    def test_invalid_device_id_in_payload(self, consumer: DiscoveryConsumer) -> None:
        """Invalid device_id (wildcard) must log with exact device_id and error."""
        payload: dict[str, Any] = {**_valid_payload(), "device_id": "bad+id"}
        with patch("backend.mqtt.discovery.log_with_code") as mock_log:
            consumer._register_device(payload)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_REGISTRATION_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger is not None and exact parameters
            assert call.args[0] is not None
            assert call.args[1] == "warning"
            assert call.kwargs["device_id"] == "bad+id"  # Exact invalid device_id
            assert "error" in call.kwargs
        assert consumer.device_count == 0

    def test_non_dict_payload_raises(self, consumer: DiscoveryConsumer) -> None:
        """Non-dict raw data triggers registration failure."""
        with patch("backend.mqtt.discovery.log_with_code") as mock_log:
            consumer._register_device({"bad": True})
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_REGISTRATION_FAILED
            ]
            assert len(failed_calls) == 1
