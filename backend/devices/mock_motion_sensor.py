"""Mock motion sensor for SmartNest.

Simulates a binary motion sensor that detects motion events and
publishes state changes with a configurable cooldown period.

Sensor data format::

    {"state": "motion", "timestamp": 1707400000.0}

The sensor is **event-driven** — it publishes state changes when
motion is detected or clears.  A cooldown period prevents rapid
toggling between states.

Commands supported::

    {"trigger": true}   — Simulate motion detection
    {"clear": true}     — Manually clear motion state
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from backend.devices.base import BaseDevice
from backend.logging import MessageCode, get_logger, log_with_code, start_operation
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

    from backend.mqtt import MQTTConfig

logger = get_logger(__name__)

# Default cooldown (seconds)
_DEFAULT_COOLDOWN = 5.0
_MIN_COOLDOWN = 1.0

# Motion states
_STATE_MOTION = "motion"
_STATE_CLEAR = "clear"


class MockMotionSensor(BaseDevice):
    """Mock binary motion sensor with cooldown logic.

    Motion detection is simulated via MQTT commands.  When motion is
    triggered, the sensor publishes ``{"state": "motion"}`` and starts
    a cooldown timer.  After the cooldown expires, the sensor
    automatically clears (publishes ``{"state": "clear"}``).

    Attributes:
        motion_detected: Whether motion is currently detected.
        cooldown: Cooldown period in seconds.

    Example::

        sensor = MockMotionSensor(
            device_id="motion_01",
            name="Hallway Motion",
            config=MQTTConfig(broker="localhost", client_id="motion_01"),
            cooldown=5.0,
        )
        sensor.start()
    """

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        config: MQTTConfig,
        cooldown: float = _DEFAULT_COOLDOWN,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="motion_sensor",
            name=name,
            config=config,
        )
        self._motion_detected = False
        self._cooldown = max(_MIN_COOLDOWN, cooldown)
        self._cooldown_timer: threading.Timer | None = None
        self._timer_lock = threading.Lock()

    # -- Properties ------------------------------------------------------------

    @property
    def motion_detected(self) -> bool:
        """Return ``True`` if motion is currently detected."""
        return self._motion_detected

    @property
    def cooldown(self) -> float:
        """Return the cooldown period in seconds."""
        return self._cooldown

    # -- State -----------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """Return the current sensor state as a dictionary."""
        return {
            "state": _STATE_MOTION if self._motion_detected else _STATE_CLEAR,
        }

    # -- BaseDevice implementation ---------------------------------------------

    def _on_start(self) -> None:
        """Publish initial clear state after startup."""
        self._publish_sensor_state()

    def _on_stop(self) -> None:
        """Cancel any active cooldown timer."""
        self._cancel_cooldown()

    def _handle_command(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Process a motion sensor command.

        Supports:
            - ``{"trigger": true}`` — Simulate motion detection.
            - ``{"clear": true}`` — Manually clear motion state.
        """
        correlation_id = start_operation("motion_command", device_id=self._device_id)

        payload = self.parse_command_payload(message)
        if payload is None:
            log_with_code(
                self._logger,
                "warning",
                MessageCode.DEVICE_COMMAND_FAILED,
                command="unknown",
                device_id=self._device_id,
                error="Invalid JSON payload",
                correlation_id=correlation_id,
            )
            return

        if payload.get("trigger"):
            self._trigger_motion()
        elif payload.get("clear"):
            self._clear_motion()

    def _get_discovery_payload(self) -> dict[str, Any]:
        """Return the discovery announcement for this sensor."""
        return {
            "device_id": self._device_id,
            "name": self._name,
            "device_type": self._device_type,
            "device_class": "motion",
            "cooldown": self._cooldown,
            "capabilities": ["motion"],
            "topics": {
                "command": TopicBuilder.device_topic(self._device_id, "command"),
                "data": TopicBuilder.sensor_topic(self._device_id),
            },
        }

    # -- Motion logic ----------------------------------------------------------

    def trigger_motion(self) -> None:
        """Programmatically trigger motion detection.

        Public API for integration tests and external callers.
        """
        self._trigger_motion()

    def clear_motion(self) -> None:
        """Programmatically clear motion state.

        Public API for integration tests and external callers.
        """
        self._clear_motion()

    def _trigger_motion(self) -> None:
        """Trigger motion detection and start cooldown.

        If motion is already detected, the cooldown timer is reset.
        """
        # Cancel any existing cooldown (retrigger resets the window)
        self._cancel_cooldown()

        if not self._motion_detected:
            self._motion_detected = True
            log_with_code(
                self._logger,
                "info",
                MessageCode.DEVICE_COMMAND_SENT,
                command="trigger",
                device_id=self._device_id,
            )
            self._publish_sensor_state()

        # Start cooldown timer to auto-clear
        with self._timer_lock:
            self._cooldown_timer = threading.Timer(self._cooldown, self._auto_clear)
            self._cooldown_timer.daemon = True
            self._cooldown_timer.start()

    def _clear_motion(self) -> None:
        """Clear the motion state and cancel any cooldown timer."""
        self._cancel_cooldown()

        if self._motion_detected:
            self._motion_detected = False
            log_with_code(
                self._logger,
                "info",
                MessageCode.DEVICE_COMMAND_SENT,
                command="clear",
                device_id=self._device_id,
            )
            self._publish_sensor_state()

    def _auto_clear(self) -> None:
        """Auto-clear motion after cooldown expires.

        Called by the cooldown timer.
        """
        if self._running and self._motion_detected:
            self._motion_detected = False
            self._publish_sensor_state()

    # -- Publishing ------------------------------------------------------------

    def _publish_sensor_state(self) -> None:
        """Publish the current motion state as sensor data."""
        reading = self.get_state()
        success = self._client.publish_sensor_data(self._device_id, reading)
        if success:
            topic = TopicBuilder.sensor_topic(self._device_id)
            log_with_code(
                self._logger,
                "debug",
                MessageCode.DEVICE_SENSOR_PUBLISHED,
                device_id=self._device_id,
                topic=topic,
            )

    # -- Helpers ---------------------------------------------------------------

    def _cancel_cooldown(self) -> None:
        """Cancel the cooldown timer if active."""
        with self._timer_lock:
            if self._cooldown_timer is not None:
                self._cooldown_timer.cancel()
                self._cooldown_timer = None
