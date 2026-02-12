"""
Device repository for database operations.

Provides CRUD operations for IoT devices in the SmartNest system.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from backend.api.models.device import DeviceCreate, DeviceResponse
from backend.database.connection import get_connection

if TYPE_CHECKING:
    import aiosqlite


class DeviceRepository:
    """Repository for device database operations."""

    @staticmethod
    async def create(device: DeviceCreate) -> DeviceResponse:
        """
        Create a new device in the database.

        Args:
            device: Device data to create

        Returns:
            Created device with timestamps

        Raises:
            aiosqlite.IntegrityError: If device ID already exists
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        capabilities_json = json.dumps(device.capabilities)

        await conn.execute(
            """
            INSERT INTO devices (
                id, friendly_name, device_type, manufacturer, model,
                firmware_version, mqtt_topic, capabilities_json, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device.id,
                device.friendly_name,
                device.device_type,
                device.manufacturer,
                device.model,
                device.firmware_version,
                device.mqtt_topic,
                capabilities_json,
                "offline",  # Default status
                now.isoformat(),
                now.isoformat(),
            ),
        )
        await conn.commit()

        return DeviceResponse(
            id=device.id,
            friendly_name=device.friendly_name,
            device_type=device.device_type,
            manufacturer=device.manufacturer,
            model=device.model,
            firmware_version=device.firmware_version,
            mqtt_topic=device.mqtt_topic,
            capabilities=device.capabilities,
            status="offline",
            created_at=now,
            updated_at=now,
            last_seen_at=None,
        )

    @staticmethod
    async def get_by_id(device_id: str) -> DeviceResponse | None:
        """
        Get a device by its ID.

        Args:
            device_id: Unique device identifier

        Returns:
            Device if found, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
            SELECT id, friendly_name, device_type, manufacturer, model,
                   firmware_version, mqtt_topic, capabilities_json, status,
                   created_at, updated_at, last_seen_at
            FROM devices
            WHERE id = ?
            """,
            (device_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return DeviceRepository._row_to_response(row)

    @staticmethod
    async def get_all(skip: int = 0, limit: int = 100) -> list[DeviceResponse]:
        """
        Get all devices with pagination.

        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)

        Returns:
            List of devices
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
            SELECT id, friendly_name, device_type, manufacturer, model,
                   firmware_version, mqtt_topic, capabilities_json, status,
                   created_at, updated_at, last_seen_at
            FROM devices
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, skip),
        )
        rows = await cursor.fetchall()

        return [DeviceRepository._row_to_response(row) for row in rows]

    @staticmethod
    async def update(device_id: str, device: DeviceCreate) -> DeviceResponse | None:
        """
        Update an existing device.

        Args:
            device_id: ID of device to update
            device: New device data

        Returns:
            Updated device if found, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        capabilities_json = json.dumps(device.capabilities)

        cursor = await conn.execute(
            """
            UPDATE devices
            SET friendly_name = ?, device_type = ?, manufacturer = ?,
                model = ?, firmware_version = ?, mqtt_topic = ?,
                capabilities_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                device.friendly_name,
                device.device_type,
                device.manufacturer,
                device.model,
                device.firmware_version,
                device.mqtt_topic,
                capabilities_json,
                now.isoformat(),
                device_id,
            ),
        )
        await conn.commit()

        if cursor.rowcount == 0:
            return None

        return await DeviceRepository.get_by_id(device_id)

    @staticmethod
    async def delete(device_id: str) -> bool:
        """
        Delete a device by ID.

        Args:
            device_id: ID of device to delete

        Returns:
            True if deleted, False if not found
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        await conn.commit()

        return cursor.rowcount > 0  # type: ignore[no-any-return]

    @staticmethod
    async def count() -> int:
        """
        Get total count of devices.

        Returns:
            Number of devices in database
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute("SELECT COUNT(*) FROM devices")
        row = await cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    async def update_status(device_id: str, status: str, last_seen: datetime | None = None) -> bool:
        """
        Update device status and last_seen timestamp.

        Args:
            device_id: ID of device to update
            status: New status (online/offline/error)
            last_seen: Last seen timestamp (defaults to now)

        Returns:
            True if updated, False if not found
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        last_seen_val = (last_seen or now).isoformat()

        cursor = await conn.execute(
            """
            UPDATE devices
            SET status = ?, last_seen_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, last_seen_val, now.isoformat(), device_id),
        )
        await conn.commit()

        return cursor.rowcount > 0  # type: ignore[no-any-return]

    @staticmethod
    def _row_to_response(row: aiosqlite.Row) -> DeviceResponse:
        """
        Convert database row to DeviceResponse model.

        Args:
            row: Database row from devices table

        Returns:
            DeviceResponse model instance
        """
        capabilities = json.loads(row[7]) if row[7] else []
        created_at = datetime.fromisoformat(row[9])
        updated_at = datetime.fromisoformat(row[10])
        last_seen_at = datetime.fromisoformat(row[11]) if row[11] else None

        return DeviceResponse(
            id=row[0],
            friendly_name=row[1],
            device_type=row[2],
            manufacturer=row[3],
            model=row[4],
            firmware_version=row[5],
            mqtt_topic=row[6],
            capabilities=capabilities,
            status=row[8],
            created_at=created_at,
            updated_at=updated_at,
            last_seen_at=last_seen_at,
        )
