"""Integration tests for device API endpoints.

Tests the complete request/response cycle for device CRUD operations
using FastAPI TestClient.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_current_user
from backend.api.models.user import UserResponse
from backend.app import app
from backend.database.connection import get_connection, init_database

_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

_ADMIN_USER = UserResponse(
    id=99,
    username="admin",
    email="admin@example.com",
    role="admin",
    is_active=True,
    created_at=_NOW,
    updated_at=_NOW,
    last_login_at=None,
)


async def _override_get_current_user() -> UserResponse:
    """Return a fake admin user for integration tests."""
    return _ADMIN_USER


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Create a test client with auth dependency overridden."""
    app.dependency_overrides[get_current_user] = _override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def setup_database() -> None:
    """Initialize database and clean up before each test."""
    await init_database()
    # Clean up devices table before each test to ensure test isolation
    async with get_connection() as conn:
        await conn.execute("DELETE FROM devices")
        await conn.commit()


class TestListDevices:
    """Tests for GET /api/devices - list devices endpoint."""

    def test_list_devices_empty(self, client: TestClient) -> None:
        """Test listing devices when database is empty."""
        response = client.get("/api/devices")

        assert response.status_code == 200
        data = response.json()
        assert data["devices"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_devices_with_pagination(self, client: TestClient) -> None:
        """Test pagination parameters."""
        # Create a device first
        device_data = {
            "id": "light-001",
            "friendly_name": "Test Light",
            "device_type": "light",
            "mqtt_topic": "test/light",
            "manufacturer": "Test Corp",
            "model": "Test Model",
            "firmware_version": "1.0.0",
            "capabilities": ["power"],
        }
        client.post("/api/devices", json=device_data)

        # Test pagination
        response = client.get("/api/devices?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] == 1
        assert len(data["devices"]) == 1

    def test_list_devices_invalid_page(self, client: TestClient) -> None:
        """Test invalid page number."""
        response = client.get("/api/devices?page=0")

        assert response.status_code == 422  # Validation error

    def test_list_devices_invalid_page_size(self, client: TestClient) -> None:
        """Test page size exceeds maximum."""
        response = client.get("/api/devices?page_size=200")

        assert response.status_code == 422  # Validation error


class TestGetDevice:
    """Tests for GET /api/devices/{device_id} - get device by ID."""

    def test_get_device_success(self, client: TestClient) -> None:
        """Test getting an existing device."""
        # Create device
        device_data = {
            "id": "sensor-001",
            "friendly_name": "Temp Sensor",
            "device_type": "sensor",
            "mqtt_topic": "test/sensor",
            "manufacturer": "SensorCo",
            "model": "TMP100",
            "firmware_version": "2.0.0",
            "capabilities": ["temperature"],
        }
        create_response = client.post("/api/devices", json=device_data)
        assert create_response.status_code == 201

        # Get device
        response = client.get("/api/devices/sensor-001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "sensor-001"
        assert data["friendly_name"] == "Temp Sensor"
        assert data["device_type"] == "sensor"
        assert data["status"] == "offline"

    def test_get_device_not_found(self, client: TestClient) -> None:
        """Test getting non-existent device."""
        response = client.get("/api/devices/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateDevice:
    """Tests for POST /api/devices - create device."""

    def test_create_device_success(self, client: TestClient) -> None:
        """Test creating a new device."""
        device_data = {
            "id": "light-create-001",
            "friendly_name": "Living Room Light",
            "device_type": "light",
            "mqtt_topic": "smartnest/light/001",
            "manufacturer": "Philips",
            "model": "Hue",
            "firmware_version": "3.0.0",
            "capabilities": ["power", "brightness"],
        }

        response = client.post("/api/devices", json=device_data)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "light-create-001"
        assert data["friendly_name"] == "Living Room Light"
        assert data["status"] == "offline"
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_device_duplicate(self, client: TestClient) -> None:
        """Test creating device with duplicate ID."""
        device_data = {
            "id": "duplicate-001",
            "friendly_name": "First Device",
            "device_type": "light",
            "mqtt_topic": "test/light",
            "manufacturer": "Test",
            "model": "Model",
            "firmware_version": "1.0.0",
            "capabilities": [],
        }

        # Create first device
        response1 = client.post("/api/devices", json=device_data)
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = client.post("/api/devices", json=device_data)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    def test_create_device_minimal_fields(self, client: TestClient) -> None:
        """Test creating device with only required fields."""
        device_data = {
            "id": "minimal-001",
            "friendly_name": "Minimal Device",
            "device_type": "sensor",
            "mqtt_topic": "test/minimal",
        }

        response = client.post("/api/devices", json=device_data)

        assert response.status_code == 201
        data = response.json()
        assert data["manufacturer"] is None
        assert data["model"] is None
        assert data["firmware_version"] is None
        assert data["capabilities"] == []

    def test_create_device_invalid_data(self, client: TestClient) -> None:
        """Test creating device with missing required fields."""
        device_data = {
            "id": "invalid-001",
            # Missing friendly_name, device_type, mqtt_topic
        }

        response = client.post("/api/devices", json=device_data)

        assert response.status_code == 422  # Validation error


class TestUpdateDevice:
    """Tests for PUT /api/devices/{device_id} - update device."""

    def test_update_device_success(self, client: TestClient) -> None:
        """Test updating an existing device."""
        # Create device
        create_data = {
            "id": "update-001",
            "friendly_name": "Original Name",
            "device_type": "light",
            "mqtt_topic": "test/light",
            "manufacturer": "OldCorp",
            "model": "OldModel",
            "firmware_version": "1.0.0",
            "capabilities": ["power"],
        }
        client.post("/api/devices", json=create_data)

        # Update device
        update_data = {
            "id": "update-001",  # ID in body (ignored for update)
            "friendly_name": "Updated Name",
            "device_type": "light",
            "mqtt_topic": "test/light/updated",
            "manufacturer": "NewCorp",
            "model": "NewModel",
            "firmware_version": "2.0.0",
            "capabilities": ["power", "brightness"],
        }
        response = client.put("/api/devices/update-001", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["friendly_name"] == "Updated Name"
        assert data["manufacturer"] == "NewCorp"
        assert data["firmware_version"] == "2.0.0"

    def test_update_device_not_found(self, client: TestClient) -> None:
        """Test updating non-existent device."""
        update_data = {
            "id": "nonexistent",
            "friendly_name": "Test",
            "device_type": "light",
            "mqtt_topic": "test/light",
            "manufacturer": "Test",
            "model": "Test",
            "firmware_version": "1.0.0",
            "capabilities": [],
        }

        response = client.put("/api/devices/nonexistent", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteDevice:
    """Tests for DELETE /api/devices/{device_id} - delete device."""

    def test_delete_device_success(self, client: TestClient) -> None:
        """Test deleting an existing device."""
        # Create device
        device_data = {
            "id": "delete-001",
            "friendly_name": "To Delete",
            "device_type": "sensor",
            "mqtt_topic": "test/sensor",
            "manufacturer": "Test",
            "model": "Test",
            "firmware_version": "1.0.0",
            "capabilities": [],
        }
        client.post("/api/devices", json=device_data)

        # Delete device
        response = client.delete("/api/devices/delete-001")

        assert response.status_code == 204

        # Verify device is gone
        get_response = client.get("/api/devices/delete-001")
        assert get_response.status_code == 404

    def test_delete_device_not_found(self, client: TestClient) -> None:
        """Test deleting non-existent device."""
        response = client.delete("/api/devices/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetDeviceCount:
    """Tests for GET /api/devices/count - get device count."""

    def test_get_count_empty(self, client: TestClient) -> None:
        """Test count when no devices exist."""
        response = client.get("/api/devices/count")

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_get_count_with_devices(self, client: TestClient) -> None:
        """Test count with multiple devices."""
        # Create 3 devices
        for i in range(3):
            device_data = {
                "id": f"count-{i:03d}",
                "friendly_name": f"Device {i}",
                "device_type": "sensor",
                "mqtt_topic": f"test/{i}",
                "manufacturer": "Test",
                "model": "Test",
                "firmware_version": "1.0.0",
                "capabilities": [],
            }
            client.post("/api/devices", json=device_data)

        response = client.get("/api/devices/count")

        assert response.status_code == 200
        assert response.json()["count"] == 3


class TestUpdateDeviceStatus:
    """Tests for PATCH /api/devices/{device_id}/status - update status."""

    def test_update_status_success(self, client: TestClient) -> None:
        """Test updating device status."""
        # Create device
        device_data = {
            "id": "status-001",
            "friendly_name": "Status Test",
            "device_type": "light",
            "mqtt_topic": "test/light",
            "manufacturer": "Test",
            "model": "Test",
            "firmware_version": "1.0.0",
            "capabilities": [],
        }
        client.post("/api/devices", json=device_data)

        # Update status
        status_data = {"status": "online"}
        response = client.patch("/api/devices/status-001/status", json=status_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["last_seen_at"] is not None

    def test_update_status_not_found(self, client: TestClient) -> None:
        """Test updating status of non-existent device."""
        status_data = {"status": "online"}
        response = client.patch("/api/devices/nonexistent/status", json=status_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_status_invalid_data(self, client: TestClient) -> None:
        """Test updating status with invalid data."""
        # Create device
        device_data = {
            "id": "status-invalid-001",
            "friendly_name": "Status Test",
            "device_type": "light",
            "mqtt_topic": "test/light",
            "manufacturer": "Test",
            "model": "Test",
            "firmware_version": "1.0.0",
            "capabilities": [],
        }
        client.post("/api/devices", json=device_data)

        # Try to update with empty status
        status_data = {"status": ""}
        response = client.patch("/api/devices/status-invalid-001/status", json=status_data)

        assert response.status_code == 422  # Validation error


class TestDeviceStateAndCommands:
    """Tests for device state and command endpoints used by TUI device detail."""

    def test_get_device_state_returns_default_for_light(self, client: TestClient) -> None:
        """New light devices return a default light state when no state exists yet."""
        device_data = {
            "id": "state-default-001",
            "friendly_name": "State Default Light",
            "device_type": "smart_light",
            "mqtt_topic": "smartnest/device/state-default-001/state",
            "manufacturer": "Test",
            "model": "Light",
            "firmware_version": "1.0.0",
            "capabilities": ["power", "brightness"],
        }
        create_response = client.post("/api/devices", json=device_data)
        assert create_response.status_code == 201

        response = client.get("/api/devices/state-default-001/state")

        assert response.status_code == 200
        body = response.json()
        assert body["power"] == "off"
        assert body["brightness"] == 100
        assert body["color_temperature"] == 4000

    def test_get_device_state_returns_empty_default_for_unknown_type(
        self, client: TestClient
    ) -> None:
        """Non-light devices return an empty default state when no state is persisted."""
        device_data = {
            "id": "state-default-unknown-001",
            "friendly_name": "State Default Unknown",
            "device_type": "sensor",
            "mqtt_topic": "smartnest/device/state-default-unknown-001/state",
            "manufacturer": "Test",
            "model": "Sensor",
            "firmware_version": "1.0.0",
            "capabilities": ["temperature"],
        }
        create_response = client.post("/api/devices", json=device_data)
        assert create_response.status_code == 201

        response = client.get("/api/devices/state-default-unknown-001/state")

        assert response.status_code == 200
        assert response.json() == {}

    def test_get_device_state_not_found(self, client: TestClient) -> None:
        """State endpoint returns 404 for unknown device IDs."""
        response = client.get("/api/devices/unknown-state-device/state")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_send_device_command_updates_state(self, client: TestClient) -> None:
        """Command endpoint persists updated state and returns command result."""
        device_data = {
            "id": "cmd-001",
            "friendly_name": "Command Light",
            "device_type": "smart_light",
            "mqtt_topic": "smartnest/device/cmd-001/state",
            "manufacturer": "Test",
            "model": "Light",
            "firmware_version": "1.0.0",
            "capabilities": ["power", "brightness"],
        }
        create_response = client.post("/api/devices", json=device_data)
        assert create_response.status_code == 201

        command_response = client.post(
            "/api/devices/cmd-001/command",
            json={"command": "set_brightness", "parameters": {"brightness": 80}},
        )

        assert command_response.status_code == 200
        command_body = command_response.json()
        assert command_body["device_id"] == "cmd-001"
        assert command_body["success"] is True
        assert command_body["state"]["brightness"] == 80
        assert command_body["state"]["last_command"] == "set_brightness"

        state_response = client.get("/api/devices/cmd-001/state")
        assert state_response.status_code == 200
        state_body = state_response.json()
        assert state_body["brightness"] == 80
        assert state_body["last_command"] == "set_brightness"

    def test_send_device_command_set_power_bool_normalized(self, client: TestClient) -> None:
        """Boolean power values are normalized to on/off strings for TUI rendering."""
        device_data = {
            "id": "cmd-002",
            "friendly_name": "Power Command Light",
            "device_type": "smart_light",
            "mqtt_topic": "smartnest/device/cmd-002/state",
            "manufacturer": "Test",
            "model": "Light",
            "firmware_version": "1.0.0",
            "capabilities": ["power"],
        }
        create_response = client.post("/api/devices", json=device_data)
        assert create_response.status_code == 201

        command_response = client.post(
            "/api/devices/cmd-002/command",
            json={"command": "set_power", "parameters": {"power": True}},
        )

        assert command_response.status_code == 200
        body = command_response.json()
        assert body["state"]["power"] == "on"

    def test_send_device_command_uses_existing_state_and_keeps_non_bool_power(
        self,
        client: TestClient,
    ) -> None:
        """Existing state is reused and string power values bypass bool normalization."""
        device_data = {
            "id": "cmd-003",
            "friendly_name": "Command Existing State",
            "device_type": "smart_light",
            "mqtt_topic": "smartnest/device/cmd-003/state",
            "manufacturer": "Test",
            "model": "Light",
            "firmware_version": "1.0.0",
            "capabilities": ["power", "brightness"],
        }
        create_response = client.post("/api/devices", json=device_data)
        assert create_response.status_code == 201

        first_command = client.post(
            "/api/devices/cmd-003/command",
            json={"command": "set_brightness", "parameters": {"brightness": 55}},
        )
        assert first_command.status_code == 200

        second_command = client.post(
            "/api/devices/cmd-003/command",
            json={"command": "set_power", "parameters": {"power": "on"}},
        )

        assert second_command.status_code == 200
        body = second_command.json()
        assert body["state"]["brightness"] == 55
        assert body["state"]["power"] == "on"
        assert body["state"]["last_command"] == "set_power"

    def test_send_device_command_not_found(self, client: TestClient) -> None:
        """Command endpoint returns 404 for unknown device IDs."""
        response = client.post(
            "/api/devices/unknown-command-device/command",
            json={"command": "set_power", "parameters": {"power": "on"}},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
