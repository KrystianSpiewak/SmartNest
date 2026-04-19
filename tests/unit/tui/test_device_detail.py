"""Unit tests for DeviceDetailScreen."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from backend.tui.screens.device_detail import DeviceDetailScreen


def _panel_text(panel: Panel) -> str:
    """Render a panel to plain text for stable content assertions."""
    console = Console(record=True, width=140)
    console.print(panel)
    return console.export_text()


@pytest.fixture
def mock_console() -> MagicMock:
    """Create mock Console for testing."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client for testing."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def device_detail_screen(
    mock_console: MagicMock, mock_http_client: MagicMock
) -> DeviceDetailScreen:
    """Create DeviceDetailScreen instance for testing."""
    return DeviceDetailScreen(mock_console, mock_http_client)


class TestDeviceDetailScreenInitialization:
    """Test DeviceDetailScreen initialization."""

    def test_initialization_with_console_and_client(
        self,
        device_detail_screen: DeviceDetailScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that DeviceDetailScreen initializes with console and HTTP client."""
        assert device_detail_screen.console is mock_console
        assert device_detail_screen.http_client is mock_http_client
        assert device_detail_screen.device_id is None
        assert device_detail_screen.device is None
        assert device_detail_screen.device_state is None
        assert device_detail_screen.live_state is None
        assert device_detail_screen.live_state_source is None


class TestSetDevice:
    """Test set_device method."""

    def test_set_device(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test setting the device ID."""
        device_detail_screen.set_device("light_01")
        assert device_detail_screen.device_id == "light_01"

    def test_set_device_resets_cached_state(self, device_detail_screen: DeviceDetailScreen) -> None:
        """set_device() clears stale API/live state when selecting a new device."""
        device_detail_screen.device = {"id": "old"}
        device_detail_screen.device_state = {"power": "off"}
        device_detail_screen.live_state = {"power": True}
        device_detail_screen.live_state_source = "mqtt_state"

        device_detail_screen.set_device("new_device")

        assert device_detail_screen.device_id == "new_device"
        assert device_detail_screen.device is None
        assert device_detail_screen.device_state is None
        assert device_detail_screen.live_state is None
        assert device_detail_screen.live_state_source is None


class TestLiveStateUpdates:
    """Test real-time state update handling."""

    def test_apply_live_state_update_sets_state_and_source(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """apply_live_state_update() stores payload and source."""
        device_detail_screen.apply_live_state_update({"power": True}, source="mqtt_state")

        assert device_detail_screen.live_state == {"power": True}
        assert device_detail_screen.live_state_source == "mqtt_state"

    def test_effective_state_prefers_live_values(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """Live values override API state when both are present."""
        device_detail_screen.device_state = {"power": "off", "brightness": 50}
        device_detail_screen.apply_live_state_update({"power": True})

        effective = device_detail_screen._effective_state()

        assert effective == {"power": True, "brightness": 50}

    def test_effective_state_ignores_non_dict_device_state(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """Non-dict API state is ignored while dict live state is still used."""
        device_detail_screen.device_state = "invalid"  # type: ignore[assignment]
        device_detail_screen.apply_live_state_update({"power": "on"})

        effective = device_detail_screen._effective_state()

        assert effective == {"power": "on"}

    def test_is_smart_light_returns_false_without_device(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """_is_smart_light() is False when no device has been loaded yet."""
        assert device_detail_screen._is_smart_light() is False


class TestFetchDeviceData:
    """Test fetch_device_data method."""

    def test_fetch_device_data_success(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test successful device data fetch from API."""
        device_detail_screen.set_device("light_01")

        # Mock API responses
        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "device_id": "light_01",
            "name": "Living Room Light",
            "device_type": "smart_light",
            "status": "online",
        }

        mock_state_response = MagicMock()
        mock_state_response.json.return_value = {
            "power": "on",
            "brightness": 75,
            "color_temperature": 3000,
        }

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        # Fetch device data
        success = device_detail_screen.fetch_device_data()

        # Assert
        assert success is True
        assert device_detail_screen.device is not None
        assert device_detail_screen.device["name"] == "Living Room Light"
        assert device_detail_screen.device_state is not None
        assert device_detail_screen.device_state["power"] == "on"
        assert mock_http_client.get.call_count == 2

    def test_fetch_device_data_no_device_id(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test fetch_device_data returns False when device_id is None."""
        success = device_detail_screen.fetch_device_data()
        assert success is False
        mock_http_client.get.assert_not_called()

    def test_fetch_device_data_error(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test device data fetch error handling."""
        device_detail_screen.set_device("light_01")

        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Fetch device data
        success = device_detail_screen.fetch_device_data()

        # Assert
        assert success is False
        assert device_detail_screen.device is None
        assert device_detail_screen.device_state is None

    def test_fetch_device_data_state_404_still_returns_device(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """State endpoint 404 should not block device detail rendering."""
        device_detail_screen.set_device("temp-001")

        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "id": "temp-001",
            "friendly_name": "Living Room Temp",
            "device_type": "temperature_sensor",
            "status": "online",
        }

        mock_state_response = MagicMock()
        mock_state_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        success = device_detail_screen.fetch_device_data()

        assert success is True
        assert device_detail_screen.device is not None
        assert device_detail_screen.device["id"] == "temp-001"
        assert device_detail_screen.device_state is None
        assert mock_http_client.get.call_count == 2

    def test_fetch_device_data_ignores_non_dict_state_payload(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Non-dict state JSON should be ignored while device info still loads."""
        device_detail_screen.set_device("temp-001")

        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "id": "temp-001",
            "friendly_name": "Living Room Temp",
            "device_type": "temperature_sensor",
            "status": "online",
        }

        mock_state_response = MagicMock()
        mock_state_response.json.return_value = ["unexpected", "list"]

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        success = device_detail_screen.fetch_device_data()

        assert success is True
        assert device_detail_screen.device is not None
        assert device_detail_screen.device["id"] == "temp-001"
        assert device_detail_screen.device_state is None
        assert mock_http_client.get.call_count == 2


class TestSendCommand:
    """Test send_command method."""

    def test_send_command_success(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test successful command send."""
        device_detail_screen.set_device("light_01")

        # Mock API response
        mock_response = MagicMock()
        mock_http_client.post.return_value = mock_response

        # Send command
        success = device_detail_screen.send_command("set_brightness", {"brightness": 80})

        # Assert
        assert success is True
        mock_http_client.post.assert_called_once_with(
            "/api/devices/light_01/command",
            json={"command": "set_brightness", "parameters": {"brightness": 80}},
        )

    def test_send_command_no_device_id(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test send_command returns False when device_id is None."""
        success = device_detail_screen.send_command("set_power", {"power": "on"})
        assert success is False
        mock_http_client.post.assert_not_called()

    def test_send_command_error(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test command send error handling."""
        device_detail_screen.set_device("light_01")

        # Mock API error
        mock_http_client.post.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Send command
        success = device_detail_screen.send_command("set_power", {"power": "on"})

        # Assert
        assert success is False


class TestRenderMethods:
    """Test rendering methods."""

    def test_render_header(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_header returns Panel."""
        device_detail_screen.device = {"name": "Test Light"}
        header = device_detail_screen._render_header()
        assert isinstance(header, Panel)

    def test_render_device_info_success(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_device_info with successful data."""
        device_detail_screen.device = {
            "device_id": "light_01",
            "name": "Living Room Light",
            "device_type": "smart_light",
            "status": "online",
            "location": "Living Room",
            "last_seen_at": "2026-02-26 12:30:45",
        }
        info_panel = device_detail_screen._render_device_info(api_success=True)
        assert isinstance(info_panel, Panel)

    def test_render_device_info_error(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_device_info with API error."""
        info_panel = device_detail_screen._render_device_info(api_success=False)
        assert isinstance(info_panel, Panel)

    def test_render_device_info_offline_status(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """Test _render_device_info with offline status."""
        device_detail_screen.device = {
            "device_id": "light_02",
            "name": "Bedroom Light",
            "device_type": "smart_light",
            "status": "offline",
            "location": "Bedroom",
        }
        info_panel = device_detail_screen._render_device_info(api_success=True)
        assert isinstance(info_panel, Panel)

    def test_render_device_info_unknown_status(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """Test _render_device_info with unknown status."""
        device_detail_screen.device = {
            "device_id": "light_03",
            "name": "Kitchen Light",
            "device_type": "smart_light",
            "status": "unknown",
            "location": "Kitchen",
        }
        info_panel = device_detail_screen._render_device_info(api_success=True)
        assert isinstance(info_panel, Panel)

    def test_render_device_info_includes_state_source_row(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """_render_device_info() shows state source when live updates are active."""
        device_detail_screen.device = {
            "id": "light_03",
            "friendly_name": "Kitchen Light",
            "device_type": "smart_light",
            "status": "online",
            "location": "Kitchen",
            "updated_at": "2026-02-26 12:30:45",
        }
        device_detail_screen.live_state_source = "sensor_data"

        info_panel = device_detail_screen._render_device_info(api_success=True)
        rendered = _panel_text(info_panel)

        assert "State Source:" in rendered
        assert "sensor_data" in rendered

    def test_render_light_state_with_data(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_light_state with device state data."""
        device_detail_screen.device_state = {
            "power": "on",
            "brightness": 75,
            "color_temperature": 3000,
        }
        state_panel = device_detail_screen._render_light_state()
        assert isinstance(state_panel, Panel)

    def test_render_light_state_no_data(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_light_state without device state data."""
        device_detail_screen.device_state = None
        state_panel = device_detail_screen._render_light_state()
        assert isinstance(state_panel, Panel)

    def test_render_light_state_without_brightness(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """Test _render_light_state with power but no brightness or color temp."""
        device_detail_screen.device_state = {
            "power": "off",
        }
        state_panel = device_detail_screen._render_light_state()
        assert isinstance(state_panel, Panel)

    def test_render_light_state_defaults_power_to_unknown(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """_render_light_state() shows UNKNOWN power when state lacks power key."""
        device_detail_screen.device_state = {"brightness": 20}

        state_panel = device_detail_screen._render_light_state()
        rendered = _panel_text(state_panel)

        assert "UNKNOWN" in rendered

    def test_render_light_state_includes_additional_state_keys(
        self, device_detail_screen: DeviceDetailScreen
    ) -> None:
        """_render_light_state() includes extra non-standard keys in the table."""
        device_detail_screen.device_state = {
            "power": "on",
            "brightness": 75,
            "battery": 88,
        }

        state_panel = device_detail_screen._render_light_state()
        rendered = _panel_text(state_panel)

        assert "battery:" in rendered
        assert "88" in rendered

    def test_render_light_controls(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_light_controls returns Panel."""
        controls = device_detail_screen._render_light_controls()
        assert isinstance(controls, Panel)

    def test_render_instructions(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_instructions returns Panel."""
        instructions = device_detail_screen._render_instructions()
        assert isinstance(instructions, Panel)

    def test_render_menu(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_menu returns Text."""
        menu = device_detail_screen._render_menu()
        assert isinstance(menu, Text)

    def test_render_progress_bar(self, device_detail_screen: DeviceDetailScreen) -> None:
        """Test _render_progress_bar returns Text."""
        progress_bar = device_detail_screen._render_progress_bar(75, 100, 30)
        assert isinstance(progress_bar, Text)


class TestRenderLive:
    """Test render_live method."""

    def test_render_live_fetches_device_data(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live fetches device data and returns Group."""
        device_detail_screen.set_device("light_01")

        # Mock API responses
        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "device_id": "light_01",
            "name": "Living Room Light",
            "device_type": "smart_light",
            "status": "online",
            "location": "Living Room",
            "last_seen_at": "2026-02-26 12:30:45",
        }

        mock_state_response = MagicMock()
        mock_state_response.json.return_value = {
            "power": "on",
            "brightness": 75,
            "color_temperature": 3000,
        }

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        # Render live
        result = device_detail_screen.render_live()

        # Assert
        assert isinstance(result, Group)
        assert mock_http_client.get.call_count == 2

    def test_render_live_non_light_device(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live for non-light device (no controls shown)."""
        device_detail_screen.set_device("sensor_01")

        # Mock API responses for sensor
        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "device_id": "sensor_01",
            "name": "Temperature Sensor",
            "device_type": "temperature_sensor",
            "status": "online",
        }

        mock_state_response = MagicMock()
        mock_state_response.json.return_value = {}

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        # Render live
        result = device_detail_screen.render_live()

        # Assert
        assert isinstance(result, Group)

    def test_render_live_handles_api_error(
        self, device_detail_screen: DeviceDetailScreen, mock_http_client: MagicMock
    ) -> None:
        """Test render_live handles API error gracefully."""
        device_detail_screen.set_device("light_01")

        # Mock API error
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        # Render live
        result = device_detail_screen.render_live()

        # Assert
        assert isinstance(result, Group)


class TestRender:
    """Test render method."""

    def test_render_calls_methods_smart_light(
        self,
        device_detail_screen: DeviceDetailScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test render method calls all rendering methods for smart light."""
        device_detail_screen.set_device("light_01")

        # Mock API responses
        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "device_id": "light_01",
            "name": "Living Room Light",
            "device_type": "smart_light",
            "status": "online",
            "location": "Living Room",
        }

        mock_state_response = MagicMock()
        mock_state_response.json.return_value = {
            "power": "on",
            "brightness": 75,
        }

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        # Render
        device_detail_screen.render()

        # Assert console.print was called multiple times (should be more for smart_light with controls)
        assert mock_console.print.call_count >= 7

    def test_render_calls_methods_non_light(
        self,
        device_detail_screen: DeviceDetailScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test render method calls all rendering methods for non-light device."""
        device_detail_screen.set_device("sensor_01")

        # Mock API responses
        mock_device_response = MagicMock()
        mock_device_response.json.return_value = {
            "device_id": "sensor_01",
            "name": "Temperature Sensor",
            "device_type": "temperature_sensor",
            "status": "online",
        }

        mock_state_response = MagicMock()
        mock_state_response.json.return_value = {}

        mock_http_client.get.side_effect = [mock_device_response, mock_state_response]

        # Render
        device_detail_screen.render()

        # Assert console.print was called
        assert mock_console.print.call_count >= 5

    def test_render_handles_api_error_without_state_or_controls(
        self,
        device_detail_screen: DeviceDetailScreen,
        mock_console: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """render() still shows layout when API fetch fails."""
        device_detail_screen.set_device("light_01")
        mock_http_client.get.side_effect = httpx.RequestError(
            "Connection error", request=MagicMock()
        )

        device_detail_screen.render()

        assert mock_console.print.call_count >= 5
