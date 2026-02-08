"""Unit tests for SmartNest MQTT client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.client import ConnectFlags, DisconnectFlags
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.reasoncodes import ReasonCode

from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig


@pytest.fixture
def config() -> MQTTConfig:
    """Default test configuration."""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="test_client",
    )


@pytest.fixture
def mock_paho() -> MagicMock:
    """Mocked paho.mqtt.client.Client instance."""
    mock = MagicMock(spec=mqtt.Client)
    mock.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_SUCCESS)
    mock.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    return mock


@pytest.fixture
def client(config: MQTTConfig, mock_paho: MagicMock) -> SmartNestMQTTClient:
    """SmartNestMQTTClient with a mocked Paho client."""
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
        return SmartNestMQTTClient(config)


class TestClientInit:
    """Tests for SmartNestMQTTClient constructor."""

    def test_creates_paho_client_with_v2_api(self, config: MQTTConfig) -> None:
        with patch("backend.mqtt.client.mqtt.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            SmartNestMQTTClient(config)
            mock_cls.assert_called_once_with(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id="test_client",
            )

    def test_enables_paho_logger(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        mock_paho.enable_logger.assert_called_once()

    def test_sets_reconnect_delay(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        mock_paho.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=60)

    def test_sets_lwt(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        mock_paho.will_set.assert_called_once()
        call_kwargs = mock_paho.will_set.call_args
        assert "smartnest/system/event" in str(call_kwargs)

    def test_credentials_set_when_provided(self) -> None:
        cfg = MQTTConfig(username="admin", password="secret", client_id="auth_test")
        with patch("backend.mqtt.client.mqtt.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            SmartNestMQTTClient(cfg)
            mock_instance.username_pw_set.assert_called_once_with("admin", "secret")

    def test_no_credentials_when_none(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        mock_paho.username_pw_set.assert_not_called()


class TestClientProperties:
    """Tests for client properties."""

    def test_is_connected_initially_false(self, client: SmartNestMQTTClient) -> None:
        assert client.is_connected is False

    def test_set_connected_for_test_clears_state(self, client: SmartNestMQTTClient) -> None:
        client.set_connected_for_test()
        assert client.is_connected is True
        client.set_connected_for_test(connected=False)
        assert client.is_connected is False

    def test_config_returns_config(self, client: SmartNestMQTTClient, config: MQTTConfig) -> None:
        assert client.config is config


class TestClientConnect:
    """Tests for SmartNestMQTTClient.connect()."""

    def test_connect_calls_paho_connect(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        # Simulate CONNACK by setting connected during loop_start
        def set_connected(*_args: object, **_kwargs: object) -> None:
            client.set_connected_for_test()

        mock_paho.loop_start.side_effect = set_connected
        result = client.connect(timeout=1.0)
        assert result is True
        mock_paho.connect.assert_called_once_with("localhost", 1883, keepalive=60)
        mock_paho.loop_start.assert_called_once()

    def test_connect_timeout_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        result = client.connect(timeout=0.1)
        assert result is False

    def test_connect_os_error_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        mock_paho.connect.side_effect = OSError("Connection refused")
        result = client.connect(timeout=0.1)
        assert result is False


class TestClientDisconnect:
    """Tests for SmartNestMQTTClient.disconnect()."""

    def test_disconnect_stops_loop_and_disconnects(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        client.set_connected_for_test()
        client.disconnect()
        mock_paho.loop_stop.assert_called_once()
        mock_paho.disconnect.assert_called_once()
        assert client.is_connected is False


class TestClientPublish:
    """Tests for SmartNestMQTTClient.publish()."""

    def test_publish_when_connected(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        client.set_connected_for_test()
        result = client.publish("smartnest/test", {"key": "value"})
        assert result is True
        mock_paho.publish.assert_called_once_with(
            "smartnest/test", json.dumps({"key": "value"}), qos=1, retain=False
        )

    def test_publish_when_not_connected_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        result = client.publish("smartnest/test", {"key": "value"})
        assert result is False
        mock_paho.publish.assert_not_called()

    def test_publish_with_custom_qos_and_retain(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        client.set_connected_for_test()
        client.publish("t", {"x": 1}, qos=0, retain=True)
        mock_paho.publish.assert_called_once_with("t", json.dumps({"x": 1}), qos=0, retain=True)

    def test_publish_failure_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        client.set_connected_for_test()
        mock_paho.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_NO_CONN)
        result = client.publish("t", {"x": 1})
        assert result is False


class TestClientSubscribe:
    """Tests for SmartNestMQTTClient.subscribe()."""

    def test_subscribe_when_connected(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        client.set_connected_for_test()
        result = client.subscribe("smartnest/device/+/state", qos=1)
        assert result is True

    def test_subscribe_when_not_connected(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        result = client.subscribe("smartnest/device/+/state")
        assert result is False

    def test_subscribe_failure_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        client.set_connected_for_test()
        mock_paho.subscribe.return_value = (mqtt.MQTT_ERR_NO_CONN, None)
        result = client.subscribe("t")
        assert result is False


class TestClientTopicHandlers:
    """Tests for add/remove topic handler methods."""

    def test_add_topic_handler(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        handler = MagicMock()
        client.add_topic_handler("smartnest/device/+/state", handler)
        mock_paho.message_callback_add.assert_called_once_with("smartnest/device/+/state", handler)

    def test_remove_topic_handler(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        client.remove_topic_handler("smartnest/device/+/state")
        mock_paho.message_callback_remove.assert_called_once_with("smartnest/device/+/state")


class TestClientConvenienceMethods:
    """Tests for publish_device_state() and publish_sensor_data()."""

    def test_publish_device_state(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        client.set_connected_for_test()
        result = client.publish_device_state("light_01", {"power": "on"})
        assert result is True
        call_args = mock_paho.publish.call_args
        assert call_args[0][0] == "smartnest/device/light_01/state"
        payload = json.loads(call_args[0][1])
        assert payload["power"] == "on"
        assert "timestamp" in payload
        assert call_args[1]["qos"] == 1
        assert call_args[1]["retain"] is True

    def test_publish_sensor_data(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        client.set_connected_for_test()
        result = client.publish_sensor_data("temp_01", {"value": 21.5})
        assert result is True
        call_args = mock_paho.publish.call_args
        assert call_args[0][0] == "smartnest/sensor/temp_01/data"
        payload = json.loads(call_args[0][1])
        assert payload["value"] == 21.5
        assert "timestamp" in payload
        assert call_args[1]["qos"] == 0
        assert call_args[1]["retain"] is False


class TestClientCallbacks:
    """Tests for Paho callback handling via assigned on_* attributes."""

    def test_on_connect_success_sets_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        on_connect = mock_paho.on_connect
        reason = ReasonCode(mqtt.CONNACK >> 4, identifier=0)
        on_connect(mock_paho, None, MagicMock(spec=ConnectFlags), reason, None)
        assert snc.is_connected is True

    def test_on_connect_failure_clears_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()
        on_connect = mock_paho.on_connect
        reason = ReasonCode(mqtt.CONNACK >> 4, identifier=0x87)
        on_connect(mock_paho, None, MagicMock(spec=ConnectFlags), reason, None)
        assert snc.is_connected is False

    def test_on_disconnect_clears_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()
        on_disconnect = mock_paho.on_disconnect
        reason = ReasonCode(mqtt.DISCONNECT >> 4, identifier=0)
        on_disconnect(mock_paho, None, MagicMock(spec=DisconnectFlags), reason, None)
        assert snc.is_connected is False

    def test_on_unexpected_disconnect_clears_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()
        on_disconnect = mock_paho.on_disconnect
        reason = ReasonCode(mqtt.DISCONNECT >> 4, identifier=0x8E)
        on_disconnect(mock_paho, None, MagicMock(spec=DisconnectFlags), reason, None)
        assert snc.is_connected is False

    def test_on_message_logs_unhandled(self, mock_paho: MagicMock, config: MQTTConfig) -> None:
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            SmartNestMQTTClient(config)
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.topic = "smartnest/test"
        msg.qos = 0
        msg.retain = False
        msg.payload = b'{"test": true}'
        on_message = mock_paho.on_message
        on_message(mock_paho, None, msg)
