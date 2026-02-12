"""Unit tests for Device Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.api.models.device import DeviceBase, DeviceCreate, DeviceList, DeviceResponse


class TestDeviceBase:
    """Tests for DeviceBase model."""

    def test_valid_device_base(self) -> None:
        """Test creating a valid DeviceBase instance."""
        device = DeviceBase(
            friendly_name="Living Room Light",
            device_type="light",
            manufacturer="Philips",
            model="Hue White",
            capabilities=["power", "brightness"],
        )

        assert device.friendly_name == "Living Room Light"
        assert device.device_type == "light"
        assert device.manufacturer == "Philips"
        assert device.model == "Hue White"
        assert device.capabilities == ["power", "brightness"]

    def test_device_base_minimal(self) -> None:
        """Test DeviceBase with only required fields."""
        device = DeviceBase(  # type: ignore[call-arg]
            friendly_name="Sensor",
            device_type="temperature",
        )

        assert device.friendly_name == "Sensor"
        assert device.device_type == "temperature"
        assert device.manufacturer is None
        assert device.model is None
        assert device.capabilities == []

    def test_device_base_empty_friendly_name_rejected(self) -> None:
        """Test that empty friendly_name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceBase(  # type: ignore[call-arg]
                friendly_name="",
                device_type="light",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("friendly_name",)
        assert "at least 1 character" in errors[0]["msg"]

    def test_device_base_friendly_name_too_long(self) -> None:
        """Test that friendly_name longer than 100 chars is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceBase(  # type: ignore[call-arg]
                friendly_name="A" * 101,
                device_type="light",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("friendly_name",)
        assert "at most 100 characters" in errors[0]["msg"]

    def test_device_base_missing_required_fields(self) -> None:
        """Test that missing required fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceBase()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert len(errors) == 2
        field_names = {error["loc"][0] for error in errors}
        assert field_names == {"friendly_name", "device_type"}


class TestDeviceCreate:
    """Tests for DeviceCreate model."""

    def test_valid_device_create(self) -> None:
        """Test creating a valid DeviceCreate instance."""
        device = DeviceCreate(
            id="light-001",
            friendly_name="Kitchen Light",
            device_type="light",
            mqtt_topic="smartnest/device/light-001/command",
            manufacturer="IKEA",
            model="Tradfri",
            capabilities=["power", "brightness", "color_temp"],
        )

        assert device.id == "light-001"
        assert device.friendly_name == "Kitchen Light"
        assert device.mqtt_topic == "smartnest/device/light-001/command"

    def test_device_create_missing_id(self) -> None:
        """Test that missing id is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceCreate(  # type: ignore[call-arg]
                friendly_name="Light",
                device_type="light",
                mqtt_topic="topic",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)

    def test_device_create_empty_mqtt_topic(self) -> None:
        """Test that empty mqtt_topic is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceCreate(  # type: ignore[call-arg]
                id="light-001",
                friendly_name="Light",
                device_type="light",
                mqtt_topic="",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("mqtt_topic",)


class TestDeviceResponse:
    """Tests for DeviceResponse model."""

    def test_valid_device_response(self) -> None:
        """Test creating a valid DeviceResponse instance."""
        now = datetime.now(UTC)
        device = DeviceResponse(
            id="light-001",
            friendly_name="Bedroom Light",
            device_type="light",
            mqtt_topic="smartnest/device/light-001/command",
            manufacturer="Philips",
            model="Hue",
            capabilities=["power"],
            status="online",
            created_at=now,
            updated_at=now,
            last_seen_at=now,
        )

        assert device.id == "light-001"
        assert device.status == "online"
        assert device.created_at == now
        assert device.last_seen_at == now

    def test_device_response_from_dict(self) -> None:
        """Test creating DeviceResponse from dictionary (simulating DB row)."""
        now = datetime.now(UTC)
        device_data = {
            "id": "sensor-001",
            "friendly_name": "Temperature Sensor",
            "device_type": "temperature",
            "mqtt_topic": "smartnest/sensor/sensor-001/data",
            "manufacturer": None,
            "model": None,
            "capabilities": ["temperature"],
            "status": "online",
            "created_at": now,
            "updated_at": now,
            "last_seen_at": None,
        }

        device = DeviceResponse(**device_data)  # type: ignore[arg-type]

        assert device.id == "sensor-001"
        assert device.manufacturer is None
        assert device.last_seen_at is None

    def test_device_response_missing_required_timestamp(self) -> None:
        """Test that missing required timestamps are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceResponse(
                id="light-001",
                friendly_name="Light",
                device_type="light",
                mqtt_topic="topic",
                capabilities=[],
                status="online",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        missing_fields = {error["loc"][0] for error in errors}
        assert "created_at" in missing_fields
        assert "updated_at" in missing_fields


class TestDeviceList:
    """Tests for DeviceList model."""

    def test_valid_device_list(self) -> None:
        """Test creating a valid DeviceList instance."""
        now = datetime.now(UTC)
        device = DeviceResponse(  # type: ignore[call-arg]
            id="light-001",
            friendly_name="Light",
            device_type="light",
            mqtt_topic="topic",
            capabilities=[],
            status="online",
            created_at=now,
            updated_at=now,
            last_seen_at=None,
        )

        device_list = DeviceList(
            devices=[device],
            total=1,
            page=1,
            page_size=50,
        )

        assert len(device_list.devices) == 1
        assert device_list.total == 1
        assert device_list.page == 1
        assert device_list.page_size == 50

    def test_device_list_empty(self) -> None:
        """Test DeviceList with no devices."""
        device_list = DeviceList(  # type: ignore[call-arg]
            devices=[],
            total=0,
        )

        assert device_list.devices == []
        assert device_list.total == 0
        assert device_list.page == 1  # Default
        assert device_list.page_size == 50  # Default

    def test_device_list_invalid_page(self) -> None:
        """Test that page < 1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceList(  # type: ignore[call-arg]
                devices=[],
                total=0,
                page=0,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("page",) for error in errors)

    def test_device_list_page_size_too_large(self) -> None:
        """Test that page_size > 100 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeviceList(  # type: ignore[call-arg]
                devices=[],
                total=0,
                page_size=101,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("page_size",) for error in errors)
