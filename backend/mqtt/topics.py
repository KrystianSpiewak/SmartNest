"""SmartNest MQTT Topic Structure.

Provides type-safe topic builders for the SmartNest MQTT topic hierarchy:

- Device commands:  ``smartnest/device/{device_id}/command``
- Device state:     ``smartnest/device/{device_id}/state``
- Device status:    ``smartnest/device/{device_id}/status``
- Sensor data:      ``smartnest/sensor/{device_id}/data``
- Discovery:        ``smartnest/discovery/announce``
- System events:    ``smartnest/system/event``
"""

from __future__ import annotations

from typing import Literal

# Type aliases for topic segments
DeviceTopicType = Literal["command", "state", "status"]
SystemTopicType = Literal["event"]

# Prefix constant
TOPIC_PREFIX = "smartnest"


def validate_device_id(device_id: str) -> None:
    """Validate a device identifier for use in MQTT topics.

    Raises:
        ValueError: If *device_id* is empty, contains whitespace,
            or includes MQTT wildcard characters (``+``, ``#``, ``/``).
    """
    if not device_id:
        msg = "device_id must not be empty"
        raise ValueError(msg)
    if not device_id.strip():
        msg = "device_id must not be whitespace-only"
        raise ValueError(msg)
    invalid_chars = {"+", "#", "/"}
    found = invalid_chars.intersection(device_id)
    if found:
        msg = f"device_id contains invalid MQTT characters: {sorted(found)}"
        raise ValueError(msg)


class TopicBuilder:
    """Build SmartNest MQTT topics following project conventions.

    All methods are class-level and stateless.  The topic hierarchy is::

        smartnest/
        ├── device/{device_id}/
        │   ├── command   (QoS 1 - device commands)
        │   ├── state     (QoS 1, retained - current device state)
        │   └── status    (QoS 1, retained - online/offline via LWT)
        ├── sensor/{device_id}/
        │   └── data      (QoS 0 - periodic sensor readings)
        ├── discovery/
        │   └── announce  (QoS 1 - device discovery)
        └── system/
            └── event     (QoS 1 - system-wide events)
    """

    PREFIX: str = TOPIC_PREFIX

    @classmethod
    def device_topic(cls, device_id: str, topic_type: DeviceTopicType) -> str:
        """Build a device-specific topic.

        Args:
            device_id: Unique device identifier (e.g. ``"light_01"``).
            topic_type: One of ``"command"``, ``"state"``, or ``"status"``.

        Returns:
            Fully-qualified MQTT topic string.

        Raises:
            ValueError: If *device_id* is invalid.
        """
        validate_device_id(device_id)
        return f"{cls.PREFIX}/device/{device_id}/{topic_type}"

    @classmethod
    def sensor_topic(cls, device_id: str) -> str:
        """Build a sensor data topic.

        Args:
            device_id: Unique sensor identifier.

        Returns:
            Fully-qualified MQTT topic string.

        Raises:
            ValueError: If *device_id* is invalid.
        """
        validate_device_id(device_id)
        return f"{cls.PREFIX}/sensor/{device_id}/data"

    @classmethod
    def discovery_topic(cls) -> str:
        """Return the device discovery announcement topic."""
        return f"{cls.PREFIX}/discovery/announce"

    @classmethod
    def system_topic(cls, topic_type: SystemTopicType = "event") -> str:
        """Build a system-wide event topic.

        Args:
            topic_type: Currently only ``"event"`` is supported.
        """
        return f"{cls.PREFIX}/system/{topic_type}"

    # -- Wildcard subscription helpers -----------------------------------------

    @classmethod
    def device_wildcard(cls, topic_type: DeviceTopicType) -> str:
        """Build a single-level wildcard subscription for all devices.

        Example:
            ``TopicBuilder.device_wildcard("state")``
            → ``"smartnest/device/+/state"``
        """
        return f"{cls.PREFIX}/device/+/{topic_type}"

    @classmethod
    def sensor_wildcard(cls) -> str:
        """Build a wildcard subscription for all sensor data.

        Returns:
            ``"smartnest/sensor/+/data"``
        """
        return f"{cls.PREFIX}/sensor/+/data"

    @classmethod
    def all_devices_wildcard(cls) -> str:
        """Build a multi-level wildcard for all device topics.

        Returns:
            ``"smartnest/device/#"``
        """
        return f"{cls.PREFIX}/device/#"
