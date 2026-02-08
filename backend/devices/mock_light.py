"""Mock smart light device for SmartNest.

Simulates a controllable smart light with power, brightness, and color
temperature capabilities.  Responds to JSON commands on its MQTT command
topic and publishes state updates on each change.

Command format::

    {"power": true, "brightness": 75, "color_temp": 3000}

State format (published on change)::

    {"power": true, "brightness": 75, "color_temp": 3000, "timestamp": 1707400000.0}

All fields in commands are optional — only provided fields are updated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.devices.base import BaseDevice
from backend.logging import MessageCode, get_logger, log_with_code, start_operation
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

    from backend.mqtt import MQTTConfig

logger = get_logger(__name__)

# Brightness bounds
_BRIGHTNESS_MIN = 0
_BRIGHTNESS_MAX = 100

# Color temperature bounds (Kelvin)
_COLOR_TEMP_MIN = 2700
_COLOR_TEMP_MAX = 6500


class MockSmartLight(BaseDevice):
    """Mock smart light with power, brightness, and color temperature.

    Attributes:
        power: Whether the light is on (``True``) or off (``False``).
        brightness: Brightness level (0-100).
        color_temp: Color temperature in Kelvin (2700-6500).

    Example::

        light = MockSmartLight(
            device_id="light_01",
            name="Living Room Light",
            config=MQTTConfig(broker="localhost", client_id="light_01"),
        )
        light.start()
    """

    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        config: MQTTConfig,
        power: bool = False,
        brightness: int = 100,
        color_temp: int = 4000,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="smart_light",
            name=name,
            config=config,
        )
        self._power = power
        self._brightness = self._clamp_brightness(brightness)
        self._color_temp = self._clamp_color_temp(color_temp)

    # -- Properties ------------------------------------------------------------

    @property
    def power(self) -> bool:
        """Return the current power state."""
        return self._power

    @property
    def brightness(self) -> int:
        """Return the current brightness level (0-100)."""
        return self._brightness

    @property
    def color_temp(self) -> int:
        """Return the current color temperature in Kelvin (2700-6500)."""
        return self._color_temp

    # -- State -----------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """Return the current device state as a dictionary."""
        return {
            "power": self._power,
            "brightness": self._brightness,
            "color_temp": self._color_temp,
        }

    # -- BaseDevice implementation ---------------------------------------------

    def _on_start(self) -> None:
        """Publish initial state after startup."""
        self._publish_state(self.get_state())

    def _handle_command(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Process an incoming light command.

        Accepts JSON with optional keys: ``power``, ``brightness``,
        ``color_temp``.  Invalid payloads or out-of-range values are
        logged and rejected.
        """
        correlation_id = start_operation("light_command", device_id=self._device_id)

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

        changed = self._apply_command(payload)

        if changed:
            log_with_code(
                self._logger,
                "info",
                MessageCode.DEVICE_STATE_UPDATED,
                device_id=self._device_id,
            )
            self._publish_state(self.get_state())

    def _get_discovery_payload(self) -> dict[str, Any]:
        """Return the discovery announcement for this light."""
        return {
            "device_id": self._device_id,
            "name": self._name,
            "device_type": self._device_type,
            "capabilities": ["power", "brightness", "color_temp"],
            "state": self.get_state(),
            "topics": {
                "command": TopicBuilder.device_topic(self._device_id, "command"),
                "state": TopicBuilder.device_topic(self._device_id, "state"),
            },
        }

    # -- Command processing ----------------------------------------------------

    def _apply_command(self, payload: dict[str, Any]) -> bool:
        """Apply command payload fields to device state.

        Args:
            payload: Parsed JSON command dictionary.

        Returns:
            ``True`` if any state field was changed.
        """
        changed = False

        if "power" in payload:
            new_power = bool(payload["power"])
            if new_power != self._power:
                self._power = new_power
                changed = True
                log_with_code(
                    self._logger,
                    "info",
                    MessageCode.DEVICE_COMMAND_SENT,
                    command="power",
                    device_id=self._device_id,
                )

        if "brightness" in payload:
            try:
                raw = int(payload["brightness"])
            except (TypeError, ValueError):
                log_with_code(
                    self._logger,
                    "warning",
                    MessageCode.DEVICE_COMMAND_FAILED,
                    command="brightness",
                    device_id=self._device_id,
                    error=f"Invalid brightness value: {payload['brightness']}",
                )
                return changed
            new_brightness = self._clamp_brightness(raw)
            if new_brightness != self._brightness:
                self._brightness = new_brightness
                changed = True
                log_with_code(
                    self._logger,
                    "info",
                    MessageCode.DEVICE_COMMAND_SENT,
                    command="brightness",
                    device_id=self._device_id,
                )

        if "color_temp" in payload:
            try:
                raw = int(payload["color_temp"])
            except (TypeError, ValueError):
                log_with_code(
                    self._logger,
                    "warning",
                    MessageCode.DEVICE_COMMAND_FAILED,
                    command="color_temp",
                    device_id=self._device_id,
                    error=f"Invalid color_temp value: {payload['color_temp']}",
                )
                return changed
            new_color_temp = self._clamp_color_temp(raw)
            if new_color_temp != self._color_temp:
                self._color_temp = new_color_temp
                changed = True
                log_with_code(
                    self._logger,
                    "info",
                    MessageCode.DEVICE_COMMAND_SENT,
                    command="color_temp",
                    device_id=self._device_id,
                )

        return changed

    # -- Helpers ---------------------------------------------------------------

    @staticmethod
    def _clamp_brightness(value: int) -> int:
        """Clamp brightness to valid range [0, 100]."""
        return max(_BRIGHTNESS_MIN, min(_BRIGHTNESS_MAX, value))

    @staticmethod
    def _clamp_color_temp(value: int) -> int:
        """Clamp color temperature to valid range [2700, 6500]."""
        return max(_COLOR_TEMP_MIN, min(_COLOR_TEMP_MAX, value))
