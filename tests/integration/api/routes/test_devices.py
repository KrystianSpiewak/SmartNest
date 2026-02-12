"""Integration tests for device API endpoints.

Tests the complete request/response cycle for device CRUD operations
using FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.database.connection import get_connection, init_database


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


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
