"""Unit tests for MockSmartLight device."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest

from backend.devices.mock_light import MockSmartLight
from backend.logging.catalog import MessageCode
from backend.mqtt.config import MQTTConfig

# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def light(mqtt_config: MQTTConfig, mock_paho_client: MagicMock) -> MockSmartLight:
    """MockSmartLight with mocked Paho client."""
    # Override client_id for device-specific identification
    light_config = MQTTConfig(
        broker=mqtt_config.broker,
        port=mqtt_config.port,
        client_id="smartnest_light_01",
    )
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
        return MockSmartLight(
            device_id="light_01",
            name="Living Room Light",
            config=light_config,
        )


def _make_message(payload: dict[str, object]) -> MagicMock:
    """Create a mock MQTT message with JSON payload."""
    msg = MagicMock(spec=mqtt.MQTTMessage)
    msg.payload = json.dumps(payload).encode("utf-8")
    msg.topic = "smartnest/device/light_01/command"
    return msg


# -- Tests: Init ---------------------------------------------------------------


class TestMockSmartLightInit:
    """Tests for MockSmartLight constructor."""

    def test_default_state(self, light: MockSmartLight) -> None:
        """Light initializes with power off, full brightness, neutral color."""
        assert light.power is False
        assert light.brightness == 100
        assert light.color_temp == 4000

    def test_custom_initial_state(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Custom initial state values are accepted."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light = MockSmartLight(
                device_id="light_02",
                name="Custom Light",
                config=mqtt_config,
                power=True,
                brightness=50,
                color_temp=3000,
            )
        assert light.power is True
        assert light.brightness == 50
        assert light.color_temp == 3000

    def test_device_type_is_smart_light(self, light: MockSmartLight) -> None:
        """Device type is set to 'smart_light'."""
        assert light.device_type == "smart_light"

    def test_brightness_clamped_below_zero(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Brightness below 0 is clamped to 0."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light = MockSmartLight(
                device_id="light_03", name="Low", config=mqtt_config, brightness=-10
            )
        assert light.brightness == 0

    def test_brightness_clamped_above_100(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Brightness above 100 is clamped to 100."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light = MockSmartLight(
                device_id="light_04", name="High", config=mqtt_config, brightness=200
            )
        assert light.brightness == 100

    def test_color_temp_clamped_below_min(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Color temp below 2700 is clamped to 2700."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light = MockSmartLight(
                device_id="light_05", name="Warm", config=mqtt_config, color_temp=1000
            )
        assert light.color_temp == 2700

    def test_color_temp_clamped_above_max(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Color temp above 6500 is clamped to 6500."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light = MockSmartLight(
                device_id="light_06", name="Cool", config=mqtt_config, color_temp=9000
            )
        assert light.color_temp == 6500

    def test_brightness_defaults_to_100(
        self, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Creating light without brightness parameter defaults to 100."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light = MockSmartLight(
                device_id="test_light",
                name="Test",
                config=mqtt_config,
                # Explicitly NOT providing brightness parameter
            )
        # Verify runtime default value - kills brightness=101 mutation
        assert light.brightness == 100


# -- Tests: get_state ----------------------------------------------------------


class TestMockSmartLightGetState:
    """Tests for MockSmartLight.get_state()."""

    def test_returns_current_state(self, light: MockSmartLight) -> None:
        """get_state() returns a dict with power, brightness, color_temp."""
        state = light.get_state()
        assert state == {"power": False, "brightness": 100, "color_temp": 4000}


# -- Tests: Command handling ---------------------------------------------------


class TestMockSmartLightCommandHandling:
    """Tests for MockSmartLight._handle_command()."""

    def test_power_on(self, light: MockSmartLight) -> None:
        """Power command turns the light on."""
        msg = _make_message({"power": True})
        light._handle_command(MagicMock(), None, msg)
        assert light.power is True

    def test_power_off(
        self, light: MockSmartLight, mqtt_config: MQTTConfig, mock_paho_client: MagicMock
    ) -> None:
        """Power command turns the light off."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho_client):
            light_on = MockSmartLight(
                device_id="light_07", name="On", config=mqtt_config, power=True
            )
        msg = _make_message({"power": False})
        light_on._handle_command(MagicMock(), None, msg)
        assert light_on.power is False

    def test_set_brightness(self, light: MockSmartLight) -> None:
        """Brightness command updates brightness level."""
        msg = _make_message({"brightness": 75})
        light._handle_command(MagicMock(), None, msg)
        assert light.brightness == 75

    def test_set_brightness_clamped(self, light: MockSmartLight) -> None:
        """Brightness values outside range are clamped."""
        msg = _make_message({"brightness": 150})
        light._handle_command(MagicMock(), None, msg)
        assert light.brightness == 100

    def test_set_color_temp(self, light: MockSmartLight) -> None:
        """Color temp command updates color temperature."""
        msg = _make_message({"color_temp": 3000})
        light._handle_command(MagicMock(), None, msg)
        assert light.color_temp == 3000

    def test_set_color_temp_clamped(self, light: MockSmartLight) -> None:
        """Color temp values outside range are clamped."""
        msg = _make_message({"color_temp": 10000})
        light._handle_command(MagicMock(), None, msg)
        assert light.color_temp == 6500

    def test_multiple_fields_in_one_command(self, light: MockSmartLight) -> None:
        """Command with multiple fields updates all at once."""
        msg = _make_message({"power": True, "brightness": 50, "color_temp": 3000})
        light._handle_command(MagicMock(), None, msg)
        assert light.power is True
        assert light.brightness == 50
        assert light.color_temp == 3000

    def test_invalid_json_ignored(self, light: MockSmartLight) -> None:
        """Invalid JSON payload is ignored without crashing."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"not json"
        light._handle_command(MagicMock(), None, msg)
        # State unchanged
        assert light.power is False
        assert light.brightness == 100

    def test_invalid_brightness_type_rejected(self, light: MockSmartLight) -> None:
        """Non-numeric brightness value is rejected."""
        msg = _make_message({"brightness": "bright"})
        light._handle_command(MagicMock(), None, msg)
        assert light.brightness == 100  # unchanged

    def test_invalid_color_temp_type_rejected(self, light: MockSmartLight) -> None:
        """Non-numeric color_temp value is rejected."""
        msg = _make_message({"color_temp": "warm"})
        light._handle_command(MagicMock(), None, msg)
        assert light.color_temp == 4000  # unchanged

    def test_no_change_no_publish(self, light: MockSmartLight, mock_paho_client: MagicMock) -> None:
        """Command that doesn't change state doesn't trigger publish."""
        light.client.set_connected_for_test(True)
        mock_paho_client.publish.reset_mock()
        # Send current values — no change
        msg = _make_message({"brightness": 100})
        light._handle_command(MagicMock(), None, msg)
        mock_paho_client.publish.assert_not_called()

    def test_same_power_no_log(self, light: MockSmartLight) -> None:
        """Setting power to current value does not log DEVICE_COMMAND_SENT."""
        # light starts with power=False
        msg = _make_message({"power": False})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 0

    def test_same_color_temp_no_log(self, light: MockSmartLight) -> None:
        """Setting color_temp to current value does not log DEVICE_COMMAND_SENT."""
        # light starts with color_temp=4000
        msg = _make_message({"color_temp": 4000})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 0

    def test_state_change_publishes(
        self, light: MockSmartLight, mock_paho_client: MagicMock
    ) -> None:
        """State change triggers a publish."""
        light.client.set_connected_for_test(True)
        mock_paho_client.publish.reset_mock()
        msg = _make_message({"power": True})
        light._handle_command(MagicMock(), None, msg)
        assert mock_paho_client.publish.called

    def test_empty_command_no_change(self, light: MockSmartLight) -> None:
        """Empty command payload causes no state change."""
        msg = _make_message({})
        light._handle_command(MagicMock(), None, msg)
        assert light.power is False
        assert light.brightness == 100
        assert light.color_temp == 4000


# -- Tests: Command logging ---------------------------------------------------


class TestMockSmartLightCommandLogging:
    """Tests for MockSmartLight command log events."""

    def test_handle_command_starts_operation_with_exact_params(self, light: MockSmartLight) -> None:
        """_handle_command must call start_operation with exact operation and device_id."""
        msg = _make_message({"power": True})
        with patch("backend.devices.mock_light.start_operation") as mock_start_op:
            mock_start_op.return_value = "test-correlation-id"
            light._handle_command(MagicMock(), None, msg)

            # Verify start_operation called with exact parameters
            mock_start_op.assert_called_once()
            call = mock_start_op.call_args
            # Kills operation=None, "XXlight_commandXX", "LIGHT_COMMAND"
            assert call.args[0] == "light_command"
            # Kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "light_01"
            assert call.kwargs["device_id"] is not None

    def test_invalid_json_logs_failure(self, light: MockSmartLight) -> None:
        """Invalid JSON must log with exact logger and error."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"not json"
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger is not None and exact parameters
            assert call.args[0] is not None
            # Verify exact log level - kills level=None, level="WARNING"
            assert call.args[1] == "warning"
            # Verify command parameter present - kills command=None, removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "unknown"
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "light_01"
            assert call.kwargs["device_id"] is not None
            # Verify error parameter present - kills error=None
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None
            # Verify exact error string - kills case/content variations
            assert call.kwargs["error"] == "Invalid JSON payload"
            # Verify correlation_id parameter present - kills correlation_id=None, removal
            assert "correlation_id" in call.kwargs
            assert call.kwargs["correlation_id"] is not None

    def test_power_change_logs_command_sent(self, light: MockSmartLight) -> None:
        """Power state change must log exact command='power'."""
        msg = _make_message({"power": True})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 1
            call = sent_calls[0]
            # Verify logger is not None and exact parameters
            assert call.args[0] is not None
            # Verify exact log level - kills level=None, level="INFO"
            assert call.args[1] == "info"
            # Verify command parameter present - kills command=None, removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "power"  # Exact string, kills mutations
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "light_01"
            assert call.kwargs["device_id"] is not None

    def test_invalid_brightness_logs_failure(self, light: MockSmartLight) -> None:
        """Invalid brightness must log exact command='brightness' and error."""
        msg = _make_message({"brightness": "invalid"})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger and exact parameters
            assert call.args[0] is not None
            # Verify exact log level - kills level=None, level="WARNING"
            assert call.args[1] == "warning"
            # Verify command parameter present - kills command=None, removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "brightness"  # Exact command name
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "light_01"
            assert call.kwargs["device_id"] is not None
            # Verify error parameter present - kills error=None
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None

    def test_brightness_change_logs_command_sent(self, light: MockSmartLight) -> None:
        """Brightness change must log exact command='brightness'."""
        msg = _make_message({"brightness": 50})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 1
            call = sent_calls[0]
            assert call.args[0] is not None
            assert call.args[1] == "info"
            assert call.kwargs["command"] == "brightness"  # Kills command=None mutations

    def test_color_temp_change_logs_command_sent(self, light: MockSmartLight) -> None:
        """Color temp change must log exact command='color_temp'."""
        msg = _make_message({"color_temp": 3000})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 1
            call = sent_calls[0]
            assert call.args[0] is not None
            assert call.args[1] == "info"
            assert call.kwargs["command"] == "color_temp"  # Exact string

    def test_invalid_color_temp_logs_failure(self, light: MockSmartLight) -> None:
        """Invalid color_temp value logs DEVICE_COMMAND_FAILED."""
        msg = _make_message({"color_temp": []})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1

    def test_state_updated_logged(self, light: MockSmartLight) -> None:
        """State change logs DEVICE_STATE_UPDATED."""
        msg = _make_message({"power": True})
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            light._handle_command(MagicMock(), None, msg)
            updated_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_STATE_UPDATED
            ]
            assert len(updated_calls) == 1


# -- Tests: _apply_command return value ---------------------------------------


class TestMockSmartLightApplyCommand:
    """Tests for MockSmartLight._apply_command() return value."""

    def test_apply_command_returns_true_when_power_changes(self, light: MockSmartLight) -> None:
        """_apply_command must return True when power changes."""
        result = light._apply_command({"power": True})
        assert result is True  # Kills changed=False, changed=None mutations
        assert light.power is True

    def test_apply_command_returns_false_when_no_change(self, light: MockSmartLight) -> None:
        """_apply_command must return False when state unchanged."""
        result = light._apply_command({"power": False})  # Already False
        assert result is False  # Kills changed=True, changed=None mutations
        assert light.power is False

    def test_apply_command_returns_true_when_brightness_changes(
        self, light: MockSmartLight
    ) -> None:
        """_apply_command must return True when brightness changes."""
        result = light._apply_command({"brightness": 50})
        assert result is True  # Kills changed=False mutation
        assert light.brightness == 50

    def test_apply_command_returns_false_when_brightness_unchanged(
        self, light: MockSmartLight
    ) -> None:
        """_apply_command returns False when brightness stays same."""
        result = light._apply_command({"brightness": 100})  # Already 100
        assert result is False
        assert light.brightness == 100

    def test_apply_command_returns_true_when_color_temp_changes(
        self, light: MockSmartLight
    ) -> None:
        """_apply_command must return True when color temp changes."""
        result = light._apply_command({"color_temp": 3000})
        assert result is True
        assert light.color_temp == 3000

    def test_apply_command_returns_false_when_color_temp_unchanged(
        self, light: MockSmartLight
    ) -> None:
        """_apply_command returns False when color temp stays same."""
        result = light._apply_command({"color_temp": 4000})  # Already 4000
        assert result is False

    def test_apply_command_multiple_changes_returns_true(self, light: MockSmartLight) -> None:
        """_apply_command returns True if ANY field changes."""
        result = light._apply_command({"power": True, "brightness": 75})
        assert result is True
        assert light.power is True
        assert light.brightness == 75

    def test_apply_command_empty_payload_returns_false(self, light: MockSmartLight) -> None:
        """_apply_command with empty payload returns False."""
        result = light._apply_command({})
        assert result is False  # No changes

    def test_apply_command_invalid_brightness_returns_false(self, light: MockSmartLight) -> None:
        """_apply_command with invalid brightness returns False (no state change)."""
        result = light._apply_command({"brightness": "invalid"})
        assert result is False
        assert light.brightness == 100  # Unchanged

    def test_apply_command_invalid_color_temp_logs_exact_params(
        self, light: MockSmartLight
    ) -> None:
        """Invalid color_temp must log with exact command, device_id, and error."""
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            result = light._apply_command({"color_temp": "invalid"})

            # Verify return value is False (no change)
            assert result is False

            # Find DEVICE_COMMAND_FAILED call
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]

            # Verify all parameters present with exact values
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "color_temp"  # NOT None, NOT removed
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "light_01"  # NOT None
            assert call.kwargs["device_id"] is not None
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None  # NOT None
            assert "invalid" in call.kwargs["error"].lower()  # Contains actual value
            assert call.args[1] == "warning"  # Exact log level

    def test_apply_command_color_temp_success_logs_exact_params(
        self, light: MockSmartLight
    ) -> None:
        """Successful color_temp change must log with exact command and device_id."""
        with patch("backend.devices.mock_light.log_with_code") as mock_log:
            result = light._apply_command({"color_temp": 3500})

            assert result is True

            # Find DEVICE_COMMAND_SENT call
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 1
            call = sent_calls[0]

            # Verify parameters
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "color_temp"
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "light_01"  # NOT None
            assert call.kwargs["device_id"] is not None
            assert call.args[1] == "info"


# -- Tests: Discovery payload -------------------------------------------------


class TestMockSmartLightDiscovery:
    """Tests for MockSmartLight discovery payload."""

    def test_discovery_payload_structure(self, light: MockSmartLight) -> None:
        """Discovery payload contains all required fields."""
        payload = light._get_discovery_payload()
        assert payload["device_id"] == "light_01"
        assert payload["name"] == "Living Room Light"
        assert payload["device_type"] == "smart_light"
        assert "power" in payload["capabilities"]
        assert "brightness" in payload["capabilities"]
        assert "color_temp" in payload["capabilities"]
        assert "command" in payload["topics"]
        assert "state" in payload["topics"]

    def test_discovery_topics_correct(self, light: MockSmartLight) -> None:
        """Discovery payload topics point to correct MQTT topics."""
        payload = light._get_discovery_payload()
        assert payload["topics"]["command"] == "smartnest/device/light_01/command"
        assert payload["topics"]["state"] == "smartnest/device/light_01/state"

    def test_discovery_includes_current_state(self, light: MockSmartLight) -> None:
        """Discovery payload includes current device state."""
        payload = light._get_discovery_payload()
        assert "state" in payload
        assert payload["state"]["power"] is False


# -- Tests: on_start -----------------------------------------------------------


class TestMockSmartLightOnStart:
    """Tests for MockSmartLight._on_start() initial state publish."""

    def test_on_start_publishes_initial_state(
        self, light: MockSmartLight, mock_paho_client: MagicMock
    ) -> None:
        """_on_start() publishes the initial device state."""
        light.client.set_connected_for_test(True)
        light.start()

        publish_calls = mock_paho_client.publish.call_args_list
        state_calls = [
            c
            for c in publish_calls
            if (c.args[0] if c.args else "") == "smartnest/device/light_01/state"
        ]
        assert len(state_calls) >= 1
