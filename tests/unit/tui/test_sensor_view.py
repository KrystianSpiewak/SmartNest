"""Unit tests for SensorViewScreen."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from backend.tui.screens.sensor_view import SensorViewScreen

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_console() -> MagicMock:
    """Create mock Console for testing."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client for testing."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def sensor_view_screen(mock_console: MagicMock, mock_http_client: MagicMock) -> SensorViewScreen:
    """Create SensorViewScreen instance for testing."""
    return SensorViewScreen(mock_console, mock_http_client)


class TestSensorViewScreenInitialization:
    """Test SensorViewScreen initialization."""

    def test_initialization_with_console_and_client(
        self,
        sensor_view_screen: SensorViewScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that SensorViewScreen initializes with console and HTTP client."""
        assert sensor_view_screen.console is mock_console
        assert sensor_view_screen.http_client is mock_http_client
        assert sensor_view_screen.sensor_data == []
        assert sensor_view_screen.sensor_stats == {}


class TestFetchSensorData:
    """Test fetch_sensor_data method."""

    def test_fetch_sensor_data_success(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """Test successful sensor data fetch from API."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "readings": [
                {
                    "device_name": "Living Room Temp",
                    "sensor_type": "temperature",
                    "value": 21.5,
                    "unit": "°C",
                    "timestamp": "2026-02-26 12:30:45",
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        # Fetch sensor data
        success = sensor_view_screen.fetch_sensor_data()

        # Assert
        assert success is True
        assert len(sensor_view_screen.sensor_data) == 1
        assert sensor_view_screen.sensor_data[0]["value"] == 21.5
        mock_http_client.get.assert_called_once_with("/api/sensors/latest")

    def test_fetch_sensor_data_error(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """Test sensor data fetch error handling."""
        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Fetch sensor data
        success = sensor_view_screen.fetch_sensor_data()

        # Assert
        assert success is False
        assert sensor_view_screen.sensor_data == []

    def test_fetch_sensor_data_uses_cached_result_within_interval(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """fetch_sensor_data() returns cached status when called again within throttle window."""
        sensor_view_screen._sensor_data_last_fetch = 100.0
        sensor_view_screen._sensor_data_last_success = True
        sensor_view_screen._fetch_interval_seconds = 2.0

        with patch("backend.tui.screens.sensor_view.time.monotonic", return_value=101.0):
            success = sensor_view_screen.fetch_sensor_data()

        assert success is True
        mock_http_client.get.assert_not_called()


class TestFetchSensorStats:
    """Test fetch_sensor_stats method."""

    def test_fetch_sensor_stats_success(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """Test successful sensor stats fetch from API."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "stats": {
                "Living Room Temp": {
                    "min": 19.5,
                    "max": 23.0,
                    "average": 21.2,
                    "count": 144,
                    "unit": "°C",
                }
            }
        }
        mock_http_client.get.return_value = mock_response

        # Fetch sensor stats
        success = sensor_view_screen.fetch_sensor_stats()

        # Assert
        assert success is True
        assert "Living Room Temp" in sensor_view_screen.sensor_stats
        assert sensor_view_screen.sensor_stats["Living Room Temp"]["min"] == 19.5
        mock_http_client.get.assert_called_once_with("/api/sensors/stats/24h")

    def test_fetch_sensor_stats_error(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """Test sensor stats fetch error handling."""
        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Fetch sensor stats
        success = sensor_view_screen.fetch_sensor_stats()

        # Assert
        assert success is False
        assert sensor_view_screen.sensor_stats == {}

    def test_fetch_sensor_stats_uses_cached_result_within_interval(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """fetch_sensor_stats() returns cached status when called again within throttle window."""
        sensor_view_screen._sensor_stats_last_fetch = 100.0
        sensor_view_screen._sensor_stats_last_success = True
        sensor_view_screen._fetch_interval_seconds = 2.0

        with patch("backend.tui.screens.sensor_view.time.monotonic", return_value=101.0):
            success = sensor_view_screen.fetch_sensor_stats()

        assert success is True
        mock_http_client.get.assert_not_called()


class TestRenderMethods:
    """Test rendering methods."""

    def test_render_header(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_header returns Panel."""
        header = sensor_view_screen._render_header()
        assert isinstance(header, Panel)

    def test_render_readings_table_success(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_readings_table with successful data."""
        sensor_view_screen.sensor_data = [
            {
                "device_name": "Living Room Temp",
                "sensor_type": "temperature",
                "value": 21.5,
                "unit": "°C",
                "timestamp": "2026-02-26 12:30:45",
            }
        ]
        table_panel = sensor_view_screen._render_readings_table(api_success=True)
        assert isinstance(table_panel, Panel)

    def test_render_readings_table_error(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_readings_table with API error."""
        table_panel = sensor_view_screen._render_readings_table(api_success=False)
        assert isinstance(table_panel, Panel)

    def test_render_readings_table_missing_values(
        self, sensor_view_screen: SensorViewScreen
    ) -> None:
        """Test _render_readings_table with missing values."""
        sensor_view_screen.sensor_data = [
            {
                "device_name": "Sensor",
                "sensor_type": "unknown",
                "value": None,
                "timestamp": None,
            }
        ]
        table_panel = sensor_view_screen._render_readings_table(api_success=True)
        assert isinstance(table_panel, Panel)

    def test_render_statistics_success(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_statistics with successful data."""
        sensor_view_screen.sensor_stats = {
            "Living Room Temp": {
                "min": 19.5,
                "max": 23.0,
                "average": 21.2,
                "count": 144,
                "unit": "°C",
            }
        }
        stats_panel = sensor_view_screen._render_statistics(api_success=True)
        assert isinstance(stats_panel, Panel)

    def test_render_statistics_error(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_statistics with API error."""
        stats_panel = sensor_view_screen._render_statistics(api_success=False)
        assert isinstance(stats_panel, Panel)

    def test_render_statistics_empty(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_statistics with no data."""
        sensor_view_screen.sensor_stats = {}
        stats_panel = sensor_view_screen._render_statistics(api_success=True)
        assert isinstance(stats_panel, Panel)

    def test_render_statistics_missing_values(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_statistics with missing values."""
        sensor_view_screen.sensor_stats = {
            "Sensor": {
                "min": None,
                "max": None,
                "average": None,
                "count": 0,
            }
        }
        stats_panel = sensor_view_screen._render_statistics(api_success=True)
        assert isinstance(stats_panel, Panel)

    def test_render_instructions(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_instructions returns Panel."""
        instructions = sensor_view_screen._render_instructions()
        assert isinstance(instructions, Panel)

    def test_render_instructions_with_action_status(
        self, sensor_view_screen: SensorViewScreen
    ) -> None:
        """_render_instructions includes status text when action status exists."""
        sensor_view_screen._action_status = "Exported"
        instructions = sensor_view_screen._render_instructions()
        assert isinstance(instructions, Panel)

    def test_render_menu(self, sensor_view_screen: SensorViewScreen) -> None:
        """Test _render_menu returns Text."""
        menu = sensor_view_screen._render_menu()
        assert isinstance(menu, Text)


class TestRenderLive:
    """Test render_live method."""

    def test_render_live_fetches_data(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live fetches both sensor data and stats."""
        # Mock API responses
        mock_readings_response = MagicMock()
        mock_readings_response.json.return_value = {
            "readings": [
                {
                    "device_name": "Living Room Temp",
                    "sensor_type": "temperature",
                    "value": 21.5,
                    "unit": "°C",
                    "timestamp": "2026-02-26 12:30:45",
                }
            ]
        }

        mock_stats_response = MagicMock()
        mock_stats_response.json.return_value = {
            "stats": {
                "Living Room Temp": {
                    "min": 19.5,
                    "max": 23.0,
                    "average": 21.2,
                    "count": 144,
                }
            }
        }

        mock_http_client.get.side_effect = [
            mock_readings_response,
            mock_stats_response,
        ]

        # Render live
        result = sensor_view_screen.render_live()

        # Assert
        assert isinstance(result, Group)
        assert mock_http_client.get.call_count == 2

    def test_render_live_handles_api_error(
        self, sensor_view_screen: SensorViewScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live handles API error gracefully."""
        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Render live
        result = sensor_view_screen.render_live()

        # Assert
        assert isinstance(result, Group)


class TestRender:
    """Test render method."""

    def test_render_calls_methods(
        self,
        sensor_view_screen: SensorViewScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test render method calls all rendering methods."""
        # Mock API responses
        mock_readings_response = MagicMock()
        mock_readings_response.json.return_value = {"readings": []}

        mock_stats_response = MagicMock()
        mock_stats_response.json.return_value = {"stats": {}}

        mock_http_client.get.side_effect = [
            mock_readings_response,
            mock_stats_response,
        ]

        # Render
        sensor_view_screen.render()

        # Assert console.print was called
        assert mock_console.print.call_count >= 5


class TestActions:
    """Test sensor action methods."""

    def test_refresh_now_success(self, sensor_view_screen: SensorViewScreen) -> None:
        """refresh_now() forces both fetches and updates success status."""
        sensor_view_screen._sensor_data_last_fetch = 123.0
        sensor_view_screen._sensor_stats_last_fetch = 456.0
        sensor_view_screen.fetch_sensor_data = MagicMock(return_value=True)  # type: ignore[method-assign]
        sensor_view_screen.fetch_sensor_stats = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = sensor_view_screen.refresh_now()

        assert result is True
        assert sensor_view_screen._sensor_data_last_fetch == 0.0
        assert sensor_view_screen._sensor_stats_last_fetch == 0.0
        assert sensor_view_screen._action_status == "Refreshed"

    def test_refresh_now_failure(self, sensor_view_screen: SensorViewScreen) -> None:
        """refresh_now() reports failure when any fetch fails."""
        sensor_view_screen.fetch_sensor_data = MagicMock(return_value=False)  # type: ignore[method-assign]
        sensor_view_screen.fetch_sensor_stats = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = sensor_view_screen.refresh_now()

        assert result is False
        assert sensor_view_screen._action_status == "Refresh failed"

    def test_export_csv_success(
        self,
        sensor_view_screen: SensorViewScreen,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """export_csv() writes report file and stores success status."""
        sensor_view_screen.sensor_data = [
            {
                "device_name": "Temp 1",
                "sensor_type": "temperature",
                "value": 21.5,
                "unit": "C",
                "timestamp": "2026-02-26 12:30:45",
            }
        ]
        sensor_view_screen.sensor_stats = {
            "Temp 1": {"min": 20.1, "max": 22.3, "average": 21.0, "count": 5, "unit": "C"}
        }
        sensor_view_screen.refresh_now = MagicMock(return_value=True)  # type: ignore[method-assign]
        monkeypatch.chdir(tmp_path)

        result = sensor_view_screen.export_csv()

        assert result is not None
        assert "sensor_export_" in result
        assert (tmp_path / "reports").exists()
        assert sensor_view_screen._action_status.startswith("Exported:")

    def test_export_csv_os_error(self, sensor_view_screen: SensorViewScreen) -> None:
        """export_csv() sets failure status and returns None when writing fails."""
        sensor_view_screen.refresh_now = MagicMock(return_value=True)  # type: ignore[method-assign]

        with patch("backend.tui.screens.sensor_view.Path.open", side_effect=OSError):
            result = sensor_view_screen.export_csv()

        assert result is None
        assert sensor_view_screen._action_status == "Export failed"
