"""Device management API endpoints.

Provides REST API for CRUD operations on IoT devices, including
registration, updates, status tracking, and deletion.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.deps import get_current_user, require_role
from backend.api.models.device import DeviceCreate, DeviceResponse
from backend.api.models.user import UserResponse
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )
    return device


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device: DeviceCreate,
    _writer: Annotated[UserResponse, Depends(require_role("admin", "user"))],
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device already exists: {device.id}",
        )

    result = await DeviceRepository.create(device)
    return result


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device: DeviceCreate,
    _writer: Annotated[UserResponse, Depends(require_role("admin", "user"))],
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )
    return updated


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    _writer: Annotated[UserResponse, Depends(require_role("admin", "user"))],
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )


@router.patch("/{device_id}/status", response_model=DeviceResponse)
async def update_device_status(
    device_id: str,
    status_update: DeviceStatusUpdate,
    _writer: Annotated[UserResponse, Depends(require_role("admin", "user"))],
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_id}",
        )

    # Fetch updated device
    device = await DeviceRepository.get_by_id(device_id)
    assert device is not None, f"Device {device_id} vanished after successful update"
    return device
