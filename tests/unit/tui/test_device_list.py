"""Unit tests for DeviceListScreen."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import httpx
import pytest
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from backend.tui.screens.device_list import DeviceListScreen


@pytest.fixture
def mock_console() -> MagicMock:
    """Create mock Console for testing."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client for testing."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def device_list_screen(mock_console: MagicMock, mock_http_client: MagicMock) -> DeviceListScreen:
    """Create DeviceListScreen instance for testing."""
    return DeviceListScreen(mock_console, mock_http_client)


class TestDeviceListScreenInitialization:
    """Test DeviceListScreen initialization."""

    def test_initialization_with_console_and_client(
        self,
        device_list_screen: DeviceListScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that DeviceListScreen initializes with console and HTTP client."""
        assert device_list_screen.console is mock_console
        assert device_list_screen.http_client is mock_http_client
        assert device_list_screen.devices == []
        assert device_list_screen.filter_type == "all"
        assert device_list_screen.search_query == ""


class TestFetchDevices:
    """Test fetch_devices method."""

    def test_fetch_devices_success(
        self, device_list_screen: DeviceListScreen, mock_http_client: MagicMock
    ) -> None:
        """Test successful device fetch from API."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "devices": [
                {
                    "device_id": "light_01",
                    "name": "Living Room Light",
                    "device_type": "smart_light",
                    "status": "online",
                },
            ]
        }
        mock_http_client.get.return_value = mock_response

        # Fetch devices
        success = device_list_screen.fetch_devices()

        # Assert
        assert success is True
        assert len(device_list_screen.devices) == 1
        assert device_list_screen.devices[0]["name"] == "Living Room Light"
        mock_http_client.get.assert_called_once_with("/api/devices")

    def test_fetch_devices_error(
        self, device_list_screen: DeviceListScreen, mock_http_client: MagicMock
    ) -> None:
        """Test device fetch error handling."""
        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Fetch devices
        success = device_list_screen.fetch_devices()

        # Assert
        assert success is False
        assert device_list_screen.devices == []

    def test_fetch_devices_uses_cached_result_when_throttled(self) -> None:
        """fetch_devices() returns cached success and skips HTTP call inside throttle window."""
        console = MagicMock()
        http_client = MagicMock()
        screen = DeviceListScreen(console, http_client)
        screen._last_fetch_success = True
        screen._last_fetch_at = time.monotonic()

        result = screen.fetch_devices()

        assert result is True
        http_client.get.assert_not_called()

    def test_fetch_devices_uses_cached_failure_when_throttled(self) -> None:
        """fetch_devices() returns cached failure and skips HTTP call inside throttle window."""
        console = MagicMock()
        http_client = MagicMock()
        screen = DeviceListScreen(console, http_client)
        screen._last_fetch_success = False
        screen._last_fetch_at = time.monotonic()

        result = screen.fetch_devices()

        assert result is False
        http_client.get.assert_not_called()


class TestFilterMethods:
    """Test filter and search functionality."""

    def test_set_filter_valid_types(self, device_list_screen: DeviceListScreen) -> None:
        """Test setting valid filter types."""
        device_list_screen.set_filter("lights")
        assert device_list_screen.filter_type == "lights"

        device_list_screen.set_filter("sensors")
        assert device_list_screen.filter_type == "sensors"

        device_list_screen.set_filter("switches")
        assert device_list_screen.filter_type == "switches"

        device_list_screen.set_filter("all")
        assert device_list_screen.filter_type == "all"

    def test_set_filter_invalid_type(self, device_list_screen: DeviceListScreen) -> None:
        """Test that invalid filter types are ignored."""
        device_list_screen.filter_type = "all"
        device_list_screen.set_filter("invalid_type")
        assert device_list_screen.filter_type == "all"

    def test_set_search(self, device_list_screen: DeviceListScreen) -> None:
        """Test setting search query."""
        device_list_screen.set_search("kitchen")
        assert device_list_screen.search_query == "kitchen"


class TestGetFilteredDevices:
    """Test get_filtered_devices method."""

    def test_filter_by_lights(self, device_list_screen: DeviceListScreen) -> None:
        """Test filtering devices by lights."""
        device_list_screen.devices = [
            {"name": "Light 1", "device_type": "smart_light"},
            {"name": "Sensor 1", "device_type": "temperature_sensor"},
            {"name": "Light 2", "device_type": "smart_light"},
        ]
        device_list_screen.set_filter("lights")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 2
        assert all(d["device_type"] == "smart_light" for d in filtered)

    def test_filter_by_lights_accepts_light_alias(
        self, device_list_screen: DeviceListScreen
    ) -> None:
        """Test light filter accepts API device_type='light'."""
        device_list_screen.devices = [
            {"id": "light_01", "friendly_name": "Living Room Light", "device_type": "light"},
            {
                "id": "sensor_01",
                "friendly_name": "Temp Sensor",
                "device_type": "temperature_sensor",
            },
        ]
        device_list_screen.set_filter("lights")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 1
        assert filtered[0]["device_type"] == "light"

    def test_filter_by_sensors(self, device_list_screen: DeviceListScreen) -> None:
        """Test filtering devices by sensors."""
        device_list_screen.devices = [
            {"name": "Light 1", "device_type": "smart_light"},
            {"name": "Temp Sensor", "device_type": "temperature_sensor"},
            {"name": "Motion Sensor", "device_type": "motion_sensor"},
        ]
        device_list_screen.set_filter("sensors")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 2
        assert all(d["device_type"] in ("temperature_sensor", "motion_sensor") for d in filtered)

    def test_filter_by_switches(self, device_list_screen: DeviceListScreen) -> None:
        """Test filtering devices by switches."""
        device_list_screen.devices = [
            {"name": "Light 1", "device_type": "smart_light"},
            {"name": "Switch 1", "device_type": "smart_switch"},
        ]
        device_list_screen.set_filter("switches")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 1
        assert filtered[0]["device_type"] == "smart_switch"

    def test_filter_by_search_query(self, device_list_screen: DeviceListScreen) -> None:
        """Test filtering by search query."""
        device_list_screen.devices = [
            {"name": "Kitchen Light", "location": "kitchen"},
            {"name": "Bedroom Light", "location": "bedroom"},
            {"name": "Kitchen Sensor", "location": "kitchen"},
        ]
        device_list_screen.set_search("kitchen")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 2
        assert all(
            "kitchen" in str(d["name"]).lower() or "kitchen" in str(d["location"]).lower()
            for d in filtered
        )

    def test_filter_by_search_query_uses_api_field_names(
        self, device_list_screen: DeviceListScreen
    ) -> None:
        """Test search works with id/friendly_name API response fields."""
        device_list_screen.devices = [
            {"id": "light_01", "friendly_name": "Kitchen Light", "device_type": "light"},
            {
                "id": "sensor_01",
                "friendly_name": "Bedroom Sensor",
                "device_type": "temperature_sensor",
            },
        ]
        device_list_screen.set_search("kitchen")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 1
        assert filtered[0]["id"] == "light_01"

    def test_filter_combined(self, device_list_screen: DeviceListScreen) -> None:
        """Test combined type filter and search query."""
        device_list_screen.devices = [
            {"name": "Kitchen Light", "device_type": "smart_light", "location": "kitchen"},
            {"name": "Bedroom Light", "device_type": "smart_light", "location": "bedroom"},
            {"name": "Kitchen Sensor", "device_type": "temperature_sensor", "location": "kitchen"},
        ]
        device_list_screen.set_filter("lights")
        device_list_screen.set_search("kitchen")

        filtered = device_list_screen.get_filtered_devices()

        assert len(filtered) == 1
        assert filtered[0]["name"] == "Kitchen Light"


class TestRenderMethods:
    """Test rendering methods."""

    def test_render_header(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_header returns Panel."""
        header = device_list_screen._render_header()
        assert isinstance(header, Panel)

    def test_render_filter_bar_no_search(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_filter_bar without search query."""
        device_list_screen.filter_type = "lights"
        filter_bar = device_list_screen._render_filter_bar()
        assert isinstance(filter_bar, Panel)

    def test_render_filter_bar_with_search(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_filter_bar with search query."""
        device_list_screen.filter_type = "sensors"
        device_list_screen.search_query = "kitchen"
        filter_bar = device_list_screen._render_filter_bar()
        assert isinstance(filter_bar, Panel)

    def test_render_device_table_success(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_device_table with successful API response."""
        device_list_screen.devices = [
            {
                "device_id": "light_01",
                "name": "Living Room Light",
                "device_type": "smart_light",
                "status": "online",
                "location": "Living Room",
                "last_seen_at": "2026-02-26 12:30:45",
            }
        ]
        table_panel = device_list_screen._render_device_table(api_success=True)
        assert isinstance(table_panel, Panel)

    def test_render_device_table_error(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_device_table with API error."""
        table_panel = device_list_screen._render_device_table(api_success=False)
        assert isinstance(table_panel, Panel)

    def test_render_device_table_different_statuses(
        self, device_list_screen: DeviceListScreen
    ) -> None:
        """Test _render_device_table with different device statuses."""
        device_list_screen.devices = [
            {
                "device_id": "light_01",
                "name": "Light 1",
                "device_type": "smart_light",
                "status": "online",
                "location": "Living Room",
                "last_seen_at": "2026-02-26 12:30:45",
            },
            {
                "device_id": "light_02",
                "name": "Light 2",
                "device_type": "smart_light",
                "status": "offline",
                "location": "Bedroom",
                "last_seen_at": None,
            },
            {
                "device_id": "light_03",
                "name": "Light 3",
                "device_type": "smart_light",
                "status": "unknown",
                "location": "Kitchen",
                "last_seen_at": "2026-02-26 12:30:45",
            },
        ]
        table_panel = device_list_screen._render_device_table(api_success=True)
        assert isinstance(table_panel, Panel)

    def test_render_instructions(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_instructions returns Panel."""
        instructions = device_list_screen._render_instructions()
        assert isinstance(instructions, Panel)

    def test_render_menu(self, device_list_screen: DeviceListScreen) -> None:
        """Test _render_menu returns Text."""
        menu = device_list_screen._render_menu()
        assert isinstance(menu, Text)


class TestRenderLive:
    """Test render_live method."""

    def test_render_live_fetches_devices(
        self, device_list_screen: DeviceListScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live fetches devices and returns Group."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "devices": [
                {
                    "device_id": "light_01",
                    "name": "Living Room Light",
                    "device_type": "smart_light",
                    "status": "online",
                    "location": "Living Room",
                    "last_seen_at": "2026-02-26 12:30:45",
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        # Render live
        result = device_list_screen.render_live()

        # Assert
        assert isinstance(result, Group)
        mock_http_client.get.assert_called_once_with("/api/devices")

    def test_render_live_handles_api_error(
        self, device_list_screen: DeviceListScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live handles API error gracefully."""
        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Render live
        result = device_list_screen.render_live()

        # Assert
        assert isinstance(result, Group)


class TestRender:
    """Test render method."""

    def test_render_calls_methods(
        self,
        device_list_screen: DeviceListScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test render method calls all rendering methods."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"devices": []}
        mock_http_client.get.return_value = mock_response

        # Render
        device_list_screen.render()

        # Assert console.print was called
        assert mock_console.print.call_count >= 5
