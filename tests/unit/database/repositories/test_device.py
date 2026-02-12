"""Unit tests for DeviceRepository."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.models.device import DeviceCreate, DeviceResponse
from backend.database.repositories.device import DeviceRepository

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def sample_device_create() -> DeviceCreate:
    """Sample DeviceCreate for testing."""
    return DeviceCreate(
        id="light-001",
        friendly_name="Living Room Light",
        device_type="light",
        manufacturer="Philips",
        model="Hue",
        firmware_version="1.0.0",
        mqtt_topic="smartnest/device/light-001/command",
        capabilities=["power", "brightness"],
    )


@pytest.fixture
def sample_device_row() -> tuple[object, ...]:
    """Sample database row for device."""
    now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
    return (
        "light-001",  # id
        "Living Room Light",  # friendly_name
        "light",  # device_type
        "Philips",  # manufacturer
        "Hue",  # model
        "1.0.0",  # firmware_version
        "smartnest/device/light-001/command",  # mqtt_topic
        '["power", "brightness"]',  # capabilities_json
        "online",  # status
        now.isoformat(),  # created_at
        now.isoformat(),  # updated_at
        now.isoformat(),  # last_seen_at
    )


@pytest.fixture
def mock_connection() -> Mock:
    """Mock database connection."""
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.commit = AsyncMock()
    cursor = MagicMock()
    cursor.fetchone = AsyncMock()
    cursor.fetchall = AsyncMock()
    cursor.rowcount = 1
    conn.execute.return_value = cursor
    return conn


class TestDeviceRepositoryCreate:
    """Tests for DeviceRepository.create()."""

    @pytest.mark.asyncio
    async def test_create_device_success(
        self, sample_device_create: DeviceCreate, mock_connection: Mock
    ) -> None:
        """Test creating a device successfully."""
        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.create(sample_device_create)

            # Verify execute was called with correct SQL
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args
            assert "INSERT INTO devices" in call_args[0][0]
            assert call_args[0][1][0] == "light-001"
            assert call_args[0][1][1] == "Living Room Light"

            # Verify commit was called
            mock_connection.commit.assert_called_once()

            # Verify returned DeviceResponse
            assert isinstance(result, DeviceResponse)
            assert result.id == "light-001"
            assert result.friendly_name == "Living Room Light"
            assert result.status == "offline"
            assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_device_minimal_fields(self, mock_connection: Mock) -> None:
        """Test creating device with minimal required fields."""
        minimal_device = DeviceCreate(
            id="sensor-001",
            friendly_name="Temp Sensor",
            device_type="sensor",
            mqtt_topic="smartnest/sensor/001",
            manufacturer=None,
            model=None,
            firmware_version=None,
        )

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.create(minimal_device)

            assert result.id == "sensor-001"
            assert result.manufacturer is None
            assert result.capabilities == []


class TestDeviceRepositoryGetById:
    """Tests for DeviceRepository.get_by_id()."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self, sample_device_row: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test getting device by ID when it exists."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = sample_device_row

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.get_by_id("light-001")

            # Verify query was correct
            mock_connection.execute.assert_called_once()
            assert "SELECT" in mock_connection.execute.call_args[0][0]
            assert "WHERE id = ?" in mock_connection.execute.call_args[0][0]

            # Verify result
            assert result is not None
            assert result.id == "light-001"
            assert result.friendly_name == "Living Room Light"
            assert result.status == "online"
            assert len(result.capabilities) == 2

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_connection: Mock) -> None:
        """Test getting device by ID when it doesn't exist."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = None

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.get_by_id("nonexistent")

            assert result is None


class TestDeviceRepositoryGetAll:
    """Tests for DeviceRepository.get_all()."""

    @pytest.mark.asyncio
    async def test_get_all_with_results(
        self, sample_device_row: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test getting all devices with results."""
        cursor = mock_connection.execute.return_value
        cursor.fetchall.return_value = [sample_device_row, sample_device_row]

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.get_all()

            # Verify query includes pagination
            call_args = mock_connection.execute.call_args
            assert "LIMIT ? OFFSET ?" in call_args[0][0]
            assert call_args[0][1] == (100, 0)  # Default pagination

            assert len(result) == 2
            assert all(isinstance(d, DeviceResponse) for d in result)

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, mock_connection: Mock) -> None:
        """Test getting devices with custom pagination."""
        cursor = mock_connection.execute.return_value
        cursor.fetchall.return_value = []

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            await DeviceRepository.get_all(skip=10, limit=50)

            call_args = mock_connection.execute.call_args
            assert call_args[0][1] == (50, 10)

    @pytest.mark.asyncio
    async def test_get_all_empty(self, mock_connection: Mock) -> None:
        """Test getting all devices when database is empty."""
        cursor = mock_connection.execute.return_value
        cursor.fetchall.return_value = []

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.get_all()

            assert result == []


class TestDeviceRepositoryUpdate:
    """Tests for DeviceRepository.update()."""

    @pytest.mark.asyncio
    async def test_update_device_success(
        self,
        sample_device_create: DeviceCreate,
        sample_device_row: tuple[object, ...],
        mock_connection: Mock,
    ) -> None:
        """Test updating a device successfully."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1
        cursor.fetchone.return_value = sample_device_row

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.update("light-001", sample_device_create)

            # Verify UPDATE was called
            assert mock_connection.execute.call_count == 2  # UPDATE + SELECT
            update_call = mock_connection.execute.call_args_list[0]
            assert "UPDATE devices" in update_call[0][0]

            assert result is not None
            assert result.id == "light-001"

    @pytest.mark.asyncio
    async def test_update_device_not_found(
        self, sample_device_create: DeviceCreate, mock_connection: Mock
    ) -> None:
        """Test updating non-existent device."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.update("nonexistent", sample_device_create)

            assert result is None


class TestDeviceRepositoryDelete:
    """Tests for DeviceRepository.delete()."""

    @pytest.mark.asyncio
    async def test_delete_device_success(self, mock_connection: Mock) -> None:
        """Test deleting a device successfully."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.delete("light-001")

            # Verify DELETE was called
            call_args = mock_connection.execute.call_args
            assert "DELETE FROM devices" in call_args[0][0]
            assert call_args[0][1] == ("light-001",)

            assert result is True

    @pytest.mark.asyncio
    async def test_delete_device_not_found(self, mock_connection: Mock) -> None:
        """Test deleting non-existent device."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.delete("nonexistent")

            assert result is False


class TestDeviceRepositoryCount:
    """Tests for DeviceRepository.count()."""

    @pytest.mark.asyncio
    async def test_count_devices(self, mock_connection: Mock) -> None:
        """Test counting devices."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = (42,)

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.count()

            call_args = mock_connection.execute.call_args
            assert "SELECT COUNT(*)" in call_args[0][0]
            assert result == 42

    @pytest.mark.asyncio
    async def test_count_zero(self, mock_connection: Mock) -> None:
        """Test counting when no devices."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = (0,)

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.count()

            assert result == 0


class TestDeviceRepositoryUpdateStatus:
    """Tests for DeviceRepository.update_status()."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, mock_connection: Mock) -> None:
        """Test updating device status."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.update_status("light-001", "online")

            # Verify UPDATE was called
            call_args = mock_connection.execute.call_args
            assert "UPDATE devices" in call_args[0][0]
            assert "SET status = ?" in call_args[0][0]
            assert call_args[0][1][0] == "online"

            assert result is True

    @pytest.mark.asyncio
    async def test_update_status_with_custom_timestamp(self, mock_connection: Mock) -> None:
        """Test updating status with custom last_seen timestamp."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1
        custom_time = datetime(2026, 1, 15, 10, 30, 0)  # noqa: DTZ001

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.update_status(
                "light-001", "offline", last_seen=custom_time
            )

            call_args = mock_connection.execute.call_args
            assert call_args[0][1][1] == custom_time.isoformat()
            assert result is True

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, mock_connection: Mock) -> None:
        """Test updating status for non-existent device."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with patch(
            "backend.database.repositories.device.get_connection",
            AsyncMock(return_value=mock_connection),
        ):
            result = await DeviceRepository.update_status("nonexistent", "online")

            assert result is False


class TestDeviceRepositoryRowConversion:
    """Tests for DeviceRepository._row_to_response()."""

    def test_row_to_response_complete(self, sample_device_row: tuple[object, ...]) -> None:
        """Test converting complete database row to response."""
        result = DeviceRepository._row_to_response(sample_device_row)  # type: ignore[arg-type]

        assert isinstance(result, DeviceResponse)
        assert result.id == "light-001"
        assert result.friendly_name == "Living Room Light"
        assert result.capabilities == ["power", "brightness"]
        assert isinstance(result.created_at, datetime)
        assert result.last_seen_at is not None

    def test_row_to_response_null_last_seen(self) -> None:
        """Test converting row with null last_seen_at."""
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        row = (
            "sensor-001",
            "Sensor",
            "sensor",
            None,
            None,
            None,
            "topic",
            "[]",
            "offline",
            now.isoformat(),
            now.isoformat(),
            None,  # last_seen_at is null
        )

        result = DeviceRepository._row_to_response(row)  # type: ignore[arg-type]

        assert result.last_seen_at is None
        assert result.manufacturer is None
