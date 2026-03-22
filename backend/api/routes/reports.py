"""Report API endpoints.

Provides dashboard summary data used by the SmartNest TUI dashboard
and report views.
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.deps import get_current_user
from backend.api.models.user import UserResponse
from backend.database.connection import get_connection

router = APIRouter(prefix="/api/reports", tags=["reports"])


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary payload for live TUI rendering."""

    total_devices: int
    online_devices: int
    offline_devices: int
    sensor_devices: int
    backend_status: str
    database_status: str
    database_size_mb: float
    response_time_ms: int
    recent_activity: list[str]
    alerts: list[str]


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> DashboardSummaryResponse:
    """Return aggregate metrics needed by the dashboard screen."""
    start = time.perf_counter()

    async with get_connection() as conn:
        total_cursor = await conn.execute("SELECT COUNT(*) AS total_count FROM devices")
        total_row = await total_cursor.fetchone()

        online_cursor = await conn.execute(
            "SELECT COUNT(*) AS online_count FROM devices WHERE status = 'online'"
        )
        online_row = await online_cursor.fetchone()

        offline_cursor = await conn.execute(
            "SELECT COUNT(*) AS offline_count FROM devices WHERE status != 'online'"
        )
        offline_row = await offline_cursor.fetchone()

        sensor_cursor = await conn.execute(
            """
            SELECT COUNT(*) AS sensor_count
            FROM devices
            WHERE device_type LIKE '%sensor%'
            """
        )
        sensor_row = await sensor_cursor.fetchone()

        activity_cursor = await conn.execute(
            """
            SELECT d.friendly_name,
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
            LIMIT 5
            """
        )
        activity_rows = await activity_cursor.fetchall()

        page_size_cursor = await conn.execute("PRAGMA page_size")
        page_size_row = await page_size_cursor.fetchone()

        page_count_cursor = await conn.execute("PRAGMA page_count")
        page_count_row = await page_count_cursor.fetchone()

    total_devices = int(total_row["total_count"]) if total_row else 0
    online_devices = int(online_row["online_count"]) if online_row else 0
    offline_devices = int(offline_row["offline_count"]) if offline_row else 0
    sensor_devices = int(sensor_row["sensor_count"]) if sensor_row else 0

    recent_activity = [
        (
            f"{row['friendly_name']}: {row['sensor_type']}="
            f"{row['value']} {row['unit'] or ''} @ {row['timestamp']}"
        ).strip()
        for row in activity_rows
    ]

    alerts: list[str] = []
    if total_devices == 0:
        alerts.append("No devices registered")
    if offline_devices > 0:
        alerts.append(f"{offline_devices} device(s) offline")

    page_size = int(page_size_row[0]) if page_size_row else 0
    page_count = int(page_count_row[0]) if page_count_row else 0
    db_size_mb = round((page_size * page_count) / (1024 * 1024), 2)
    response_time_ms = int((time.perf_counter() - start) * 1000)

    return DashboardSummaryResponse(
        total_devices=total_devices,
        online_devices=online_devices,
        offline_devices=offline_devices,
        sensor_devices=sensor_devices,
        backend_status="online",
        database_status="online",
        database_size_mb=db_size_mb,
        response_time_ms=response_time_ms,
        recent_activity=recent_activity,
        alerts=alerts,
    )
