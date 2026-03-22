"""Integration tests for report API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_current_user
from backend.api.models.user import UserResponse
from backend.app import app
from backend.database.connection import get_connection, init_database

if TYPE_CHECKING:
    from collections.abc import Iterator

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
    async with get_connection() as conn:
        await conn.execute("DELETE FROM sensor_readings")
        await conn.execute("DELETE FROM devices")
        await conn.commit()


class TestDashboardSummaryEndpoint:
    """Tests for GET /api/reports/dashboard-summary."""

    def test_dashboard_summary_empty(self, client: TestClient) -> None:
        """Empty database returns zero counts and no devices alert."""
        response = client.get("/api/reports/dashboard-summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_devices"] == 0
        assert data["online_devices"] == 0
        assert data["offline_devices"] == 0
        assert "No devices registered" in data["alerts"]

    @pytest.mark.asyncio
    async def test_dashboard_summary_with_devices_and_activity(self, client: TestClient) -> None:
        """Summary includes counts, alerts, and recent activity strings."""
        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO devices (
                    id, friendly_name, device_type, mqtt_topic, capabilities, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    "temp-002",
                    "Kitchen Temp",
                    "temperature_sensor",
                    "smartnest/sensor/temp-002",
                    "[]",
                    "offline",
                ),
            )
            await conn.execute(
                """
                INSERT INTO sensor_readings (device_id, sensor_type, value, unit, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("temp-002", "temperature", 19.5, "C", "2026-03-20 11:00:00"),
            )
            await conn.commit()

        response = client.get("/api/reports/dashboard-summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_devices"] == 1
        assert data["online_devices"] == 0
        assert data["offline_devices"] == 1
        assert data["sensor_devices"] == 1
        assert data["backend_status"] == "online"
        assert data["database_status"] == "online"
        assert data["response_time_ms"] >= 0
        assert len(data["recent_activity"]) == 1
        assert "offline" in " ".join(data["alerts"]).lower()
