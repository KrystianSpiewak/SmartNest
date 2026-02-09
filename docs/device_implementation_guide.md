# SmartNest Device Implementation Guide

**Version:** 1.0  
**Phase:** 2 - Device Ecosystem  
**Last Updated:** February 8, 2026

---

## Overview

This guide explains how to create new mock IoT devices in SmartNest by inheriting from the `BaseDevice` abstract class. All devices follow a consistent pattern for MQTT lifecycle management, command handling, and state publishing.

## Table of Contents

1. [Quick Start](#quick-start)
2. [BaseDevice Architecture](#basedevice-architecture)
3. [Creating a New Device](#creating-a-new-device)
4. [Required Methods](#required-methods)
5. [Optional Lifecycle Hooks](#optional-lifecycle-hooks)
6. [State Management](#state-management)
7. [Testing Your Device](#testing-your-device)
8. [Common Patterns](#common-patterns)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

```python
from backend.devices.base import BaseDevice
from backend.mqtt import MQTTConfig
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

class MyDevice(BaseDevice):
    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        config: MQTTConfig,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="my_device",  # descriptive type label
            name=name,
            config=config,
        )
        # Initialize device-specific state here

    def _handle_command(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
        /,
    ) -> None:
        """Process incoming commands."""
        # Parse message.payload and update state

    def _get_discovery_payload(self) -> dict[str, Any]:
        """Return discovery announcement payload."""
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type,
            "capabilities": ["cap1", "cap2"],
            "topics": {
                "command": TopicBuilder.device_topic(self.device_id, "command"),
                "state": TopicBuilder.device_topic(self.device_id, "state"),
            },
        }

# Usage
device = MyDevice(
    device_id="my_device_01",
    name="My Test Device",
    config=MQTTConfig(broker="localhost", client_id="my_device_01"),
)
device.start()  # Connects, subscribes, announces
# ... device is running ...
device.stop()   # Disconnects cleanly
```

---

## BaseDevice Architecture

### Lifecycle

`BaseDevice` manages the complete device lifecycle:

1. **Initialization** - Validates device_id, creates MQTT client, configures logging
2. **Start** - Connects to broker, subscribes to command topic, publishes discovery
3. **Runtime** - Receives and processes commands, publishes state updates
4. **Stop** - Unsubscribes, disconnects, cleans up resources

### Automatic Behaviors

When you inherit from `BaseDevice`, you get:

- ✅ Validated device IDs (no MQTT wildcards)
- ✅ MQTT connection management with timeout
- ✅ Automatic command topic subscription (`smartnest/device/{device_id}/command`)
- ✅ Discovery announcement publishing (`smartnest/discovery/announce`)
- ✅ Structured logging with device context
- ✅ Idempotent start/stop (safe to call multiple times)
- ✅ Thread-safe state management

### Properties

All devices have these public properties:

| Property | Type | Description |
|----------|------|-------------|
| `device_id` | `str` | Unique device identifier (read-only) |
| `device_type` | `str` | Device type label (e.g. "smart_light") |
| `name` | `str` | Human-readable display name |
| `is_running` | `bool` | True if connected and running |
| `client` | `SmartNestMQTTClient` | Underlying MQTT client (testing only) |

---

## Creating a New Device

### Step 1: Define Device Class

```python
"""MyDevice - Brief description.

Detailed explanation of what this device simulates and its capabilities.

Command format::

    {"field1": value1, "field2": value2}

State format::

    {"field1": value1, "field2": value2, "timestamp": 1707400000.0}
"""

from backend.devices.base import BaseDevice

class MyDevice(BaseDevice):
    def __init__(
        self,
        *,
        device_id: str,
        name: str,
        config: MQTTConfig,
        # Add device-specific parameters
        param1: int = 0,
        param2: bool = False,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="my_device",
            name=name,
            config=config,
        )
        # Initialize device state
        self._param1 = param1
        self._param2 = param2
```

### Step 2: Implement Required Methods

Two methods are **required**:

```python
def _handle_command(
    self,
    _client: mqtt.Client,
    _userdata: object,
    message: mqtt.MQTTMessage,
    /,
) -> None:
    """Process an incoming command from MQTT."""
    # 1. Parse the message payload
    # 2. Validate the command
    # 3. Update device state
    # 4. Publish state update
    pass  # Implement your logic

def _get_discovery_payload(self) -> dict[str, Any]:
    """Return the discovery announcement payload."""
    return {
        "device_id": self.device_id,
        "name": self.name,
        "device_type": self.device_type,
        "capabilities": ["list", "of", "capabilities"],
        "topics": {
            "command": TopicBuilder.device_topic(self.device_id, "command"),
            "state": TopicBuilder.device_topic(self.device_id, "state"),
        },
    }
```

### Step 3: Add Optional Lifecycle Hooks

Override these methods to add custom behavior:

```python
def _on_start(self) -> None:
    """Called after successful start and discovery announcement."""
    # Publish initial state
    self._publish_state(self.get_state())

def _on_stop(self) -> None:
    """Called before disconnecting on stop()."""
    # Clean up timers, threads, or resources
    pass
```

---

## Required Methods

### `_handle_command()`

**Purpose:** Process incoming MQTT commands.

**Signature:**
```python
def _handle_command(
    self,
    _client: mqtt.Client,
    _userdata: object,
    message: mqtt.MQTTMessage,
    /,
) -> None
```

**Implementation Pattern:**

```python
def _handle_command(
    self,
    _client: mqtt.Client,
    _userdata: object,
    message: mqtt.MQTTMessage,
    /,
) -> None:
    start_operation("device_command_received")
    
    # 1. Parse JSON payload
    try:
        command: dict[str, Any] = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        log_with_code(
            self._logger,
            "error",
            MessageCode.DEVICE_COMMAND_INVALID,
            error=str(err),
        )
        return

    # 2. Validate and process command
    changed = False
    if "param1" in command:
        new_value = self._validate_param1(command["param1"])
        if new_value != self._param1:
            self._param1 = new_value
            changed = True

    # 3. Log and publish state if changed
    if changed:
        log_with_code(
            self._logger,
            "info",
            MessageCode.DEVICE_STATE_UPDATED,
        )
        self._publish_state(self.get_state())
```

**Best Practices:**
- ✅ Use `start_operation()` for tracing
- ✅ Handle JSON parsing errors gracefully
- ✅ Validate all input values before applying
- ✅ Only publish state if something changed
- ✅ Use structured logging with `log_with_code()`

### `_get_discovery_payload()`

**Purpose:** Define the device's discovery announcement.

**Signature:**
```python
def _get_discovery_payload(self) -> dict[str, Any]
```

**Required Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `device_id` | `str` | Must match `self.device_id` |
| `name` | `str` | Must match `self.name` |
| `device_type` | `str` | Must match `self.device_type` |
| `capabilities` | `list[str]` | List of supported capabilities |
| `topics` | `dict[str, str]` | MQTT topic map (at minimum `command`) |

**Example:**

```python
def _get_discovery_payload(self) -> dict[str, Any]:
    return {
        "device_id": self.device_id,
        "name": self.name,
        "device_type": self.device_type,
        "capabilities": ["power", "brightness", "color_temp"],
        "topics": {
            "command": TopicBuilder.device_topic(self.device_id, "command"),
            "state": TopicBuilder.device_topic(self.device_id, "state"),
        },
        "metadata": {
            "manufacturer": "SmartNest",
            "model": "Mock Light v1.0",
        },
    }
```

**Note:** The `model_config = ConfigDict(extra="allow")` in `DeviceDiscoveryMessage` allows additional fields beyond the required ones.

---

## Optional Lifecycle Hooks

### `_on_start()`

**Purpose:** Execute custom logic after successful start.

**Common Uses:**
- Publish initial device state
- Start background timers or threads
- Initialize sensor readings

**Example:**

```python
def _on_start(self) -> None:
    """Publish initial state and start periodic sensor readings."""
    self._publish_state(self.get_state())
    self._start_periodic_readings()
```

### `_on_stop()`

**Purpose:** Clean up resources before disconnect.

**Common Uses:**
- Stop timers or threads
- Flush buffers
- Release resources

**Example:**

```python
def _on_stop(self) -> None:
    """Stop periodic sensor readings."""
    if self._timer is not None:
        self._timer.cancel()
        self._timer = None
```

---

## State Management

### Getting State

Define a `get_state()` method to return current device state:

```python
def get_state(self) -> dict[str, Any]:
    """Return the current device state as a dictionary."""
    return {
        "param1": self._param1,
        "param2": self._param2,
    }
```

### Publishing State

Use the inherited `_publish_state()` method to publish state updates:

```python
def _publish_state(self, state: dict[str, Any]) -> None:
    """Publish device state to the state topic."""
    topic = TopicBuilder.device_topic(self.device_id, "state")
    success = self.client.publish(topic, state, qos=1, retain=True)
    
    if success:
        log_with_code(
            self._logger,
            "info",
            MessageCode.DEVICE_STATE_PUBLISHED,
            state=state,
        )
```

**Note:** `BaseDevice` provides this implementation. Call it after state changes.

### State Patterns

**Event-Driven (Commands):**
```python
# MockSmartLight pattern
def _handle_command(self, ...):
    # Update state based on command
    if "power" in command:
        self._power = command["power"]
    
    # Publish updated state
    self._publish_state(self.get_state())
```

**Time-Driven (Sensors):**
```python
# MockTemperatureSensor pattern
def _on_start(self):
    self._schedule_next_reading()

def _schedule_next_reading(self):
    self._timer = threading.Timer(self._interval, self._take_reading)
    self._timer.start()

def _take_reading(self):
    # Update sensor state
    self._current_temp += self._simulate_drift()
    
    # Publish sensor data
    self._publish_sensor_data({
        "value": self._current_temp,
        "unit": "°F",
        "timestamp": time.time(),
    })
    
    # Schedule next reading
    if self.is_running:
        self._schedule_next_reading()
```

---

## Testing Your Device

### Unit Test Template

```python
"""Unit tests for MyDevice."""

import pytest
from unittest.mock import MagicMock, patch

from backend.devices.my_device import MyDevice
from backend.mqtt import MQTTConfig

@pytest.fixture
def device() -> MyDevice:
    """Create a test device instance."""
    config = MQTTConfig(broker="localhost", client_id="test_device")
    return MyDevice(
        device_id="test_01",
        name="Test Device",
        config=config,
    )

class TestMyDevice:
    def test_initialization(self, device: MyDevice) -> None:
        """Device initializes with correct properties."""
        assert device.device_id == "test_01"
        assert device.device_type == "my_device"
        assert device.name == "Test Device"
        assert not device.is_running

    def test_start(self, device: MyDevice) -> None:
        """Device starts and publishes discovery."""
        with patch.object(device.client, "connect", return_value=True):
            with patch.object(device.client, "subscribe"):
                with patch.object(device.client, "publish") as mock_publish:
                    assert device.start()
                    assert device.is_running
                    assert mock_publish.called

    def test_handle_command(self, device: MyDevice) -> None:
        """Device processes commands correctly."""
        message = MagicMock()
        message.payload = b'{"param1": 42}'
        
        with patch.object(device, "_publish_state") as mock_publish:
            device._handle_command(MagicMock(), None, message)
            assert mock_publish.called

    def test_get_discovery_payload(self, device: MyDevice) -> None:
        """Discovery payload contains required fields."""
        payload = device._get_discovery_payload()
        assert payload["device_id"] == "test_01"
        assert payload["device_type"] == "my_device"
        assert "capabilities" in payload
        assert "topics" in payload
```

### Integration Test Pattern

```python
@pytest.mark.skipif(
    not _broker_available(),
    reason="MQTT broker not available",
)
def test_device_end_to_end():
    """Test device with real broker."""
    device = MyDevice(
        device_id="integration_test",
        name="Integration Test Device",
        config=MQTTConfig(broker="localhost", client_id="integration_test"),
    )
    
    try:
        assert device.start(timeout=5.0)
        # Send commands, verify state, etc.
    finally:
        device.stop()
```

---

## Common Patterns

### Input Validation

```python
def _clamp_value(self, value: int, min_val: int, max_val: int) -> int:
    """Clamp value to valid range."""
    return max(min_val, min(max_val, value))

def _handle_command(self, ...):
    if "brightness" in command:
        clamped = self._clamp_value(command["brightness"], 0, 100)
        if clamped != command["brightness"]:
            self._logger.warning(
                "brightness_clamped",
                requested=command["brightness"],
                actual=clamped,
            )
        self._brightness = clamped
```

### Periodic Tasks

```python
import threading

class MySensor(BaseDevice):
    def _on_start(self):
        self._schedule_reading()
    
    def _on_stop(self):
        if hasattr(self, "_timer") and self._timer:
            self._timer.cancel()
    
    def _schedule_reading(self):
        self._timer = threading.Timer(30.0, self._take_reading)
        self._timer.start()
    
    def _take_reading(self):
        # Take reading
        if self.is_running:
            self._schedule_reading()
```

### Error Recovery

```python
def _handle_command(self, ...):
    try:
        command = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        log_with_code(
            self._logger,
            "error",
            MessageCode.DEVICE_COMMAND_INVALID,
            error=str(err),
            payload=message.payload[:100],  # Log snippet
        )
        return  # Don't crash, just skip invalid command
```

---

## Troubleshooting

### Device Won't Start

**Symptom:** `device.start()` returns `False`

**Causes:**
1. MQTT broker is not running → Check `docker ps` or `npm run docker:up`
2. Invalid device_id → Check for MQTT wildcards (`+`, `#`)
3. Config client_id conflicts → Ensure unique client_id per device
4. Network issues → Verify broker host/port

### Commands Not Processed

**Symptom:** Commands sent but no state updates

**Debug Steps:**
1. Check topic name matches: `smartnest/device/{device_id}/command`
2. Verify JSON format is valid
3. Add debug logging to `_handle_command()`
4. Check `is_running` property is `True`

### State Not Publishing

**Symptom:** `_publish_state()` called but no state messages

**Debug Steps:**
1. Check QoS level (use QoS 1 or 2)
2. Verify client is connected: `device.is_running`
3. Check topic name: `smartnest/device/{device_id}/state`
4. Enable MQTT client logging

### Discovery Not Working

**Symptom:** Device not appearing in discovery registry

**Debug Steps:**
1. Verify `_get_discovery_payload()` returns valid dict
2. Check discovery topic: `smartnest/discovery/announce`
3. Ensure payload includes required fields
4. Check DiscoveryConsumer is running

---

## Reference Examples

- **Event-Driven Device:** [backend/devices/mock_light.py](../backend/devices/mock_light.py)
- **Time-Driven Sensor:** [backend/devices/mock_temperature_sensor.py](../backend/devices/mock_temperature_sensor.py)
- **Event-Driven Sensor:** [backend/devices/mock_motion_sensor.py](../backend/devices/mock_motion_sensor.py)
- **BaseDevice Source:** [backend/devices/base.py](../backend/devices/base.py)
- **Unit Test Examples:** [tests/unit/devices/](../tests/unit/devices/)

---

**Developer:** Krystian Spiewak  
**Course:** SDEV435 - Capstone Project  
**Institution:** Champlain College
