"""Unit tests for MockTemperatureSensor device."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest

from backend.devices.mock_temperature_sensor import MockTemperatureSensor
from backend.logging.catalog import MessageCode
from backend.mqtt.config import MQTTConfig

# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def config() -> MQTTConfig:
    """Default test configuration for temperature sensor."""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="smartnest_temp_01",
    )


@pytest.fixture
def mock_paho() -> MagicMock:
    """Mocked paho.mqtt.client.Client instance."""
    mock = MagicMock(spec=mqtt.Client)
    mock.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_SUCCESS)
    mock.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    return mock


@pytest.fixture
def sensor(config: MQTTConfig, mock_paho: MagicMock) -> MockTemperatureSensor:
    """MockTemperatureSensor with mocked Paho client."""
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
        return MockTemperatureSensor(
            device_id="temp_01",
            name="Kitchen Temperature",
            config=config,
            interval=30.0,
        )


def _make_message(payload: dict[str, object]) -> MagicMock:
    """Create a mock MQTT message with JSON payload."""
    msg = MagicMock(spec=mqtt.MQTTMessage)
    msg.payload = json.dumps(payload).encode("utf-8")
    msg.topic = "smartnest/device/temp_01/command"
    return msg


# -- Tests: Init ---------------------------------------------------------------


class TestTempSensorInit:
    """Tests for MockTemperatureSensor constructor."""

    def test_default_temperature(self, sensor: MockTemperatureSensor) -> None:
        """Default initial temperature is 70.0°F."""
        assert sensor.temperature == 70.0

    def test_default_unit(self, sensor: MockTemperatureSensor) -> None:
        """Temperature unit is Fahrenheit."""
        assert sensor.unit == "F"

    def test_default_interval(self, sensor: MockTemperatureSensor) -> None:
        """Default reporting interval is 30 seconds."""
        assert sensor.interval == 30.0

    def test_device_type(self, sensor: MockTemperatureSensor) -> None:
        """Device type is 'temperature_sensor'."""
        assert sensor.device_type == "temperature_sensor"

    def test_custom_initial_temp(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Custom initial temperature is clamped to valid range."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_02",
                name="Custom",
                config=config,
                initial_temp=72.5,
            )
        assert sensor.temperature == 72.5

    def test_initial_temp_clamped_low(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Initial temperature below 65 is clamped to 65."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_03",
                name="Cold",
                config=config,
                initial_temp=50.0,
            )
        assert sensor.temperature == 65.0

    def test_initial_temp_clamped_high(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Initial temperature above 75 is clamped to 75."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_04",
                name="Hot",
                config=config,
                initial_temp=90.0,
            )
        assert sensor.temperature == 75.0

    def test_interval_minimum_enforced(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Interval below 5 seconds is clamped to 5."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_05",
                name="Fast",
                config=config,
                interval=1.0,
            )
        assert sensor.interval == 5.0

    def test_init_timer_starts_as_none(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Timer must be initialized to None, not empty string."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_01",
                name="Test",
                config=config,
            )
        # Verify timer is None before any reading scheduled
        assert sensor._timer is None  # Kills "" mutation
        assert sensor._timer != ""


# -- Tests: State and reading --------------------------------------------------


class TestTempSensorState:
    """Tests for get_state() and get_reading()."""

    def test_get_state(self, sensor: MockTemperatureSensor) -> None:
        """get_state() returns value and unit."""
        state = sensor.get_state()
        assert state["value"] == 70.0
        assert state["unit"] == "F"

    def test_get_reading(self, sensor: MockTemperatureSensor) -> None:
        """get_reading() returns value and unit."""
        reading = sensor.get_reading()
        assert reading["value"] == 70.0
        assert reading["unit"] == "F"


# -- Tests: Rounding precision -------------------------------------------------


class TestTempSensorRoundingPrecision:
    """Tests for temperature rounding precision."""

    def test_get_state_rounds_to_one_decimal(
        self, config: MQTTConfig, mock_paho: MagicMock
    ) -> None:
        """get_state must round to exactly 1 decimal place."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_01",
                name="Test",
                config=config,
                initial_temp=70.12345,  # Many decimals
            )
        state = sensor.get_state()
        # Verify exactly 1 decimal - kills round(x,None), round(x,2)
        assert state["value"] == 70.1
        # Verify it's actually rounded, not truncated
        sensor._temperature = 70.16
        assert sensor.get_state()["value"] == 70.2  # Rounds up

    def test_get_reading_rounds_to_one_decimal(
        self, config: MQTTConfig, mock_paho: MagicMock
    ) -> None:
        """get_reading must round to exactly 1 decimal place."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_01",
                name="Test",
                config=config,
                initial_temp=72.14,
            )
        reading = sensor.get_reading()
        # round(72.14, 1) = 72.1
        # round(72.14, None) = 72 (different!)
        # round(72.14, 2) = 72.14 (different!)
        assert reading["value"] == 72.1  # Kills all rounding mutations


# -- Tests: Temperature drift --------------------------------------------------


class TestTempSensorDrift:
    """Tests for temperature drift simulation."""

    def test_simulate_drift_changes_temperature(self, sensor: MockTemperatureSensor) -> None:
        """_simulate_drift() modifies the temperature within bounds."""
        initial = sensor.temperature
        # Run drift many times — should deviate from initial at some point
        different = False
        for _ in range(100):
            sensor._simulate_drift()
            if sensor.temperature != initial:
                different = True
                break
        assert different

    def test_drift_stays_within_bounds(self, sensor: MockTemperatureSensor) -> None:
        """Temperature stays within [65, 75] after many drift iterations."""
        for _ in range(1000):
            sensor._simulate_drift()
        assert 65.0 <= sensor.temperature <= 75.0

    def test_drift_at_lower_bound(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Drift from lower bound stays within range."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_06",
                name="Low",
                config=config,
                initial_temp=65.0,
            )
        for _ in range(100):
            sensor._simulate_drift()
        assert sensor.temperature >= 65.0

    def test_drift_at_upper_bound(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Drift from upper bound stays within range."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockTemperatureSensor(
                device_id="temp_07",
                name="High",
                config=config,
                initial_temp=75.0,
            )
        for _ in range(100):
            sensor._simulate_drift()
        assert sensor.temperature <= 75.0

    def test_simulate_drift_uses_negative_bound(self, sensor: MockTemperatureSensor) -> None:
        """_simulate_drift must use symmetric negative bound for random.uniform."""
        initial_temp = sensor.temperature

        with patch("backend.devices.mock_temperature_sensor.random.uniform") as mock_uniform:
            # Return a negative drift
            mock_uniform.return_value = -0.5
            sensor._simulate_drift()

            # Verify random.uniform was called with negative first argument
            mock_uniform.assert_called_once()
            first_arg = mock_uniform.call_args[0][0]
            second_arg = mock_uniform.call_args[0][1]
            # Kills random.uniform(+X, X) mutation
            assert first_arg < 0  # Must be negative
            assert second_arg > 0  # Must be positive
            assert abs(first_arg) == second_arg  # Symmetric

            # Verify temperature decreased
            assert sensor.temperature < initial_temp

    def test_simulate_drift_applies_addition(self, sensor: MockTemperatureSensor) -> None:
        """_simulate_drift must ADD drift to temperature, not subtract."""
        with patch("backend.devices.mock_temperature_sensor.random.uniform") as mock_uniform:
            mock_uniform.return_value = 1.0  # Positive drift
            initial = sensor._temperature
            sensor._simulate_drift()
            # Kills self._temperature - drift mutation
            assert sensor._temperature > initial  # Must increase


# -- Tests: Publishing ---------------------------------------------------------


class TestTempSensorPublishing:
    """Tests for periodic sensor data publishing."""

    def test_publish_reading_publishes_data(
        self, sensor: MockTemperatureSensor, mock_paho: MagicMock
    ) -> None:
        """_publish_reading() publishes sensor data to correct topic."""
        sensor.client.set_connected_for_test(True)
        sensor._running = True
        mock_paho.publish.reset_mock()

        # Patch timer scheduling to avoid side effects
        with patch.object(sensor, "_schedule_reading"):
            sensor._publish_reading()

        publish_calls = mock_paho.publish.call_args_list
        sensor_calls = [
            c
            for c in publish_calls
            if (c.args[0] if c.args else "") == "smartnest/sensor/temp_01/data"
        ]
        assert len(sensor_calls) == 1

    def test_publish_reading_logs_success(
        self, sensor: MockTemperatureSensor, mock_paho: MagicMock
    ) -> None:
        """Successful publish logs DEVICE_SENSOR_PUBLISHED."""
        sensor.client.set_connected_for_test(True)
        sensor._running = True
        with (
            patch.object(sensor, "_schedule_reading"),
            patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log,
        ):
            sensor._publish_reading()
            published_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_SENSOR_PUBLISHED
            ]
            assert len(published_calls) == 1

    def test_publish_reading_noop_when_not_running(
        self, sensor: MockTemperatureSensor, mock_paho: MagicMock
    ) -> None:
        """_publish_reading() does nothing when sensor is not running."""
        sensor._running = False
        mock_paho.publish.reset_mock()
        sensor._publish_reading()
        mock_paho.publish.assert_not_called()

    def test_publish_reading_reschedules(
        self, sensor: MockTemperatureSensor, mock_paho: MagicMock
    ) -> None:
        """_publish_reading() reschedules itself after publishing."""
        sensor.client.set_connected_for_test(True)
        sensor._running = True
        with patch.object(sensor, "_schedule_reading") as mock_schedule:
            sensor._publish_reading()
            mock_schedule.assert_called_once()

    def test_publish_reading_no_log_when_publish_fails(
        self, sensor: MockTemperatureSensor, mock_paho: MagicMock
    ) -> None:
        """Failed publish does not log DEVICE_SENSOR_PUBLISHED."""
        sensor._running = True
        # Client not connected → publish_sensor_data returns False
        with (
            patch.object(sensor, "_schedule_reading"),
            patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log,
        ):
            sensor._publish_reading()
            published_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_SENSOR_PUBLISHED
            ]
            assert len(published_calls) == 0

    def test_publish_reading_no_reschedule_when_stopped(
        self, sensor: MockTemperatureSensor, mock_paho: MagicMock
    ) -> None:
        """_publish_reading() does not reschedule when _running goes False mid-publish."""
        sensor.client.set_connected_for_test(True)
        sensor._running = True

        # Simulate _running going False during publish (between publish and reschedule)
        original_publish = sensor._client.publish_sensor_data

        def publish_and_stop(device_id: str, data: dict[str, object]) -> bool:
            result = original_publish(device_id, data)
            sensor._running = False  # Stop mid-publish
            return result

        with (
            patch.object(sensor._client, "publish_sensor_data", side_effect=publish_and_stop),
            patch.object(sensor, "_schedule_reading") as mock_schedule,
        ):
            sensor._publish_reading()
            mock_schedule.assert_not_called()


# -- Tests: Timer management --------------------------------------------------


class TestTempSensorTimerManagement:
    """Tests for timer lifecycle management."""

    def test_on_start_schedules_reading(self, sensor: MockTemperatureSensor) -> None:
        """_on_start() schedules the first reading."""
        with patch.object(sensor, "_schedule_reading") as mock_schedule:
            sensor._on_start()
            mock_schedule.assert_called_once()

    def test_on_stop_cancels_timer(self, sensor: MockTemperatureSensor) -> None:
        """_on_stop() cancels the active timer."""
        with patch.object(sensor, "_cancel_timer") as mock_cancel:
            sensor._on_stop()
            mock_cancel.assert_called_once()

    def test_cancel_timer_clears_reference(self, sensor: MockTemperatureSensor) -> None:
        """_cancel_timer() sets timer to None."""
        mock_timer = MagicMock()
        sensor._timer = mock_timer
        sensor._cancel_timer()
        assert sensor._timer is None
        mock_timer.cancel.assert_called_once()

    def test_cancel_timer_noop_when_no_timer(self, sensor: MockTemperatureSensor) -> None:
        """_cancel_timer() is safe when no timer exists."""
        sensor._timer = None
        sensor._cancel_timer()  # Should not raise

    def test_schedule_reading_creates_timer(self, sensor: MockTemperatureSensor) -> None:
        """_schedule_reading() creates and starts a daemon Timer."""
        with patch("backend.devices.mock_temperature_sensor.threading.Timer") as mock_timer_cls:
            mock_timer = MagicMock()
            mock_timer_cls.return_value = mock_timer
            sensor._schedule_reading()
            mock_timer_cls.assert_called_once_with(30.0, sensor._publish_reading)
            assert mock_timer.daemon is True
            mock_timer.start.assert_called_once()


# -- Tests: Command handling ---------------------------------------------------


class TestTempSensorCommandHandling:
    """Tests for MockTemperatureSensor command processing."""

    def test_interval_command_updates_interval(self, sensor: MockTemperatureSensor) -> None:
        """Interval command changes the reporting interval."""
        msg = _make_message({"interval": 15})
        sensor._handle_command(MagicMock(), None, msg)
        assert sensor.interval == 15.0

    def test_interval_command_enforces_minimum(self, sensor: MockTemperatureSensor) -> None:
        """Interval below minimum is clamped to 5 seconds."""
        msg = _make_message({"interval": 1})
        sensor._handle_command(MagicMock(), None, msg)
        assert sensor.interval == 5.0

    def test_invalid_json_logs_failure(self, sensor: MockTemperatureSensor) -> None:
        """Invalid JSON payload logs DEVICE_COMMAND_FAILED."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"bad json"
        with patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1

    def test_invalid_interval_type_logs_failure(self, sensor: MockTemperatureSensor) -> None:
        """Non-numeric interval value logs DEVICE_COMMAND_FAILED."""
        msg = _make_message({"interval": "fast"})
        with patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1

    def test_interval_command_restarts_timer_when_running(
        self, sensor: MockTemperatureSensor
    ) -> None:
        """Interval change restarts the timer when sensor is running."""
        sensor._running = True
        msg = _make_message({"interval": 10})
        with (
            patch.object(sensor, "_cancel_timer") as mock_cancel,
            patch.object(sensor, "_schedule_reading") as mock_schedule,
        ):
            sensor._handle_command(MagicMock(), None, msg)
            mock_cancel.assert_called_once()
            mock_schedule.assert_called_once()

    def test_interval_command_no_timer_restart_when_stopped(
        self, sensor: MockTemperatureSensor
    ) -> None:
        """Interval change does not restart timer when sensor is stopped."""
        sensor._running = False
        msg = _make_message({"interval": 10})
        with patch.object(sensor, "_schedule_reading") as mock_schedule:
            sensor._handle_command(MagicMock(), None, msg)
            mock_schedule.assert_not_called()

    def test_command_without_interval_is_noop(self, sensor: MockTemperatureSensor) -> None:
        """Valid JSON without 'interval' key does nothing."""
        msg = _make_message({"brightness": 50})
        original_interval = sensor.interval
        sensor._handle_command(MagicMock(), None, msg)
        assert sensor.interval == original_interval


# -- Tests: Command logging ----------------------------------------------------


class TestTempSensorCommandLogging:
    """Tests for command log events with exact logger and parameter verification."""

    def test_interval_command_logs_with_exact_params(self, sensor: MockTemperatureSensor) -> None:
        """Interval change must log with non-None logger and command='interval'."""
        msg = _make_message({"interval": 15})
        with patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 1
            call = sent_calls[0]
            # Verify logger is not None - kills logger=None mutations
            assert call.args[0] is not None
            assert hasattr(call.args[0], "info")
            assert call.args[1] == "info"
            assert call.kwargs["command"] == "interval"  # Exact string
            assert call.kwargs["device_id"] == "temp_01"

    def test_invalid_json_logs_with_logger(self, sensor: MockTemperatureSensor) -> None:
        """Invalid JSON must log with non-None logger."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"not json"
        with patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger is not None
            assert call.args[0] is not None
            # Verify exact log level - kills level=None, level="WARNING"
            assert call.args[1] == "warning"
            # Verify command parameter present - kills removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "unknown"
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "temp_01"
            assert call.kwargs["device_id"] is not None
            # Verify error parameter present - kills error=None
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None
            # Verify exact error string - kills case/content variations
            assert call.kwargs["error"] == "Invalid JSON payload"

    def test_invalid_interval_logs_exact_command_and_error(
        self, sensor: MockTemperatureSensor
    ) -> None:
        """Invalid interval must log exact command='interval' and error message."""
        msg = _make_message({"interval": "fast"})
        with patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1
            call = failed_calls[0]
            # Verify logger is not None
            assert call.args[0] is not None
            # Verify exact log level - kills level=None, level="WARNING"
            assert call.args[1] == "warning"
            # Verify command parameter present - kills command=None, removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "interval"  # Exact string
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "temp_01"
            assert call.kwargs["device_id"] is not None
            # Verify error parameter present - kills error=None
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None


# -- Tests: State publishing methods -------------------------------------------


class TestTempSensorStatePublishLogging:
    """Tests for state publishing methods with logger verification."""

    def test_publish_reading_logs_with_exact_params(self, sensor: MockTemperatureSensor) -> None:
        """_publish_reading must log SENSOR_DATA_PUBLISHED with non-None logger."""
        sensor.client.set_connected_for_test(True)
        sensor._running = True
        with (
            patch.object(sensor, "_schedule_reading"),
            patch("backend.devices.mock_temperature_sensor.log_with_code") as mock_log,
        ):
            sensor._publish_reading()
            # Find sensor data published log
            calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_SENSOR_PUBLISHED
            ]
            assert len(calls) == 1
            call = calls[0]
            # Verify logger is not None - kills logger=None mutations
            assert call.args[0] is not None
            assert hasattr(call.args[0], "debug")
            assert call.args[1] == "debug"
            assert call.kwargs["device_id"] == "temp_01"
            assert call.kwargs["topic"] == "smartnest/sensor/temp_01/data"


# -- Tests: Discovery ----------------------------------------------------------


class TestTempSensorDiscovery:
    """Tests for MockTemperatureSensor discovery payload."""

    def test_discovery_payload_structure(self, sensor: MockTemperatureSensor) -> None:
        """Discovery payload contains all required fields."""
        payload = sensor._get_discovery_payload()
        assert payload["device_id"] == "temp_01"
        assert payload["name"] == "Kitchen Temperature"
        assert payload["device_type"] == "temperature_sensor"
        assert payload["sensor_class"] == "temperature"
        assert payload["unit"] == "F"
        assert payload["interval"] == 30.0
        assert "temperature" in payload["capabilities"]
        assert "command" in payload["topics"]
        assert "data" in payload["topics"]

    def test_discovery_topic_paths(self, sensor: MockTemperatureSensor) -> None:
        """Discovery payload topics point to correct MQTT topics."""
        payload = sensor._get_discovery_payload()
        assert payload["topics"]["command"] == "smartnest/device/temp_01/command"
        assert payload["topics"]["data"] == "smartnest/sensor/temp_01/data"
