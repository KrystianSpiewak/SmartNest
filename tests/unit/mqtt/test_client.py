"""Unit tests for SmartNest MQTT client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.client import ConnectFlags, DisconnectFlags
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.reasoncodes import ReasonCode

from backend.logging.catalog import MessageCode
from backend.mqtt.client import SmartNestMQTTClient, logger
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
        """LWT must be configured with correct topic, payload, QoS, and retain settings."""
        mock_paho.will_set.assert_called_once()
        call_args = mock_paho.will_set.call_args

        # Verify topic
        assert call_args.kwargs["topic"] == "smartnest/system/event"

        # Verify payload structure
        payload_str = call_args.kwargs["payload"]
        payload = json.loads(payload_str)
        assert payload["event"] == "client_offline"
        assert payload["client_id"] == "test_client"

        # Verify MQTT parameters for reliable LWT delivery
        assert call_args.kwargs["qos"] == 1  # QoS 1 ensures LWT delivery
        assert call_args.kwargs["retain"] is False  # LWT should not be retained

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

    def test_lwt_constants_match_schema(self) -> None:
        """LWT event type constants must match system event schema."""
        from backend.mqtt.client import (  # noqa: PLC0415
            LWT_CLIENT_ID_KEY,
            LWT_EVENT_KEY,
            LWT_EVENT_TYPE,
        )

        # Verify constants have expected values
        assert LWT_EVENT_TYPE == "client_offline"
        assert LWT_EVENT_KEY == "event"
        assert LWT_CLIENT_ID_KEY == "client_id"


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
        """Connection attempt must log broker, port, and client_id for traceability."""

        # Simulate CONNACK by setting connected during loop_start
        def set_connected(*_args: object, **_kwargs: object) -> None:
            client.set_connected_for_test()

        mock_paho.loop_start.side_effect = set_connected

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            result = client.connect(timeout=1.0)

            # Verify log_with_code was called with exact connection details
            mock_log.assert_any_call(
                logger,
                "info",
                MessageCode.MQTT_CONNECTION_INITIATED,
                broker="localhost",
                port=1883,
                client_id="test_client",
            )

        assert result is True
        mock_paho.connect.assert_called_once_with("localhost", 1883, keepalive=60)
        mock_paho.loop_start.assert_called_once()

    def test_connect_timeout_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Connection timeout must log timeout value for troubleshooting."""
        with patch("backend.mqtt.client.log_with_code") as mock_log:
            result = client.connect(timeout=0.1)

            # Verify timeout was logged with exact timeout value
            mock_log.assert_any_call(
                logger,
                "error",
                MessageCode.MQTT_CONNECTION_TIMEOUT,
                timeout=0.1,
            )

        assert result is False

    def test_connect_os_error_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """OSError during connect must be logged and return False."""
        mock_paho.connect.side_effect = OSError("Connection refused")

        with patch("backend.mqtt.client.logger.exception") as mock_exception:
            result = client.connect(timeout=0.1)

            # Verify exception was logged
            mock_exception.assert_called_once()

        assert result is False
        mock_paho.loop_start.assert_not_called()

    def test_connect_handles_logging_exception(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """OSError during connect must handle logging exceptions gracefully."""
        mock_paho.connect.side_effect = OSError("Connection refused")

        # Make logger.exception raise ValueError to test exception handler
        with patch(
            "backend.mqtt.client.logger.exception", side_effect=ValueError("Logging failed")
        ):
            result = client.connect(timeout=0.1)

        # Should still return False despite logging error
        assert result is False
        mock_paho.loop_start.assert_not_called()


class TestClientDisconnect:
    """Tests for SmartNestMQTTClient.disconnect()."""

    def test_disconnect_stops_loop_and_disconnects(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Disconnect must log disconnect event for traceability."""
        client.set_connected_for_test()

        with patch("backend.mqtt.client.logger.info") as mock_info:
            client.disconnect()

            # Verify disconnect was logged with exact message
            mock_info.assert_called_once_with("disconnecting")

        mock_paho.loop_stop.assert_called_once()
        mock_paho.disconnect.assert_called_once()
        assert client.is_connected is False

    def test_disconnect_handles_logging_exception(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Disconnect must handle logging exceptions gracefully."""
        client.set_connected_for_test()

        # Make logger.info raise OSError to test exception handler
        with patch("backend.mqtt.client.logger.info", side_effect=OSError("Logging failed")):
            client.disconnect()

        # Should still complete disconnect despite logging error
        mock_paho.loop_stop.assert_called_once()
        mock_paho.disconnect.assert_called_once()
        assert client.is_connected is False


class TestClientPublish:
    """Tests for SmartNestMQTTClient.publish()."""

    def test_publish_when_connected(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Publish success must log topic, QoS, and retain for debugging."""
        client.set_connected_for_test()

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            result = client.publish("smartnest/test", {"key": "value"})

            # Verify publish success logged with exact parameters
            mock_log.assert_any_call(
                logger,
                "debug",
                MessageCode.MQTT_PUBLISH_SUCCESS,
                topic="smartnest/test",
                qos=1,
                retain=False,
            )

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
        """Publish failure must log topic and error code for debugging."""
        client.set_connected_for_test()
        mock_paho.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_NO_CONN)

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            result = client.publish("t", {"x": 1})

            # Verify publish failure logged with exact parameters
            mock_log.assert_any_call(
                logger,
                "error",
                MessageCode.MQTT_PUBLISH_FAILED,
                topic="t",
                rc=mqtt.MQTT_ERR_NO_CONN,
            )

        assert result is False


class TestClientSubscribe:
    """Tests for SmartNestMQTTClient.subscribe()."""

    def test_subscribe_when_connected(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Successful subscription must log topic and QoS."""
        client.set_connected_for_test()
        mock_paho.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            result = client.subscribe("smartnest/device/+/state", qos=1)

            assert result is True
            mock_paho.subscribe.assert_called_once_with("smartnest/device/+/state", qos=1)

            # Verify subscription success logged with exact parameters
            mock_log.assert_called_once_with(
                logger,
                "info",
                MessageCode.MQTT_SUBSCRIBE_SUCCESS,
                topic="smartnest/device/+/state",
                qos=1,
            )

    def test_subscribe_when_not_connected(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Subscribe when not connected must return False."""
        result = client.subscribe("smartnest/device/+/state")
        assert result is False
        mock_paho.subscribe.assert_not_called()

    def test_subscribe_failure_returns_false(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Failed subscription must log error with reason code."""
        client.set_connected_for_test()
        mock_paho.subscribe.return_value = (mqtt.MQTT_ERR_NO_CONN, None)

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            result = client.subscribe("t")

            assert result is False

            # Verify subscription failure logged with exact parameters
            mock_log.assert_called_once_with(
                logger,
                "error",
                MessageCode.MQTT_SUBSCRIBE_FAILED,
                topic="t",
                rc=mqtt.MQTT_ERR_NO_CONN,
            )

    def test_subscribe_default_qos(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        """Subscribe must use QoS 1 by default."""
        client.set_connected_for_test()
        mock_paho.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)

        client.subscribe("test/topic")  # No qos parameter

        mock_paho.subscribe.assert_called_once_with("test/topic", qos=1)


class TestClientTopicHandlers:
    """Tests for add/remove topic handler methods."""

    def test_add_topic_handler(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        handler = MagicMock()
        client.add_topic_handler("smartnest/device/+/state", handler)
        mock_paho.message_callback_add.assert_called_once_with("smartnest/device/+/state", handler)

    def test_add_topic_handler_logs_topic_filter(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Verify the topic filter is passed to logging when registering a handler."""
        handler = MagicMock()

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            client.add_topic_handler("smartnest/sensor/+/data", handler)

            # Verify log_with_code was called with topic_filter parameter
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["topic_filter"] == "smartnest/sensor/+/data"

    def test_remove_topic_handler(self, client: SmartNestMQTTClient, mock_paho: MagicMock) -> None:
        client.remove_topic_handler("smartnest/device/+/state")
        mock_paho.message_callback_remove.assert_called_once_with("smartnest/device/+/state")

    def test_remove_topic_handler_logs_topic_filter(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Verify the topic filter is passed to logging when removing a handler."""
        with patch("backend.mqtt.client.log_with_code") as mock_log:
            client.remove_topic_handler("smartnest/system/+")

            # Verify log_with_code was called with topic_filter parameter
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["topic_filter"] == "smartnest/system/+"


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

    def test_publish_device_state_timestamp_is_valid(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Verify timestamp is a valid float, not None."""
        client.set_connected_for_test()
        client.publish_device_state("light_01", {"power": "on"})
        call_args = mock_paho.publish.call_args
        payload = json.loads(call_args[0][1])
        assert payload["timestamp"] is not None
        assert isinstance(payload["timestamp"], float)
        assert payload["timestamp"] > 0

    def test_publish_device_state_calls_publish_with_explicit_params(
        self, client: SmartNestMQTTClient
    ) -> None:
        """Verify publish_device_state passes explicit qos and retain parameters."""
        client.set_connected_for_test()
        with patch.object(client, "publish", return_value=True) as mock_publish:
            client.publish_device_state("light_01", {"power": "on"})
            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args[1]
            assert call_kwargs["qos"] == 1
            assert call_kwargs["retain"] is True

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

    def test_publish_sensor_data_timestamp_is_valid(
        self, client: SmartNestMQTTClient, mock_paho: MagicMock
    ) -> None:
        """Verify timestamp is a valid float, not None."""
        client.set_connected_for_test()
        client.publish_sensor_data("temp_01", {"value": 21.5})
        call_args = mock_paho.publish.call_args
        payload = json.loads(call_args[0][1])
        assert payload["timestamp"] is not None
        assert isinstance(payload["timestamp"], float)
        assert payload["timestamp"] > 0

    def test_publish_sensor_data_calls_publish_with_explicit_params(
        self, client: SmartNestMQTTClient
    ) -> None:
        """Verify publish_sensor_data passes explicit qos and retain parameters."""
        client.set_connected_for_test()
        with patch.object(client, "publish", return_value=True) as mock_publish:
            client.publish_sensor_data("temp_01", {"value": 21.5})
            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args[1]
            assert call_kwargs["qos"] == 0
            assert call_kwargs["retain"] is False


class TestClientCallbacks:
    """Tests for Paho callback handling via assigned on_* attributes."""

    def test_on_connect_success_sets_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        """Connection success must log broker, port, and client_id for observability."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            on_connect = mock_paho.on_connect
            reason = ReasonCode(mqtt.CONNACK >> 4, identifier=0)
            on_connect(mock_paho, None, MagicMock(spec=ConnectFlags), reason, None)

            # Verify connection success logged with exact parameters
            mock_log.assert_called_once_with(
                logger,
                "info",
                MessageCode.MQTT_CONNECTION_SUCCESS,
                broker="localhost",
                port=1883,
                client_id="test_client",
            )

        assert snc.is_connected is True

    def test_on_connect_failure_clears_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        """Connection failure must log reason code for troubleshooting."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()

        with patch("backend.mqtt.client.logger.error") as mock_error:
            on_connect = mock_paho.on_connect
            reason = ReasonCode(mqtt.CONNACK >> 4, identifier=0x87)
            on_connect(mock_paho, None, MagicMock(spec=ConnectFlags), reason, None)

            # Verify connection refused was logged with reason code
            mock_error.assert_called_once_with("connection_refused", reason_code=str(reason))

        assert snc.is_connected is False

    def test_on_disconnect_clears_connected(self, mock_paho: MagicMock, config: MQTTConfig) -> None:
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()
        on_disconnect = mock_paho.on_disconnect
        reason = ReasonCode(mqtt.DISCONNECT >> 4, identifier=0)
        on_disconnect(mock_paho, None, MagicMock(spec=DisconnectFlags), reason, None)
        assert snc.is_connected is False

    def test_on_connect_failure_handles_logging_exception(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        """Connection failure path must handle logging exceptions gracefully."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()

        # Make logger.error raise OSError to test exception handler
        with patch("backend.mqtt.client.logger.error", side_effect=OSError("Logging failed")):
            on_connect = mock_paho.on_connect
            reason = ReasonCode(mqtt.CONNACK >> 4, identifier=0x87)
            on_connect(mock_paho, None, MagicMock(spec=ConnectFlags), reason, None)

        # State should still be cleared despite logging error
        assert snc.is_connected is False

    def test_on_unexpected_disconnect_clears_connected(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        """Unexpected disconnect must log reason code for incident response."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            on_disconnect = mock_paho.on_disconnect
            reason = ReasonCode(mqtt.DISCONNECT >> 4, identifier=0x8E)
            on_disconnect(mock_paho, None, MagicMock(spec=DisconnectFlags), reason, None)

            # Verify unexpected disconnect logged with exact reason
            mock_log.assert_called_once_with(
                logger,
                "warning",
                MessageCode.MQTT_DISCONNECTED_UNEXPECTED,
                reason=str(reason),
            )

        assert snc.is_connected is False

    def test_on_disconnect_clean_logs_info_level(
        self, mock_paho: MagicMock, config: MQTTConfig
    ) -> None:
        """Clean disconnect (reason_code=0) must log at INFO, not WARNING."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            snc = SmartNestMQTTClient(config)
        snc.set_connected_for_test()

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            on_disconnect = mock_paho.on_disconnect
            reason = ReasonCode(mqtt.DISCONNECT >> 4, identifier=0)  # 0 = clean
            on_disconnect(mock_paho, None, MagicMock(spec=DisconnectFlags), reason, None)

            # Verify clean disconnect logged at INFO level, not WARNING
            mock_log.assert_called_once_with(
                logger,
                "info",  # Not "warning"
                MessageCode.MQTT_DISCONNECTED_CLEAN,
            )

        assert snc.is_connected is False

    def test_on_message_logs_unhandled(self, mock_paho: MagicMock, config: MQTTConfig) -> None:
        """Unhandled messages must log topic, QoS, retain, and payload for debugging."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            SmartNestMQTTClient(config)

        with patch("backend.mqtt.client.log_with_code") as mock_log:
            msg = MagicMock(spec=mqtt.MQTTMessage)
            msg.topic = "smartnest/test"
            msg.qos = 0
            msg.retain = False
            msg.payload = b'{"test": true}'
            on_message = mock_paho.on_message
            on_message(mock_paho, None, msg)

            # Verify unhandled message logged with exact parameters
            mock_log.assert_called_once_with(
                logger,
                "debug",
                MessageCode.MQTT_MESSAGE_UNHANDLED,
                topic="smartnest/test",
                qos=0,
                retain=False,
                payload='{"test": true}',
            )
