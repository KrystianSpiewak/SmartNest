"""Unit tests for MockMotionSensor device."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest

from backend.devices.mock_motion_sensor import MockMotionSensor
from backend.logging.catalog import MessageCode
from backend.mqtt.config import MQTTConfig

# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def config() -> MQTTConfig:
    """Default test configuration for motion sensor."""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="smartnest_motion_01",
    )


@pytest.fixture
def mock_paho() -> MagicMock:
    """Mocked paho.mqtt.client.Client instance."""
    mock = MagicMock(spec=mqtt.Client)
    mock.publish.return_value = MagicMock(rc=mqtt.MQTT_ERR_SUCCESS)
    mock.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    return mock


@pytest.fixture
def sensor(config: MQTTConfig, mock_paho: MagicMock) -> MockMotionSensor:
    """MockMotionSensor with mocked Paho client."""
    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
        return MockMotionSensor(
            device_id="motion_01",
            name="Hallway Motion",
            config=config,
            cooldown=5.0,
        )


def _make_message(payload: dict[str, object]) -> MagicMock:
    """Create a mock MQTT message with JSON payload."""
    msg = MagicMock(spec=mqtt.MQTTMessage)
    msg.payload = json.dumps(payload).encode("utf-8")
    msg.topic = "smartnest/device/motion_01/command"
    return msg


# -- Tests: Init ---------------------------------------------------------------


class TestMotionSensorInit:
    """Tests for MockMotionSensor constructor."""

    def test_default_motion_not_detected(self, sensor: MockMotionSensor) -> None:
        """Initially no motion detected."""
        assert sensor.motion_detected is False

    def test_default_cooldown(self, sensor: MockMotionSensor) -> None:
        """Default cooldown is 5 seconds."""
        assert sensor.cooldown == 5.0

    def test_device_type(self, sensor: MockMotionSensor) -> None:
        """Device type is 'motion_sensor'."""
        assert sensor.device_type == "motion_sensor"

    def test_cooldown_minimum_enforced(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Cooldown below 1 second is clamped to 1."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockMotionSensor(
                device_id="motion_02",
                name="Fast",
                config=config,
                cooldown=0.1,
            )
        assert sensor.cooldown == 1.0

    def test_custom_cooldown(self, config: MQTTConfig, mock_paho: MagicMock) -> None:
        """Custom cooldown above minimum is accepted."""
        with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
            sensor = MockMotionSensor(
                device_id="motion_03",
                name="Slow",
                config=config,
                cooldown=10.0,
            )
        assert sensor.cooldown == 10.0

    def test_no_cooldown_timer_initially(self, sensor: MockMotionSensor) -> None:
        """No cooldown timer exists at construction."""
        assert sensor._cooldown_timer is None


# -- Tests: State --------------------------------------------------------------


class TestMotionSensorState:
    """Tests for get_state() and motion_detected property."""

    def test_get_state_clear(self, sensor: MockMotionSensor) -> None:
        """get_state() returns 'clear' when no motion."""
        state = sensor.get_state()
        assert state["state"] == "clear"

    def test_get_state_motion(self, sensor: MockMotionSensor) -> None:
        """get_state() returns 'motion' when motion detected."""
        sensor._motion_detected = True
        state = sensor.get_state()
        assert state["state"] == "motion"

    def test_motion_detected_property_false(self, sensor: MockMotionSensor) -> None:
        """motion_detected is False when clear."""
        assert sensor.motion_detected is False

    def test_motion_detected_property_true(self, sensor: MockMotionSensor) -> None:
        """motion_detected is True when triggered."""
        sensor._motion_detected = True
        assert sensor.motion_detected is True


# -- Tests: Trigger/Clear motion -----------------------------------------------


class TestMotionSensorTriggerClear:
    """Tests for trigger_motion() and clear_motion() public API."""

    def test_trigger_motion_sets_detected(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """trigger_motion() sets motion_detected to True."""
        sensor._client.set_connected_for_test(True)
        sensor.trigger_motion()
        assert sensor.motion_detected is True

    def test_trigger_motion_publishes_sensor_data(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """trigger_motion() publishes sensor data to correct topic."""
        sensor._client.set_connected_for_test(True)
        mock_paho.publish.reset_mock()
        sensor.trigger_motion()
        sensor_calls = [
            c
            for c in mock_paho.publish.call_args_list
            if "smartnest/sensor/motion_01/data" in str(c)
        ]
        assert len(sensor_calls) >= 1

    def test_publish_sensor_state_no_log_when_publish_fails(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """_publish_sensor_state skips logging when publish returns False."""
        # Not connected → publish_sensor_data returns False
        sensor._client.set_connected_for_test(False)
        with patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log:
            sensor._publish_sensor_state()
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_SENSOR_PUBLISHED
            ]
            assert len(sent_calls) == 0

    def test_trigger_motion_starts_cooldown_timer(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """trigger_motion() starts the cooldown timer."""
        sensor._client.set_connected_for_test(True)
        with patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls:
            mock_timer = MagicMock()
            mock_cls.return_value = mock_timer
            sensor.trigger_motion()
            mock_cls.assert_called_once_with(5.0, sensor._auto_clear)
            mock_timer.start.assert_called_once()

    def test_trigger_motion_timer_is_daemon(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """Cooldown timer must be daemon thread to not block shutdown."""
        sensor._client.set_connected_for_test(True)
        with patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_timer_cls:
            mock_timer = MagicMock()
            mock_timer_cls.return_value = mock_timer

            sensor.trigger_motion()

            # Verify timer was created
            mock_timer_cls.assert_called_once()
            # Verify daemon property was set to True - kills daemon=None, daemon=False
            assert mock_timer.daemon is True

    def test_retrigger_cancels_old_cooldown(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """Re-triggering cancels existing cooldown timer before creating new."""
        sensor._client.set_connected_for_test(True)
        old_timer = MagicMock()
        sensor._cooldown_timer = old_timer
        sensor._motion_detected = True  # already triggered
        with patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls:
            mock_cls.return_value = MagicMock()
            sensor.trigger_motion()
            old_timer.cancel.assert_called_once()

    def test_retrigger_does_not_republish_state(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """Re-triggering (already detected) does not republish sensor data."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        mock_paho.publish.reset_mock()
        with patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls:
            mock_cls.return_value = MagicMock()
            sensor.trigger_motion()
        # No publish because motion was already detected
        mock_paho.publish.assert_not_called()

    def test_clear_motion_resets_detected(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """clear_motion() sets motion_detected to False."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        sensor.clear_motion()
        assert sensor.motion_detected is False

    def test_clear_motion_publishes_sensor_data(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """clear_motion() publishes sensor data."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        mock_paho.publish.reset_mock()
        sensor.clear_motion()
        sensor_calls = [
            c
            for c in mock_paho.publish.call_args_list
            if "smartnest/sensor/motion_01/data" in str(c)
        ]
        assert len(sensor_calls) >= 1

    def test_clear_motion_cancels_cooldown_timer(self, sensor: MockMotionSensor) -> None:
        """clear_motion() cancels existing cooldown timer."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        mock_timer = MagicMock()
        sensor._cooldown_timer = mock_timer
        sensor.clear_motion()
        mock_timer.cancel.assert_called_once()
        assert sensor._cooldown_timer is None

    def test_clear_when_already_clear_is_noop(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """clear_motion() when already clear does not publish."""
        sensor._client.set_connected_for_test(True)
        mock_paho.publish.reset_mock()
        sensor.clear_motion()
        mock_paho.publish.assert_not_called()


# -- Tests: Auto-clear ---------------------------------------------------------


class TestMotionSensorAutoClear:
    """Tests for auto-clear cooldown timer."""

    def test_auto_clear_resets_when_running(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """_auto_clear() clears motion when running."""
        sensor._client.set_connected_for_test(True)
        sensor._running = True
        sensor._motion_detected = True
        sensor._auto_clear()
        assert sensor.motion_detected is False

    def test_auto_clear_noop_when_not_running(self, sensor: MockMotionSensor) -> None:
        """_auto_clear() does nothing when not running."""
        sensor._running = False
        sensor._motion_detected = True
        sensor._auto_clear()
        assert sensor.motion_detected is True

    def test_auto_clear_noop_when_already_clear(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """_auto_clear() does nothing when already clear."""
        sensor._running = True
        sensor._motion_detected = False
        mock_paho.publish.reset_mock()
        sensor._auto_clear()
        mock_paho.publish.assert_not_called()


# -- Tests: Cancel cooldown ----------------------------------------------------


class TestMotionSensorCancelCooldown:
    """Tests for _cancel_cooldown() helper."""

    def test_cancel_cooldown_clears_timer(self, sensor: MockMotionSensor) -> None:
        """_cancel_cooldown() cancels and clears timer reference."""
        mock_timer = MagicMock()
        sensor._cooldown_timer = mock_timer
        sensor._cancel_cooldown()
        mock_timer.cancel.assert_called_once()
        assert sensor._cooldown_timer is None

    def test_cancel_cooldown_noop_when_no_timer(self, sensor: MockMotionSensor) -> None:
        """_cancel_cooldown() is safe when no timer exists."""
        sensor._cooldown_timer = None
        sensor._cancel_cooldown()  # Should not raise


# -- Tests: Command handling ---------------------------------------------------


class TestMotionSensorCommandHandling:
    """Tests for MockMotionSensor command processing."""

    def test_trigger_command(self, sensor: MockMotionSensor, mock_paho: MagicMock) -> None:
        """'trigger' command activates motion detection."""
        sensor._client.set_connected_for_test(True)
        msg = _make_message({"trigger": True})
        with patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls:
            mock_cls.return_value = MagicMock()
            sensor._handle_command(MagicMock(), None, msg)
        assert sensor.motion_detected is True

    def test_clear_command(self, sensor: MockMotionSensor, mock_paho: MagicMock) -> None:
        """'clear' command resets motion detection."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        msg = _make_message({"clear": True})
        sensor._handle_command(MagicMock(), None, msg)
        assert sensor.motion_detected is False

    def test_invalid_json_logs_failure(self, sensor: MockMotionSensor) -> None:
        """Invalid JSON payload logs DEVICE_COMMAND_FAILED."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"!not-json!"
        with patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            failed_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_FAILED
            ]
            assert len(failed_calls) == 1

    def test_no_action_in_payload(self, sensor: MockMotionSensor) -> None:
        """Payload with no trigger/clear keys does nothing."""
        msg = _make_message({"something": "else"})
        sensor._handle_command(MagicMock(), None, msg)
        assert sensor.motion_detected is False


# -- Tests: Command logging ----------------------------------------------------


class TestMotionSensorCommandLogging:
    """Tests for command log events with exact logger and parameter verification."""

    def test_handle_command_starts_operation_with_exact_params(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """_handle_command must call start_operation with exact operation and device_id."""
        sensor._client.set_connected_for_test(True)
        msg = _make_message({"trigger": True})
        with (
            patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls,
            patch("backend.devices.mock_motion_sensor.start_operation") as mock_start_op,
        ):
            mock_cls.return_value = MagicMock()
            mock_start_op.return_value = "test-correlation-id"
            sensor._handle_command(MagicMock(), None, msg)

            # Verify start_operation called with exact parameters
            mock_start_op.assert_called_once()
            call = mock_start_op.call_args
            # Kills operation=None, "XXmotion_commandXX", "MOTION_COMMAND"
            assert call.args[0] == "motion_command"
            # Kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "motion_01"
            assert call.kwargs["device_id"] is not None

    def test_trigger_command_logs_with_exact_params(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """Trigger command must log with non-None logger and command='trigger'."""
        sensor._client.set_connected_for_test(True)
        msg = _make_message({"trigger": True})
        with (
            patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls,
            patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log,
        ):
            mock_cls.return_value = MagicMock()
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
            # Verify exact log level - kills level=None, level="INFO"
            assert call.args[1] == "info"
            # Verify command parameter present - kills command=None, removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "trigger"  # Exact string
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "motion_01"
            assert call.kwargs["device_id"] is not None

    def test_clear_command_logs_with_exact_params(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """Clear command must log with non-None logger and command='clear'."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        msg = _make_message({"clear": True})
        with patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log:
            sensor._handle_command(MagicMock(), None, msg)
            sent_calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_COMMAND_SENT
            ]
            assert len(sent_calls) == 1
            call = sent_calls[0]
            assert call.args[0] is not None
            assert hasattr(call.args[0], "info")
            # Verify exact log level - kills level=None, level="INFO"
            assert call.args[1] == "info"
            # Verify command parameter present - kills command=None, removal
            assert "command" in call.kwargs
            assert call.kwargs["command"] == "clear"  # Exact string
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "motion_01"
            assert call.kwargs["device_id"] is not None

    def test_invalid_json_logs_with_logger(self, sensor: MockMotionSensor) -> None:
        """Invalid JSON must log with non-None logger."""
        msg = MagicMock(spec=mqtt.MQTTMessage)
        msg.payload = b"!not-json!"
        with patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log:
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
            assert call.kwargs["command"] == "unknown"
            # Verify device_id parameter present - kills device_id=None, removal
            assert "device_id" in call.kwargs
            assert call.kwargs["device_id"] == "motion_01"
            assert call.kwargs["device_id"] is not None
            # Verify error parameter present - kills error=None
            assert "error" in call.kwargs
            assert call.kwargs["error"] is not None
            # Verify exact error string - kills case/content variations
            assert call.kwargs["error"] == "Invalid JSON payload"
            # Verify correlation_id parameter present - kills correlation_id=None, removal
            assert "correlation_id" in call.kwargs
            assert call.kwargs["correlation_id"] is not None


# -- Tests: State publishing methods -------------------------------------------


class TestMotionSensorStatePublishLogging:
    """Tests for state publishing methods with logger verification."""

    def test_trigger_motion_logs_with_exact_params(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """trigger_motion must log SENSOR_DATA_PUBLISHED with non-None logger."""
        sensor._client.set_connected_for_test(True)
        with (
            patch("backend.devices.mock_motion_sensor.threading.Timer") as mock_cls,
            patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log,
        ):
            mock_cls.return_value = MagicMock()
            sensor.trigger_motion()
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
            assert call.kwargs["device_id"] == "motion_01"
            assert call.kwargs["topic"] == "smartnest/sensor/motion_01/data"

    def test_clear_motion_logs_with_exact_params(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """clear_motion must log SENSOR_DATA_PUBLISHED with non-None logger."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        with patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log:
            sensor.clear_motion()
            # Find sensor data published log
            calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_SENSOR_PUBLISHED
            ]
            assert len(calls) == 1
            call = calls[0]
            assert call.args[0] is not None
            assert hasattr(call.args[0], "debug")
            assert call.args[1] == "debug"
            assert call.kwargs["device_id"] == "motion_01"
            assert call.kwargs["topic"] == "smartnest/sensor/motion_01/data"

    def test_publish_sensor_state_logs_with_exact_params(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """_publish_sensor_state must log with non-None logger when successful."""
        sensor._client.set_connected_for_test(True)
        sensor._motion_detected = True
        with patch("backend.devices.mock_motion_sensor.log_with_code") as mock_log:
            sensor._publish_sensor_state()
            calls = [
                c
                for c in mock_log.call_args_list
                if len(c.args) >= 3 and c.args[2] == MessageCode.DEVICE_SENSOR_PUBLISHED
            ]
            assert len(calls) == 1
            call = calls[0]
            assert call.args[0] is not None
            assert call.args[1] == "debug"
            assert call.kwargs["topic"] == "smartnest/sensor/motion_01/data"


# -- Tests: Discovery ----------------------------------------------------------


class TestMotionSensorDiscovery:
    """Tests for MockMotionSensor discovery payload."""

    def test_discovery_payload_structure(self, sensor: MockMotionSensor) -> None:
        """Discovery payload contains all required fields."""
        payload = sensor._get_discovery_payload()
        assert payload["device_id"] == "motion_01"
        assert payload["name"] == "Hallway Motion"
        assert payload["device_type"] == "motion_sensor"
        assert payload["device_class"] == "motion"
        assert payload["cooldown"] == 5.0
        assert "motion" in payload["capabilities"]
        assert "command" in payload["topics"]
        assert "data" in payload["topics"]

    def test_discovery_topic_paths(self, sensor: MockMotionSensor) -> None:
        """Discovery payload topics point to correct MQTT topics."""
        payload = sensor._get_discovery_payload()
        assert payload["topics"]["command"] == "smartnest/device/motion_01/command"
        assert payload["topics"]["data"] == "smartnest/sensor/motion_01/data"


# -- Tests: On-start/On-stop hooks --------------------------------------------


class TestMotionSensorLifecycle:
    """Tests for _on_start() and _on_stop() hooks."""

    def test_on_start_publishes_initial_state(
        self, sensor: MockMotionSensor, mock_paho: MagicMock
    ) -> None:
        """_on_start() publishes initial sensor state."""
        sensor._client.set_connected_for_test(True)
        mock_paho.publish.reset_mock()
        sensor._on_start()
        sensor_calls = [
            c
            for c in mock_paho.publish.call_args_list
            if "smartnest/sensor/motion_01/data" in str(c)
        ]
        assert len(sensor_calls) >= 1

    def test_on_stop_cancels_cooldown_timer(self, sensor: MockMotionSensor) -> None:
        """_on_stop() cancels cooldown timer."""
        mock_timer = MagicMock()
        sensor._cooldown_timer = mock_timer
        sensor._on_stop()
        mock_timer.cancel.assert_called_once()
        assert sensor._cooldown_timer is None

    def test_on_stop_no_timer_safe(self, sensor: MockMotionSensor) -> None:
        """_on_stop() is safe when no timer exists."""
        sensor._cooldown_timer = None
        sensor._on_stop()  # Should not raise
