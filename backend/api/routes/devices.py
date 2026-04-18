"""Device management API endpoints.

Provides REST API for CRUD operations on IoT devices, including
registration, updates, status tracking, and deletion.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from backend.api.deps import get_current_user, require_writer_role
from backend.api.errors import raise_conflict, raise_not_found
from backend.api.models.device import DeviceCreate, DeviceResponse
from backend.api.models.user import UserResponse
from backend.database.connection import get_connection
from backend.database.repositories.device import DeviceRepository

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceListResponse(BaseModel):
    """Response model for paginated device listing."""

    devices: list[DeviceResponse]
    total: int
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)


class DeviceCountResponse(BaseModel):
    """Response model for device count."""

    count: int


class DeviceStatusUpdate(BaseModel):
    """Request model for updating device status."""

    status: str = Field(..., min_length=1, max_length=50)


class DeviceCommandRequest(BaseModel):
    """Request model for sending device commands from clients."""

    command: str = Field(..., min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DeviceCommandResponse(BaseModel):
    """Response model for device command execution results."""

    device_id: str
    success: bool
    state: dict[str, Any]


def _default_state_for_device_type(device_type: str) -> dict[str, Any]:
    """Return default state payload for known device categories."""
    if device_type in {"smart_light", "light"}:
        return {
            "power": "off",
            "brightness": 100,
            "color_temperature": 4000,
        }
    return {}


def _apply_command_to_state(
    current_state: dict[str, Any],
    command: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Apply command payload to current device state."""
    next_state = dict(current_state)
    next_state.update(parameters)

    if command == "set_power" and "power" in next_state:
        power_value = next_state["power"]
        if isinstance(power_value, bool):
            next_state["power"] = "on" if power_value else "off"

    next_state["last_command"] = command
    return next_state


async def _load_device_state(device_id: str) -> dict[str, Any] | None:
    """Load persisted device state from database."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT state FROM device_state WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()

    if not row or not row["state"]:
        return None

    loaded = json.loads(row["state"])
    return loaded if isinstance(loaded, dict) else {}


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=100)] = 20,
) -> DeviceListResponse:
    """
    List all devices with pagination.

    Args:
        page: Page number (1-indexed, default: 1)
        page_size: Number of devices per page (default: 20, max: 100)

    Returns:
        Paginated list of devices with total count
    """
    skip = (page - 1) * page_size
    devices = await DeviceRepository.get_all(skip=skip, limit=page_size)
    total = await DeviceRepository.count()

    return DeviceListResponse(
        devices=devices,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/count", response_model=DeviceCountResponse)
async def get_device_count(
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> DeviceCountResponse:
    """
    Get total count of registered devices.

    Returns:
        Total number of devices in the system
    """
    count = await DeviceRepository.count()
    return DeviceCountResponse(count=count)


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> DeviceResponse:
    """
    Get device by ID.

    Args:
        device_id: Unique device identifier

    Returns:
        Device details

    Raises:
        HTTPException: 404 if device not found
    """
    device = await DeviceRepository.get_by_id(device_id)
    if not device:
        raise_not_found(f"Device not found: {device_id}")
    return device


@router.get("/{device_id}/state")
async def get_device_state(
    device_id: str,
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get current persisted state for a device."""
    device = await DeviceRepository.get_by_id(device_id)
    if not device:
        raise_not_found(f"Device not found: {device_id}")

    state = await _load_device_state(device_id)
    if state is None:
        return _default_state_for_device_type(device.device_type)
    return state


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device: DeviceCreate,
    _writer: Annotated[UserResponse, Depends(require_writer_role)],
) -> DeviceResponse:
    """
    Register a new device.

    Args:
        device: Device details for registration

    Returns:
        Created device with timestamps

    Raises:
        HTTPException: 409 if device ID already exists
    """
    # Check if device already exists
    existing = await DeviceRepository.get_by_id(device.id)
    if existing:
        raise_conflict(f"Device already exists: {device.id}")

    result = await DeviceRepository.create(device)
    return result


@router.post("/{device_id}/command", response_model=DeviceCommandResponse)
async def send_device_command(
    device_id: str,
    command_request: DeviceCommandRequest,
    _writer: Annotated[UserResponse, Depends(require_writer_role)],
) -> DeviceCommandResponse:
    """Persist command effects to device state for UI/runtime consumption."""
    device = await DeviceRepository.get_by_id(device_id)
    if not device:
        raise_not_found(f"Device not found: {device_id}")

    current_state = await _load_device_state(device_id)
    if current_state is None:
        current_state = _default_state_for_device_type(device.device_type)

    next_state = _apply_command_to_state(
        current_state,
        command_request.command,
        command_request.parameters,
    )

    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO device_state (device_id, state, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(device_id) DO UPDATE SET
                state = excluded.state,
                updated_at = excluded.updated_at
            """,
            (device_id, json.dumps(next_state)),
        )
        await conn.commit()

    return DeviceCommandResponse(device_id=device_id, success=True, state=next_state)


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device: DeviceCreate,
    _writer: Annotated[UserResponse, Depends(require_writer_role)],
) -> DeviceResponse:
    """
    Update an existing device.

    Args:
        device_id: Device identifier to update
        device: New device details

    Returns:
        Updated device

    Raises:
        HTTPException: 404 if device not found
    """
    updated = await DeviceRepository.update(device_id, device)
    if not updated:
        raise_not_found(f"Device not found: {device_id}")
    return updated


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    _writer: Annotated[UserResponse, Depends(require_writer_role)],
) -> None:
    """
    Delete a device.

    Args:
        device_id: Device identifier to delete

    Raises:
        HTTPException: 404 if device not found
    """
    deleted = await DeviceRepository.delete(device_id)
    if not deleted:
        raise_not_found(f"Device not found: {device_id}")


@router.patch("/{device_id}/status", response_model=DeviceResponse)
async def update_device_status(
    device_id: str,
    status_update: DeviceStatusUpdate,
    _writer: Annotated[UserResponse, Depends(require_writer_role)],
) -> DeviceResponse:
    """
    Update device status (online/offline/error).

    Args:
        device_id: Device identifier
        status_update: New status value

    Returns:
        Updated device

    Raises:
        HTTPException: 404 if device not found
    """
    # Update status and last_seen timestamp
    success = await DeviceRepository.update_status(device_id, status_update.status)
    if not success:
        raise_not_found(f"Device not found: {device_id}")

    # Fetch updated device
    device = await DeviceRepository.get_by_id(device_id)
    assert device is not None, f"Device {device_id} vanished after successful update"
    return device
