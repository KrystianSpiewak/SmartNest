"""Integration tests for sensor API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


class TestSensorLatestEndpoint:
    """Tests for GET /api/sensors/latest."""

    @staticmethod
    async def _seed_sensor_data() -> None:
        """Seed one sensor device with two readings for latest selection."""
        now = datetime.now(UTC)
        earlier = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        latest = now.strftime("%Y-%m-%d %H:%M:%S")

        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO devices (
                    id, friendly_name, device_type, mqtt_topic, capabilities, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    "temp-001",
                    "Living Room Temp",
                    "temperature_sensor",
                    "smartnest/sensor/temp-001",
                    "[]",
                    "online",
                ),
            )
            await conn.execute(
                """
                INSERT INTO sensor_readings (device_id, sensor_type, value, unit, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("temp-001", "temperature", 21.2, "C", earlier),
            )
            await conn.execute(
                """
                INSERT INTO sensor_readings (device_id, sensor_type, value, unit, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("temp-001", "temperature", 22.8, "C", latest),
            )
            await conn.commit()

    def test_latest_empty(self, client: TestClient) -> None:
        """Endpoint returns empty readings list when no data exists."""
        response = client.get("/api/sensors/latest")

        assert response.status_code == 200
        assert response.json() == {"readings": []}

    @pytest.mark.asyncio
    async def test_latest_returns_most_recent(self, client: TestClient) -> None:
        """Endpoint returns latest reading per sensor stream."""
        await self._seed_sensor_data()

        response = client.get("/api/sensors/latest")

        assert response.status_code == 200
        readings = response.json()["readings"]
        assert len(readings) == 1
        assert readings[0]["device_id"] == "temp-001"
        assert readings[0]["value"] == 22.8


class TestSensorStatsEndpoint:
    """Tests for GET /api/sensors/stats/24h."""

    @pytest.mark.asyncio
    async def test_stats_24h_returns_aggregates(self, client: TestClient) -> None:
        """Endpoint computes min/max/average/count for last 24h readings."""
        await TestSensorLatestEndpoint._seed_sensor_data()

        response = client.get("/api/sensors/stats/24h")

        assert response.status_code == 200
        stats = response.json()["stats"]
        assert "Living Room Temp (temperature)" in stats
        item = stats["Living Room Temp (temperature)"]
        assert item["min"] == 21.2
        assert item["max"] == 22.8
        assert item["count"] == 2
