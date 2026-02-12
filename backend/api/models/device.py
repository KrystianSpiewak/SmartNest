"""Device Pydantic models for API validation and serialization.

Models represent IoT devices in the SmartNest system with their
metadata, capabilities, and status information.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Used at runtime by Pydantic

from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    """Base device fields shared across request/response schemas."""

    friendly_name: str = Field(..., min_length=1, max_length=100)
    device_type: str = Field(..., min_length=1, max_length=50)
    manufacturer: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    firmware_version: str | None = Field(None, max_length=50)
    capabilities: list[str] = Field(default_factory=list)


class DeviceCreate(DeviceBase):
    """Schema for creating a new device (input validation).

    Used when manually registering a device or syncing discovered devices.
    """

    id: str = Field(..., min_length=1, max_length=100)
    mqtt_topic: str = Field(..., min_length=1, max_length=200)


class DeviceResponse(DeviceBase):
    """Schema for device API responses (output serialization).

    Includes all fields from the database, including timestamps and status.
    """

    id: str
    mqtt_topic: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None

    # Configure Pydantic to work with SQLite Row objects
    model_config = ConfigDict(from_attributes=True)


class DeviceList(BaseModel):
    """Paginated list of devices with metadata."""

    devices: list[DeviceResponse]
    total: int
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=100)

    model_config = ConfigDict(from_attributes=True)
