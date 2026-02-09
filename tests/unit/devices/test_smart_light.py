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
def config() -> MQTTConfig:
    """Default test configuration for light device."""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="smartnest_light_01",
    )


@pytest.fixture
def mock_paho() -> MagicMock:
    """Mocked paho.mqtt.client.Client instance."""
    mock = MagicMock(spec=mqtt.Client)
    mock.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_SUCCESS)
    mock.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    return mock


@pytest.fixture
def light(config: MQTTConfig, mock_paho: MagicMock) -> MockSmartLight:
    """MockSmartLight with mocked Paho client."""
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
        return MockSmartLight(
            device_id="light_01",
            name="Living Room Light",
            config=config,
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

    def test_custom_initial_state(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Custom initial state values are accepted."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            light = MockSmartLight(
                device_id="light_02",
                name="Custom Light",
                config=config,
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

    def test_brightness_clamped_below_zero(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Brightness below 0 is clamped to 0."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            light = MockSmartLight(device_id="light_03", name="Low", config=config, brightness=-10)
        assert light.brightness == 0

    def test_brightness_clamped_above_100(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Brightness above 100 is clamped to 100."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            light = MockSmartLight(device_id="light_04", name="High", config=config, brightness=200)
        assert light.brightness == 100

    def test_color_temp_clamped_below_min(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Color temp below 2700 is clamped to 2700."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            light = MockSmartLight(
                device_id="light_05", name="Warm", config=config, color_temp=1000
            )
        assert light.color_temp == 2700

    def test_color_temp_clamped_above_max(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Color temp above 6500 is clamped to 6500."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            light = MockSmartLight(
                device_id="light_06", name="Cool", config=config, color_temp=9000
            )
        assert light.color_temp == 6500


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
        self, light: MockSmartLight, config: MQTTConfig, mock_paho: MagicMock
    ) -> None:
        """Power command turns the light off."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            light_on = MockSmartLight(device_id="light_07", name="On", config=config, power=True)
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

    def test_no_change_no_publish(self, light: MockSmartLight, mock_paho: MagicMock) -> None:
        """Command that doesn't change state doesn't trigger publish."""
        light.client.set_connected_for_test(True)
        mock_paho.publish.reset_mock()
        # Send current values — no change
        msg = _make_message({"brightness": 100})
        light._handle_command(MagicMock(), None, msg)
        mock_paho.publish.assert_not_called()

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

    def test_state_change_publishes(self, light: MockSmartLight, mock_paho: MagicMock) -> None:
        """State change triggers a publish."""
        light.client.set_connected_for_test(True)
        mock_paho.publish.reset_mock()
        msg = _make_message({"power": True})
        light._handle_command(MagicMock(), None, msg)
        assert mock_paho.publish.called

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
            assert call.args[1] == "warning"
            assert call.kwargs["device_id"] == "light_01"
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None

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
            assert call.args[1] == "info"
            assert call.kwargs["device_id"] == "light_01"
            assert call.kwargs["command"] == "power"  # Exact string, kills mutations

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
            assert call.args[1] == "warning"
            assert call.kwargs["device_id"] == "light_01"
            assert call.kwargs["command"] == "brightness"  # Exact command name
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
        self, light: MockSmartLight, mock_paho: MagicMock
    ) -> None:
        """_on_start() publishes the initial device state."""
        light.client.set_connected_for_test(True)
        light.start()

        publish_calls = mock_paho.publish.call_args_list
        state_calls = [
            c
            for c in publish_calls
            if (c.args[0] if c.args else "") == "smartnest/device/light_01/state"
        ]
        assert len(state_calls) >= 1
