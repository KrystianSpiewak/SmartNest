"""Sensor data API endpoints.

Provides latest sensor readings and 24-hour aggregate statistics
for the SmartNest TUI sensor screen.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.deps import get_current_user
from backend.api.models.user import UserResponse
from backend.database.connection import get_connection

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


class SensorReadingResponse(BaseModel):
    """Single latest sensor reading for a device."""

    device_id: str
    device_name: str
    sensor_type: str
    value: float
    unit: str | None
    timestamp: datetime


class SensorLatestResponse(BaseModel):
    """Latest sensor readings payload."""

    readings: list[SensorReadingResponse]


class SensorStatsItem(BaseModel):
    """24-hour aggregate statistics for one sensor stream."""

    min: float | None
    max: float | None
    average: float | None
    count: int
    unit: str | None


class SensorStatsResponse(BaseModel):
    """24-hour statistics payload keyed by sensor label."""

    stats: dict[str, SensorStatsItem]


@router.get("/latest", response_model=SensorLatestResponse)
async def get_latest_sensor_readings(
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> SensorLatestResponse:
    """Return the latest sensor reading for each device/sensor type pair."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            SELECT sr.device_id,
                   d.friendly_name AS device_name,
                   sr.sensor_type,
                   sr.value,
                   sr.unit,
                   sr.timestamp
            FROM sensor_readings AS sr
            INNER JOIN devices AS d ON d.id = sr.device_id
            INNER JOIN (
                SELECT device_id, sensor_type, MAX(timestamp) AS max_timestamp
                FROM sensor_readings
                GROUP BY device_id, sensor_type
            ) AS latest
                ON latest.device_id = sr.device_id
               AND latest.sensor_type = sr.sensor_type
               AND latest.max_timestamp = sr.timestamp
            ORDER BY sr.timestamp DESC
            """
        )
        rows = await cursor.fetchall()

    readings = [
        SensorReadingResponse(
            device_id=row["device_id"],
            device_name=row["device_name"],
            sensor_type=row["sensor_type"],
            value=row["value"],
            unit=row["unit"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
        for row in rows
    ]
    return SensorLatestResponse(readings=readings)


@router.get("/stats/24h", response_model=SensorStatsResponse)
async def get_sensor_stats_24h(
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> SensorStatsResponse:
    """Return 24-hour sensor aggregates for all available sensor streams."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            SELECT d.friendly_name AS device_name,
                   sr.sensor_type,
                   MIN(sr.value) AS min_value,
                   MAX(sr.value) AS max_value,
                   AVG(sr.value) AS avg_value,
                   COUNT(*) AS sample_count,
                   sr.unit
            FROM sensor_readings AS sr
            INNER JOIN devices AS d ON d.id = sr.device_id
            WHERE sr.timestamp >= datetime('now', '-1 day')
            GROUP BY sr.device_id, d.friendly_name, sr.sensor_type, sr.unit
            ORDER BY d.friendly_name, sr.sensor_type
            """
        )
        rows = await cursor.fetchall()

    stats: dict[str, SensorStatsItem] = {}
    for row in rows:
        key = f"{row['device_name']} ({row['sensor_type']})"
        stats[key] = SensorStatsItem(
            min=row["min_value"],
            max=row["max_value"],
            average=row["avg_value"],
            count=row["sample_count"],
            unit=row["unit"],
        )

    return SensorStatsResponse(stats=stats)
