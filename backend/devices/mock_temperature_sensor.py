"""Mock temperature sensor for SmartNest.

Simulates a temperature sensor that publishes periodic readings with
realistic drift simulation.  The temperature follows a random walk
within configurable bounds.

Sensor data format (published periodically)::

    {"value": 70.3, "unit": "F", "timestamp": 1707400000.0}

The sensor is a **time-driven** device — it publishes readings at a
configurable interval (default 30 seconds) without requiring external
commands.  It still listens on its command topic for control messages
(e.g., ``{"interval": 15}`` to change the reporting interval).
"""

from __future__ import annotations

import random
import threading
from typing import TYPE_CHECKING, Any

from backend.devices.base import BaseDevice
from backend.logging import MessageCode, get_logger, log_with_code
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

    from backend.mqtt import MQTTConfig

logger = get_logger(__name__)

# Temperature bounds (Fahrenheit)
_TEMP_MIN = 65.0
_TEMP_MAX = 75.0
_TEMP_DEFAULT = 70.0

# Drift per reading (±°F)
_DRIFT_AMOUNT = 0.5

# Default reporting interval (seconds)
_DEFAULT_INTERVAL = 30.0
_MIN_INTERVAL = 5.0


class MockTemperatureSensor(BaseDevice):
    """Mock temperature sensor with periodic readings and random drift.

    The sensor produces realistic temperature values by applying a
    random walk (±0.5°F per reading) within bounds of 65-75°F.

    Attributes:
        temperature: Current temperature reading.
        unit: Temperature unit (always ``"F"``).
        interval: Seconds between sensor readings.

    Example::

        sensor = MockTemperatureSensor(
            device_id="temp_01",
            name="Kitchen Temperature",
            config=MQTTConfig(broker="localhost", client_id="temp_01"),
            interval=30.0,
        )
        sensor.start()
    """

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        config: MQTTConfig,
        interval: float = _DEFAULT_INTERVAL,
        initial_temp: float = _TEMP_DEFAULT,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="temperature_sensor",
            name=name,
            config=config,
        )
        self._temperature = self._clamp_temperature(initial_temp)
        self._unit = "F"
        self._interval = max(_MIN_INTERVAL, interval)
        self._timer: threading.Timer | None = None
        self._timer_lock = threading.Lock()

    # -- Properties ------------------------------------------------------------

    @property
    def temperature(self) -> float:
        """Return the current temperature reading."""
        return self._temperature

    @property
    def unit(self) -> str:
        """Return the temperature unit."""
        return self._unit

    @property
    def interval(self) -> float:
        """Return the reporting interval in seconds."""
        return self._interval

    # -- State -----------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """Return the current sensor state as a dictionary."""
        return {
            "value": round(self._temperature, 1),
            "unit": self._unit,
        }

    def get_reading(self) -> dict[str, Any]:
        """Return a sensor reading payload."""
        return {
            "value": round(self._temperature, 1),
            "unit": self._unit,
        }

    # -- BaseDevice implementation ---------------------------------------------

    def _on_start(self) -> None:
        """Begin periodic temperature publishing."""
        self._schedule_reading()

    def _on_stop(self) -> None:
        """Cancel the periodic reading timer."""
        self._cancel_timer()

    def _handle_command(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Process a sensor control command.

        Supports ``{"interval": <seconds>}`` to change reporting interval.
        """
        payload = self.parse_command_payload(message)
        if payload is None:
            log_with_code(
                self._logger,
                "warning",
                MessageCode.DEVICE_COMMAND_FAILED,
                command="unknown",
                device_id=self._device_id,
                error="Invalid JSON payload",
            )
            return

        if "interval" in payload:
            try:
                new_interval = float(payload["interval"])
            except (TypeError, ValueError):
                log_with_code(
                    self._logger,
                    "warning",
                    MessageCode.DEVICE_COMMAND_FAILED,
                    command="interval",
                    device_id=self._device_id,
                    error=f"Invalid interval value: {payload['interval']}",
                )
                return

            self._interval = max(_MIN_INTERVAL, new_interval)
            log_with_code(
                self._logger,
                "info",
                MessageCode.DEVICE_COMMAND_SENT,
                command="interval",
                device_id=self._device_id,
            )

            # Restart timer with new interval
            if self._running:
                self._cancel_timer()
                self._schedule_reading()

    def _get_discovery_payload(self) -> dict[str, Any]:
        """Return the discovery announcement for this sensor."""
        return {
            "device_id": self._device_id,
            "name": self._name,
            "device_type": self._device_type,
            "sensor_class": "temperature",
            "unit": self._unit,
            "interval": self._interval,
            "capabilities": ["temperature"],
            "topics": {
                "command": TopicBuilder.device_topic(self._device_id, "command"),
                "data": TopicBuilder.sensor_topic(self._device_id),
            },
        }

    # -- Periodic reading ------------------------------------------------------

    def _schedule_reading(self) -> None:
        """Schedule the next temperature reading."""
        with self._timer_lock:
            self._timer = threading.Timer(self._interval, self._publish_reading)
            self._timer.daemon = True
            self._timer.start()

    def _publish_reading(self) -> None:
        """Simulate a temperature reading and publish it.

        Called by the timer.  Applies random drift, publishes the
        reading, then reschedules.
        """
        if not self._running:
            return

        self._simulate_drift()
        reading = self.get_reading()

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

        # Reschedule
        if self._running:
            self._schedule_reading()

    def _simulate_drift(self) -> None:
        """Apply random walk drift to the temperature."""
        drift = random.uniform(-_DRIFT_AMOUNT, _DRIFT_AMOUNT)
        self._temperature = self._clamp_temperature(self._temperature + drift)

    def _cancel_timer(self) -> None:
        """Cancel the periodic reading timer if active."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    # -- Helpers ---------------------------------------------------------------

    @staticmethod
    def _clamp_temperature(value: float) -> float:
        """Clamp temperature to valid range [65.0, 75.0]."""
        return max(_TEMP_MIN, min(_TEMP_MAX, value))
