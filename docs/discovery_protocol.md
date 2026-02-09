# SmartNest Device Discovery Protocol Specification

**Version:** 1.0  
**Phase:** 2 - Device Ecosystem (In-Memory Registry)  
**Protocol:** MQTT-based device announcement and registration  
**Last Updated:** February 8, 2026

---

## Overview

The SmartNest Discovery Protocol enables automatic device registration through MQTT topic announcements. When a device starts, it publishes a discovery message containing metadata and capabilities. The `DiscoveryConsumer` service subscribes to discovery announcements and maintains an in-memory registry of discovered devices.

**Design Rationale:** This protocol is inspired by [Home Assistant's MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery) but simplified for SmartNest's Phase 2 requirements. Database persistence will be added in Phase 3 (Backend API).

---

## Table of Contents

1. [Protocol Flow](#protocol-flow)
2. [MQTT Topics](#mqtt-topics)
3. [Message Format](#message-format)
4. [Required Fields](#required-fields)
5. [Discovery Consumer](#discovery-consumer)
6. [Device Implementation](#device-implementation)
7. [Message Examples](#message-examples)
8. [QoS and Retention](#qos-and-retention)
9. [Error Handling](#error-handling)
10. [Phase 3 Migration](#phase-3-migration)

---

## Protocol Flow

```
┌──────────────┐          ┌──────────────┐         ┌───────────────────┐
│  IoT Device  │          │ MQTT Broker  │         │DiscoveryConsumer  │
│ (MockLight)  │          │  (HiveMQ)    │         │  (Backend)        │
└──────┬───────┘          └──────┬───────┘         └─────────┬─────────┘
       │                         │                           │
       │ 1. start()              │                           │
       │────────────────────────>│                           │
       │                         │                           │
       │ 2. PUBLISH discovery    │                           │
       │    (retained, QoS 1)    │                           │
       │────────────────────────>│                           │
       │                         │                           │
       │                         │ 3. MQTT message           │
       │                         │──────────────────────────>│
       │                         │                           │
       │                         │ 4. Validate payload       │
       │                         │      (Pydantic)           │
       │                         │<──────────────────────────│
       │                         │                           │
       │                         │ 5. Register in memory     │
       │                         │      (thread-safe dict)   │
       │                         │<──────────────────────────│
       │                         │                           │
       │ 6. Device registered    │                           │
       │    (log event)          │                           │
       │<────────────────────────────────────────────────────│
```

### Sequence

1. **Device Startup:** Device calls `BaseDevice.start()` which connects to the MQTT broker
2. **Discovery Publish:** Device publishes discovery message to `smartnest/discovery/announce` (retained, QoS 1)
3. **Message Delivery:** Broker delivers discovery message to all subscribers
4. **Validation:** `DiscoveryConsumer` validates the payload using Pydantic `DeviceDiscoveryMessage` model
5. **Registration:** Valid devices are stored in the consumer's thread-safe in-memory registry
6. **Logging:** Registration events are logged with structured logging for observability

---

## MQTT Topics

### Discovery Announcement Topic

**Topic Pattern:** `smartnest/discovery/announce`

- **Purpose:** All devices publish their discovery payload to this single topic
- **QoS:** 1 (at least once delivery)
- **Retained:** Yes (new consumers see existing devices immediately)
- **Payload:** JSON-encoded `DeviceDiscoveryMessage`

**Topic Construction:**
```python
from backend.mqtt.topics import TopicBuilder

topic = TopicBuilder.discovery_topic()
# Returns: "smartnest/discovery/announce"
```

**Why a Single Topic?**
- Simplifies consumer subscription (one topic vs. wildcard)
- Enables atomic registry updates (no race conditions)
- Retained messages persist device state across broker restarts
- Follows Home Assistant's proven pattern

---

## Message Format

### JSON Schema

```json
{
  "device_id": "light_01",
  "name": "Living Room Light",
  "device_type": "smart_light",
  "capabilities": ["power", "brightness", "color_temp"],
  "topics": {
    "command": "smartnest/device/light_01/command",
    "state": "smartnest/device/light_01/state"
  },
  "metadata": {
    "manufacturer": "SmartNest",
    "model": "Mock Light v1.0"
  }
}
```

### Pydantic Model

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.mqtt.topics import validate_device_id

class DeviceDiscoveryMessage(BaseModel):
    """Validated discovery payload from a device announcement."""
    
    model_config = ConfigDict(frozen=True, extra="allow")
    
    device_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    topics: dict[str, str] = Field(default_factory=dict)
    
    @field_validator("device_id")
    @classmethod
    def _validate_device_id(cls, v: str) -> str:
        """Ensure device_id is valid for MQTT topics."""
        validate_device_id(v)
        return v
```

**Key Features:**
- **Frozen:** Immutable after creation (prevents accidental mutation)
- **Extra Fields Allowed:** Devices can include custom metadata beyond required fields
- **Validated device_id:** No MQTT wildcards (`+`, `#`) or invalid characters
- **Type Safety:** All fields are type-checked at runtime

---

## Required Fields

### Core Identity Fields

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `device_id` | `str` | ✅ Yes | `min_length=1`, no MQTT wildcards | Unique device identifier |
| `name` | `str` | ✅ Yes | `min_length=1` | Human-readable device name |
| `device_type` | `str` | ✅ Yes | `min_length=1` | Device category (e.g. "smart_light") |
| `capabilities` | `list[str]` | ⚠️ Optional | Defaults to `[]` | List of supported capabilities |
| `topics` | `dict[str, str]` | ⚠️ Optional | Defaults to `{}` | MQTT topic map |

### Capabilities Field

**Purpose:** Advertise device features to consumers.

**Examples:**
- Smart Light: `["power", "brightness", "color_temp"]`
- Temperature Sensor: `["temperature"]`
- Motion Sensor: `["motion", "last_triggered"]`
- Smart Switch: `["power", "toggle"]`

**Usage:** Enables UI to dynamically generate control interfaces based on capabilities.

### Topics Field

**Purpose:** Map topic types to actual MQTT topics.

**Common Keys:**
- `command` - Topic where device receives commands
- `state` - Topic where device publishes state updates
- `sensor_data` - Topic where sensors publish readings

**Example:**
```json
{
  "topics": {
    "command": "smartnest/device/light_01/command",
    "state": "smartnest/device/light_01/state"
  }
}
```

### Optional Metadata

Devices can include arbitrary additional fields:

```json
{
  "metadata": {
    "manufacturer": "SmartNest",
    "model": "Mock Light v1.0",
    "firmware_version": "2.0.1",
    "hardware_revision": "A1"
  },
  "location": {
    "room": "Living Room",
    "floor": 1
  }
}
```

**Note:** The `extra="allow"` model config permits additional fields without validation errors.

---

## Discovery Consumer

### Implementation

```python
from backend.mqtt.discovery import DiscoveryConsumer

# Create consumer with MQTT client
client = SmartNestMQTTClient(config)
client.connect()

consumer = DiscoveryConsumer(client)
consumer.start()

# ... devices publish discovery messages ...

# Query discovered devices
devices = consumer.get_discovered_devices()
device = consumer.get_device("light_01")
count = consumer.device_count

# Stop consumer
consumer.stop()
```

### Registry API

#### `start() -> None`

**Purpose:** Subscribe to discovery topic and begin receiving announcements.

**Behavior:**
- Subscribes to `smartnest/discovery/announce` with QoS 1
- Registers `_on_discovery_message` callback
- Idempotent (safe to call multiple times)

#### `stop() -> None`

**Purpose:** Unsubscribe from discovery topic and stop processing.

**Behavior:**
- Removes discovery topic handler
- Registry remains in memory (does not clear devices)
- Idempotent (safe to call multiple times)

#### `get_discovered_devices() -> list[DeviceDiscoveryMessage]`

**Purpose:** Return a snapshot of all registered devices.

**Returns:** List of immutable `DeviceDiscoveryMessage` objects (copy, not reference).

**Thread-Safety:** Uses lock to prevent race conditions.

#### `get_device(device_id: str) -> DeviceDiscoveryMessage | None`

**Purpose:** Retrieve a specific device by ID.

**Returns:** 
- `DeviceDiscoveryMessage` if device exists
- `None` if device not found

**Logging:** Logs `DEVICE_NOT_FOUND` debug message if device doesn't exist.

#### `device_count -> int`

**Purpose:** Get count of registered devices.

**Thread-Safety:** Uses lock to ensure accurate count.

---

## Device Implementation

### Using BaseDevice

All devices inheriting from `BaseDevice` automatically publish discovery:

```python
from backend.devices.base import BaseDevice
from backend.mqtt.topics import TopicBuilder

class MyDevice(BaseDevice):
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
```

**Automatic Behavior:**
- `BaseDevice.start()` calls `_publish_discovery()` after connecting
- Discovery message is published with QoS 1, retained flag set
- Logs `DEVICE_DISCOVERY_PUBLISHED` on success
- Logs `DEVICE_DISCOVERY_FAILED` on error (but device still starts)

### Manual Publishing

If not using `BaseDevice`, publish discovery manually:

```python
import json
from backend.mqtt.topics import TopicBuilder

def publish_discovery(client: SmartNestMQTTClient, device_id: str):
    payload = {
        "device_id": device_id,
        "name": "My Device",
        "device_type": "sensor",
        "capabilities": ["temperature"],
        "topics": {
            "sensor_data": TopicBuilder.sensor_topic(device_id, "data"),
        },
    }
    
    topic = TopicBuilder.discovery_topic()
    client.publish(topic, payload, qos=1, retain=True)
```

---

## Message Examples

### Smart Light

```json
{
  "device_id": "light_01",
  "name": "Living Room Light",
  "device_type": "smart_light",
  "capabilities": ["power", "brightness", "color_temp"],
  "topics": {
    "command": "smartnest/device/light_01/command",
    "state": "smartnest/device/light_01/state"
  },
  "metadata": {
    "manufacturer": "SmartNest",
    "model": "Mock Light v1.0"
  }
}
```

### Temperature Sensor

```json
{
  "device_id": "temp_sensor_01",
  "name": "Kitchen Temperature Sensor",
  "device_type": "temperature_sensor",
  "capabilities": ["temperature"],
  "topics": {
    "sensor_data": "smartnest/sensor/temp_sensor_01/data"
  },
  "config": {
    "update_interval": 30,
    "unit": "°F"
  }
}
```

### Motion Sensor

```json
{
  "device_id": "motion_01",
  "name": "Front Door Motion Sensor",
  "device_type": "motion_sensor",
  "capabilities": ["motion", "last_triggered"],
  "topics": {
    "sensor_data": "smartnest/sensor/motion_01/data",
    "command": "smartnest/device/motion_01/command"
  },
  "config": {
    "cooldown_seconds": 5
  }
}
```

---

## QoS and Retention

### Quality of Service (QoS)

**Discovery Messages:** QoS 1 (At Least Once)

**Rationale:**
- QoS 0 (At Most Once): Too unreliable — discovery messages could be lost during network issues
- QoS 1 (At Least Once): ✅ Guarantees delivery, acceptable duplicate handling
- QoS 2 (Exactly Once): Overkill — duplicate discovery messages are idempotent (registry update)

**Trade-offs:**
- QoS 1 may deliver duplicates → Handled by using device_id as registry key (last write wins)
- QoS 2 would add overhead without meaningful benefit for discovery

### Message Retention

**Discovery Messages:** Retained = True

**Rationale:**
- **Late Joiners:** New `DiscoveryConsumer` instances immediately see existing devices
- **Broker Restarts:** Devices remain discoverable without republishing
- **Stateless Backend:** Phase 2 doesn't persist devices to database — retained messages provide durability

**Behavior:**
- Broker stores the most recent discovery message for each device
- When consumer subscribes, broker sends all retained discovery messages
- Devices can update discovery by republishing (overwrites retained message)

**Cleanup:** Set retained message to empty payload to remove:
```python
client.publish(TopicBuilder.discovery_topic(), {}, qos=1, retain=True)
```

---

## Error Handling

### Invalid Payload Structure

**Scenario:** Discovery message is not valid JSON.

**Handling:**
```python
try:
    raw_data = json.loads(message.payload.decode("utf-8"))
except (json.JSONDecodeError, UnicodeDecodeError) as err:
    log_with_code(
        logger,
        "error",
        MessageCode.DEVICE_REGISTRATION_FAILED,
        error=str(err),
    )
    return  # Skip invalid message
```

### Missing Required Fields

**Scenario:** Payload lacks required fields (device_id, name, device_type).

**Handling:**
```python
from pydantic import ValidationError

try:
    discovery_msg = DeviceDiscoveryMessage(**raw_data)
except ValidationError as err:
    log_with_code(
        logger,
        "error",
        MessageCode.DEVICE_REGISTRATION_FAILED,
        error=str(err),
        raw_data=raw_data,
    )
    return  # Skip invalid payload
```

**Logged Information:**
- Error details from Pydantic
- Raw payload (truncated for logging)
- Message code: `DEVICE_REGISTRATION_FAILED`

### Invalid device_id

**Scenario:** device_id contains MQTT wildcards (`+`, `#`) or other invalid characters.

**Handling:**
- Detected by `@field_validator("device_id")` in `DeviceDiscoveryMessage`
- Raises `ValueError` caught by Pydantic `ValidationError`
- Logged as `DEVICE_REGISTRATION_FAILED`

**Example:**
```python
# This will fail validation:
{"device_id": "light+01", "name": "Light", "device_type": "light"}

# Error: ValueError("device_id cannot contain MQTT wildcards (+ or #)")
```

### Duplicate Announcements

**Scenario:** Device republishes discovery (e.g., after reconnection).

**Handling:**
- Uses `device_id` as dictionary key
- New announcement overwrites previous entry (last write wins)
- Logs `DEVICE_ALREADY_REGISTERED` debug message on updates
- No error condition — duplicate announcements are idempotent

---

## Phase 3 Migration

### Current State (Phase 2)

**Storage:** In-memory dictionary (`Dict[str, DeviceDiscoveryMessage]`)

**Limitations:**
- ❌ No persistence across restarts
- ❌ No historical data
- ❌ No multi-instance backend support (each instance has independent registry)

**Benefits:**
- ✅ Simple implementation
- ✅ Fast lookups (O(1))
- ✅ No database dependency during Phase 2

### Future State (Phase 3)

**Storage:** SQLite database with `devices` table

**Planned Schema:**
```sql
CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    capabilities JSON,
    topics JSON,
    metadata JSON,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Migration Path:**
1. Add database layer in Phase 3 (Backend API)
2. `DiscoveryConsumer` writes to both memory and database
3. UI reads from database via REST API
4. Deprecate direct registry access

**Backward Compatibility:**
- `DeviceDiscoveryMessage` model remains unchanged
- `get_discovered_devices()` API stays the same (data source changes underneath)

---

## Testing

### Unit Test Example

```python
from backend.mqtt.discovery import DiscoveryConsumer, DeviceDiscoveryMessage

def test_device_registration():
    """DiscoveryConsumer registers valid devices."""
    client = SmartNestMQTTClient(MQTTConfig(broker="localhost"))
    client.connect()
    
    consumer = DiscoveryConsumer(client)
    consumer.start()
    
    # Simulate discovery message
    payload = {
        "device_id": "test_device",
        "name": "Test Device",
        "device_type": "sensor",
        "capabilities": ["temp"],
    }
    
    consumer._register_device(payload)
    
    # Verify registration
    assert consumer.device_count == 1
    device = consumer.get_device("test_device")
    assert device is not None
    assert device.name == "Test Device"
    
    consumer.stop()
```

### Integration Test Example

```python
@pytest.mark.skipif(not _broker_available(), reason="Broker not running")
def test_discovery_end_to_end():
    """Test full discovery flow with real broker."""
    config = MQTTConfig(broker="localhost")
    
    # Start consumer
    consumer_client = SmartNestMQTTClient(config.with_client_id("consumer"))
    consumer_client.connect()
    consumer = DiscoveryConsumer(consumer_client)
    consumer.start()
    
    # Start device (triggers discovery)
    device = MockSmartLight(
        device_id="test_light",
        name="Test Light",
        config=config.with_client_id("test_light"),
    )
    device.start()
    
    # Wait for message propagation
    time.sleep(0.5)
    
    # Verify device was discovered
    discovered = consumer.get_device("test_light")
    assert discovered is not None
    assert discovered.device_type == "smart_light"
    
    # Cleanup
    device.stop()
    consumer.stop()
```

---

## References

- **Implementation:** [backend/mqtt/discovery.py](../backend/mqtt/discovery.py)
- **Model:** `DeviceDiscoveryMessage` class (lines 48-72)
- **Consumer:** `DiscoveryConsumer` class (lines 75-225)
- **Base Device:** [backend/devices/base.py](../backend/devices/base.py) (lines 195-205)
- **Tests:** [tests/unit/devices/test_discovery.py](../tests/unit/devices/test_discovery.py)
- **Home Assistant Reference:** [MQTT Discovery Documentation](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)

---

**Developer:** Krystian Spiewak  
**Course:** SDEV435 - Capstone Project  
**Institution:** Champlain College
