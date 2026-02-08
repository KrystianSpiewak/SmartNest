"""SmartNest mock IoT device implementations.

Provides base device abstractions and concrete mock devices for testing
the SmartNest home automation system without physical hardware.

Public API::

    from backend.devices import BaseDevice
    from backend.devices import MockSmartLight
    from backend.devices import MockTemperatureSensor
    from backend.devices import MockMotionSensor
"""

from backend.devices.base import BaseDevice
from backend.devices.mock_light import MockSmartLight
from backend.devices.mock_motion_sensor import MockMotionSensor
from backend.devices.mock_temperature_sensor import MockTemperatureSensor

__all__ = [
    "BaseDevice",
    "MockMotionSensor",
    "MockSmartLight",
    "MockTemperatureSensor",
]
