"""Unit tests for BaseDevice abstract class."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
import json
from typing import Any
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest
import structlog

from backend.devices.base import BaseDevice
from backend.logging.catalog import MessageCode
from backend.mqtt.config import MQTTConfig

# -- Concrete test implementation of BaseDevice --------------------------------


class _ConcreteDevice(BaseDevice):
    """Minimal concrete device for testing BaseDevice behaviour."""

    def __init__(
        self,
        *,
        device_id: str = "test_device",
        name: str = "Test Device",
        mqtt_config: MQTTConfig | None = None,
        on_start_hook: bool = False,
        on_stop_hook: bool = False,
    ) -> None:
        if mqtt_config is None:
            mqtt_config = MQTTConfig(
                broker="localhost", port=1883, client_id=f"smartnest_{device_id}"
            )
        self.start_hook_called = False
        self.stop_hook_called = False
        self._use_start_hook = on_start_hook
        self._use_stop_hook = on_stop_hook
        self.received_commands: list[dict[str, Any]] = []
        super().__init__(
            device_id=device_id,
            device_type="test_device",
            name=name,
            config=mqtt_config,
        )

    def _handle_command(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        payload = self.parse_command_payload(message)
        if payload is not None:
            self.received_commands.append(payload)

    def _get_discovery_payload(self) -> dict[str, Any]:
        return {
            "device_id": self._device_id,
            "name": self._name,
            "device_type": self._device_type,
            "capabilities": ["test"],
            "topics": {"command": f"smartnest/device/{self._device_id}/command"},
        }

    def _on_start(self) -> None:
        if self._use_start_hook:
            self.start_hook_called = True

    def _on_stop(self) -> None:
        if self._use_stop_hook:
            self.stop_hook_called = True


# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def device(mqtt_config: MQTTConfig, mock_paho_client: MagicMock) -> _ConcreteDevice:
    """Concrete device with mocked Paho client."""
    # Override client_id for device-specific identification
    device_config = MQTTConfig(
        broker=mqtt_config.broker,
        port=mqtt_config.port,
        client_id="smartnest_test_device",
    )
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
        return _ConcreteDevice(mqtt_config=device_config)


@pytest.fixture
def device_with_hooks(mqtt_config: MQTTConfig, mock_paho_client: MagicMock) -> _ConcreteDevice:
    """Concrete device with start/stop hooks enabled."""
    # Override client_id for device-specific identification
    device_config = MQTTConfig(
        broker=mqtt_config.broker,
        port=mqtt_config.port,
        client_id="smartnest_test_device",
    )
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
        return _ConcreteDevice(mqtt_config=device_config, on_start_hook=True, on_stop_hook=True)


# -- Tests: Init ---------------------------------------------------------------


class TestBaseDeviceInit:
    """Tests for BaseDevice constructor."""

    def test_stores_device_id(self, device: _ConcreteDevice) -> None:
        """Device ID is stored and accessible via property."""
        assert device.device_id == "test_device"

    def test_stores_device_type(self, device: _ConcreteDevice) -> None:
        """Device type is stored and accessible via property."""
        assert device.device_type == "test_device"

    def test_stores_name(self, device: _ConcreteDevice) -> None:
        """Device name is stored and accessible via property."""
        assert device.name == "Test Device"

    def test_device_not_running_initially(self, device: _ConcreteDevice) -> None:
        """Device is not running before start() is called."""
        assert device.is_running is False

    def test_client_accessible(self, device: _ConcreteDevice) -> None:
        """MQTT client is accessible for testing."""
        assert device.client is not None

    def test_validates_device_id_empty(self, mock_paho_client: MagicMock) -> None:
        """Empty device_id raises ValueError."""
        with (
            patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client),
            pytest.raises(ValueError, match="must not be empty"),
        ):
            _ConcreteDevice(device_id="")

    def test_validates_device_id_wildcards(self, mock_paho_client: MagicMock) -> None:
        """Device ID with MQTT wildcards raises ValueError."""
        with (
            patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client),
            pytest.raises(ValueError, match="invalid MQTT characters"),
        ):
            _ConcreteDevice(device_id="light+01")

    def test_logs_device_registered(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Constructor must log DEVICE_REGISTERED with exact logger and parameters."""
        with (
            patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client),
            patch("backend.devices.base.log_with_code") as mock_log,
        ):
            _ConcreteDevice(device_id="test_id", name="Test", mqtt_config=mqtt_config)
            # Verify call with exact parameters
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            # Verify logger is not None (kills logger=None mutation)
            assert call_args.args[0] is not None
            assert hasattr(call_args.args[0], "info")  # It's a logger-like object
            assert call_args.args[1] == "info"
            assert call_args.args[2] == MessageCode.DEVICE_REGISTERED
            assert call_args.kwargs["device_id"] == "test_id"  # Exact value
            assert call_args.kwargs["device_type"] == "test_device"  # Exact value

    def test_init_creates_child_logger_with_device_context(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """__init__ must bind device_id and device_type to child logger."""
        # Create device
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            device = _ConcreteDevice(device_id="test_id", name="Test", mqtt_config=mqtt_config)

        # Verify logger has bound context by checking it's a bound logger
        assert isinstance(device._logger, structlog.BoundLoggerBase)

        # Verify the logger works without errors (implicitly verifies bind worked)
        # If device_id or device_type were None, the logger would still work but
        # mutations would survive. We verify the actual values by mocking log_with_code
        device.client.set_connected_for_test(True)
        with patch("backend.devices.base.log_with_code") as mock_log:
            # Trigger a log event that uses the bound logger
            device.start()  # This will call log_with_code with the bound logger

            # Verify log_with_code was called with a logger that has bound context
            # The logger parameter should not be None
            calls = mock_log.call_args_list
            assert len(calls) > 0
            for call in calls:
                logger_arg = call.args[0]
                # Verify logger is not None - kills logger=None mutation
                assert logger_arg is not None
                # Verify it's a bound logger (has context)
                assert isinstance(logger_arg, structlog.BoundLoggerBase)


# -- Tests: Start --------------------------------------------------------------


class TestBaseDeviceStart:
    """Tests for BaseDevice.start() lifecycle."""

    def test_start_connects_to_broker(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() connects the MQTT client to the broker."""
        device.client.set_connected_for_test(True)
        result = device.start()
        assert result is True
        mock_paho_client.connect.assert_called_once()

    def test_start_subscribes_to_command_topic(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() subscribes to the device command topic."""
        device.client.set_connected_for_test(True)
        device.start()
        mock_paho_client.subscribe.assert_called_once_with(
            "smartnest/device/test_device/command", qos=1
        )

    def test_start_registers_command_handler(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() registers the command handler via message_callback_add."""
        device.client.set_connected_for_test(True)
        device.start()
        mock_paho_client.message_callback_add.assert_called_once_with(
            "smartnest/device/test_device/command",
            device._handle_command,
        )

    def test_start_publishes_discovery(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() publishes a retained discovery message."""
        device.client.set_connected_for_test(True)
        device.start()

        # Find the discovery publish call
        publish_calls = mock_paho_client.publish.call_args_list
        discovery_call = None
        for call in publish_calls:
            topic = call.args[0] if call.args else call.kwargs.get("topic")
            if topic == "smartnest/discovery/announce":
                discovery_call = call
                break

        assert discovery_call is not None
        assert discovery_call.kwargs.get("retain") is True or (
            len(discovery_call.args) > 3 and discovery_call.args[3] is True
        )

    def test_start_sets_running_true(self, device: _ConcreteDevice) -> None:
        """start() sets is_running to True on success."""
        device.client.set_connected_for_test(True)
        device.start()
        assert device.is_running is True

    def test_start_returns_false_on_connection_failure(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() returns False when broker connection fails."""
        mock_paho_client.connect.side_effect = OSError("Connection refused")
        result = device.start()
        assert result is False
        assert device.is_running is False

    def test_start_idempotent_when_already_running(self, device: _ConcreteDevice) -> None:
        """start() returns True immediately if already running."""
        device.client.set_connected_for_test(True)
        device.start()
        # Mock logger to avoid structlog I/O issues during mutation testing
        with patch.object(device._logger, "warning"):
            result = device.start()
        assert result is True

    def test_start_calls_on_start_hook(self, device_with_hooks: _ConcreteDevice) -> None:
        """start() calls _on_start() hook after setup."""
        device_with_hooks.client.set_connected_for_test(True)
        device_with_hooks.start()
        assert device_with_hooks.start_hook_called is True

    def test_start_logs_connection_failure(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() logs DEVICE_REGISTRATION_FAILED with exact error message."""
        mock_paho_client.connect.side_effect = OSError("Connection refused")
        with patch("backend.devices.base.log_with_code") as mock_log:
            device.start()
            # Find the registration failed log call
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_REGISTRATION_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger is not None (kills logger=None mutation)
            assert call.args[0] is not None
            assert hasattr(call.args[0], "error")  # It's a logger-like object
            assert call.args[1] == "error"
            assert call.kwargs["device_id"] == "test_device"
            # Verify error message contains connection failure info
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None
            # Verify exact error string - kills case/content variations
            assert call.kwargs["error"] == "Failed to connect to MQTT broker"

    def test_start_logs_device_connected(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() logs DEVICE_CONNECTED with exact device_id parameter."""
        device.client.set_connected_for_test(True)
        with patch("backend.devices.base.log_with_code") as mock_log:
            device.start()
            # Find the DEVICE_CONNECTED call and verify exact parameters
            connected_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_CONNECTED
            ]
            assert len(connected_calls) == 1
            call = connected_calls[0]
            # Verify logger is not None (kills logger=None mutation)
            assert call.args[0] is not None
            assert hasattr(call.args[0], "info")  # It's a logger-like object
            assert call.args[1] == "info"
            assert call.kwargs["device_id"] == "test_device"  # Exact value

    def test_start_default_timeout_exact_value(self) -> None:
        """start() default timeout must be exactly 10.0."""
        sig = inspect.signature(BaseDevice.start)
        # Verify exact default value - kills timeout=11.0, timeout=9.0 mutations
        assert sig.parameters["timeout"].default == 10.0

    def test_start_calls_start_operation_with_exact_params(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() must call start_operation with exact operation name and device_id."""
        device.client.set_connected_for_test(True)
        with patch("backend.devices.base.start_operation") as mock_start_op:
            device.start()

            # Verify start_operation called with exact parameters
            mock_start_op.assert_called_once()
            call = mock_start_op.call_args
            # Verify exact operation name - kills "XXdevice_startXX", None
            assert call.args[0] == "device_start"
            # Verify device_id kwarg present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "test_device"
            assert call.kwargs["device_id"] is not None

    def test_start_already_running_logs_exact_message(self, device: _ConcreteDevice) -> None:
        """start() when already running must log exact warning message."""
        device.client.set_connected_for_test(True)
        device.start()  # Start once

        # Mock the logger to capture the call
        with patch.object(device._logger, "warning") as mock_warn:
            device.start()  # Try to start again

            # Verify exact warning message
            mock_warn.assert_called_once()
            call_args = mock_warn.call_args
            # Kills None, "XXdevice_already_runningXX", "DEVICE_ALREADY_RUNNING"
            assert call_args.args[0] == "device_already_running"


# -- Tests: Stop ---------------------------------------------------------------


class TestBaseDeviceStop:
    """Tests for BaseDevice.stop() lifecycle."""

    def test_stop_disconnects_client(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """stop() disconnects the MQTT client."""
        device.client.set_connected_for_test(True)
        device.start()
        device.stop()
        mock_paho_client.disconnect.assert_called_once()

    def test_stop_sets_running_false(self, device: _ConcreteDevice) -> None:
        """stop() sets is_running to False."""
        device.client.set_connected_for_test(True)
        device.start()
        device.stop()
        assert device.is_running is False

    def test_stop_removes_command_handler(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """stop() removes the command handler before disconnecting."""
        device.client.set_connected_for_test(True)
        device.start()
        device.stop()
        mock_paho_client.message_callback_remove.assert_called_once_with(
            "smartnest/device/test_device/command"
        )

    def test_stop_noop_when_not_running(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """stop() does nothing if device is not running."""
        device.stop()
        mock_paho_client.disconnect.assert_not_called()

    def test_stop_calls_on_stop_hook(self, device_with_hooks: _ConcreteDevice) -> None:
        """stop() calls _on_stop() hook before teardown."""
        device_with_hooks.client.set_connected_for_test(True)
        device_with_hooks.start()
        device_with_hooks.stop()
        assert device_with_hooks.stop_hook_called is True

    def test_stop_logs_device_disconnected(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """stop() logs DEVICE_DISCONNECTED with exact reason parameter."""
        device.client.set_connected_for_test(True)
        device.start()
        with patch("backend.devices.base.log_with_code") as mock_log:
            device.stop(reason="test_shutdown")
            disconnect_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_DISCONNECTED
            ]
            assert len(disconnect_calls) == 1
            call = disconnect_calls[0]
            # Verify logger is not None (kills logger=None mutation)
            assert call.args[0] is not None
            assert hasattr(call.args[0], "info")  # It's a logger-like object
            assert call.args[1] == "info"
            assert call.kwargs["device_id"] == "test_device"
            assert call.kwargs["reason"] == "test_shutdown"  # Exact value

    def test_stop_default_reason_is_shutdown(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """stop() must use 'shutdown' as default reason, not None."""
        device.client.set_connected_for_test(True)
        device.start()
        with patch("backend.devices.base.log_with_code") as mock_log:
            device.stop()  # No reason parameter
            disconnect_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_DISCONNECTED
            ]
            call = disconnect_calls[0]
            # Verify exact default value - kills reason=None mutation
            assert call.kwargs["reason"] == "shutdown"
            assert call.kwargs["reason"] is not None


# -- Tests: Discovery ---------------------------------------------------------


class TestBaseDeviceDiscovery:
    """Tests for BaseDevice discovery announcement."""

    def test_publishes_discovery_on_start(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """start() publishes discovery payload to correct topic."""
        device.client.set_connected_for_test(True)
        device.start()

        publish_calls = mock_paho_client.publish.call_args_list
        discovery_calls = [
            c
            for c in publish_calls
            if (c.args[0] if c.args else c.kwargs.get("topic")) == "smartnest/discovery/announce"
        ]
        assert len(discovery_calls) == 1

    def test_discovery_payload_contains_required_fields(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """Discovery payload includes device_id, name, device_type, capabilities, topics."""
        device.client.set_connected_for_test(True)
        device.start()

        publish_calls = mock_paho_client.publish.call_args_list
        for call in publish_calls:
            topic = call.args[0] if call.args else call.kwargs.get("topic")
            if topic == "smartnest/discovery/announce":
                payload = json.loads(call.args[1])
                assert payload["device_id"] == "test_device"
                assert payload["name"] == "Test Device"
                assert payload["device_type"] == "test_device"
                assert "capabilities" in payload
                assert "topics" in payload
                return

        pytest.fail("Discovery publish not found")

    def test_discovery_logs_on_success(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """Successful discovery publish logs DEVICE_DISCOVERY_ANNOUNCED."""
        device.client.set_connected_for_test(True)
        with patch("backend.devices.base.log_with_code") as mock_log:
            device.start()
            announced_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_DISCOVERY_ANNOUNCED
            ]
            assert len(announced_calls) == 1


# -- Tests: State publishing ---------------------------------------------------


class TestBaseDeviceStatePublishing:
    """Tests for BaseDevice._publish_state()."""

    def test_publishes_state_via_client(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """_publish_state() delegates to client.publish_device_state()."""
        device.client.set_connected_for_test(True)
        state: dict[str, Any] = {"power": True, "brightness": 75}
        result = device._publish_state(state)
        assert result is True

    def test_publish_state_returns_false_when_not_connected(self, device: _ConcreteDevice) -> None:
        """_publish_state() returns False when client is not connected."""
        state: dict[str, Any] = {"power": True}
        result = device._publish_state(state)
        assert result is False

    def test_publish_state_logs_on_success(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """Successful state publish logs DEVICE_STATE_PUBLISHED with exact topic."""
        device.client.set_connected_for_test(True)
        with patch("backend.devices.base.log_with_code") as mock_log:
            device._publish_state({"power": True})
            published_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_STATE_PUBLISHED
            ]
            assert len(published_calls) == 1
            call = published_calls[0]
            # Verify logger is not None (kills logger=None mutation)
            assert call.args[0] is not None
            assert hasattr(call.args[0], "debug")  # It's a logger-like object
            assert call.args[1] == "debug"
            assert call.kwargs["device_id"] == "test_device"
            assert call.kwargs["topic"] == "smartnest/device/test_device/state"  # Exact topic


# -- Tests: Command parsing ---------------------------------------------------


class TestBaseDeviceCommandParsing:
    """Tests for BaseDevice.parse_command_payload() static method."""

    def test_parses_valid_json(self) -> None:
        """Valid JSON payloads are parsed correctly."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = json.dumps({"power": True}).encode("utf-8")
        result = BaseDevice.parse_command_payload(msg)
        assert result == {"power": True}

    def test_returns_none_for_invalid_json(self) -> None:
        """Invalid JSON returns None."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"not json"
        result = BaseDevice.parse_command_payload(msg)
        assert result is None

    def test_returns_none_for_invalid_encoding(self) -> None:
        """Non-UTF-8 payloads return None."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"\xff\xfe"
        result = BaseDevice.parse_command_payload(msg)
        assert result is None

    def test_handles_empty_object(self) -> None:
        """Empty JSON object parses successfully."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"{}"
        result = BaseDevice.parse_command_payload(msg)
        assert result == {}


# -- Tests: Default hooks -----------------------------------------------------


class TestBaseDeviceDefaultHooks:
    """Tests for BaseDevice _on_start/_on_stop default implementations."""

    def test_on_start_default_is_noop(self, device: _ConcreteDevice) -> None:
        """Default _on_start() does not raise or have side effects."""
        # The concrete device with hooks disabled should not set the flag
        device.client.set_connected_for_test(True)
        device.start()
        assert device.start_hook_called is False

    def test_on_stop_default_is_noop(self, device: _ConcreteDevice) -> None:
        """Default _on_stop() does not raise or have side effects."""
        device.client.set_connected_for_test(True)
        device.start()
        device.stop()
        assert device.stop_hook_called is False

    def test_base_on_start_returns_none(self, device: _ConcreteDevice) -> None:
        """BaseDevice._on_start() executes as no-op (covers default return)."""
        BaseDevice._on_start(device)  # should not raise

    def test_base_on_stop_returns_none(self, device: _ConcreteDevice) -> None:
        """BaseDevice._on_stop() executes as no-op (covers default return)."""
        BaseDevice._on_stop(device)  # should not raise

    def test_discovery_failure_branch(
        self, device: _ConcreteDevice, mock_paho_client: MagicMock
    ) -> None:
        """Discovery failure (publish returns False) does not log announced."""
        device.client.set_connected_for_test(False)
        with patch("backend.devices.base.log_with_code") as mock_log:
            device._publish_discovery()
            announced_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_DISCOVERY_ANNOUNCED
            ]
            assert len(announced_calls) == 0
