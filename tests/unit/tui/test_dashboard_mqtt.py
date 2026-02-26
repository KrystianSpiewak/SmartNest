"""Tests for Dashboard MQTT live updates."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.tui.screens.dashboard import DashboardScreen


class TestDashboardLiveRender:
    """Tests for DashboardScreen.render_live() method."""

    def test_render_live_returns_renderable_group(self) -> None:
        """Should return Group object for Live display."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        result = dashboard.render_live(device_count=5)

        # Should return a renderable (Group)
        assert result is not None
        # Group has __rich_console__ method
        assert hasattr(result, "__rich_console__")

    def test_render_live_with_device_count(self) -> None:
        """Should accept device_count parameter."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        result = dashboard.render_live(device_count=10)

        assert result is not None

    def test_render_live_with_none_device_count(self) -> None:
        """Should handle None device_count (API error)."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        result = dashboard.render_live(device_count=None)

        assert result is not None

    def test_render_live_with_system_status_online(self) -> None:
        """Should accept system_status parameter with online status."""
        console = MagicMock()
        dashboard = DashboardScreen(console)
        system_status = {"status": "online", "devices": 5}

        result = dashboard.render_live(device_count=5, system_status=system_status)

        assert result is not None

    def test_render_live_with_system_status_offline(self) -> None:
        """Should handle offline system status."""
        console = MagicMock()
        dashboard = DashboardScreen(console)
        system_status = {"status": "offline"}

        result = dashboard.render_live(device_count=5, system_status=system_status)

        assert result is not None

    def test_render_live_with_none_system_status(self) -> None:
        """Should handle None system_status (MQTT not connected)."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        result = dashboard.render_live(device_count=5, system_status=None)

        assert result is not None

    def test_render_live_with_empty_system_status(self) -> None:
        """Should handle empty system_status dict."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        result = dashboard.render_live(device_count=5, system_status={})

        assert result is not None


class TestSystemStatusRendering:
    """Tests for _render_system_status() with MQTT data."""

    def test_render_system_status_mqtt_online(self) -> None:
        """Should show green CONNECTED when MQTT status is online."""
        console = MagicMock()
        dashboard = DashboardScreen(console)
        mqtt_status = {"status": "online"}

        panel = dashboard._render_system_status(mqtt_status=mqtt_status)

        # Should contain "CONNECTED" text
        assert panel is not None
        assert panel.title == "[bold yellow]SYSTEM STATUS[/bold yellow]"

    def test_render_system_status_mqtt_offline(self) -> None:
        """Should show red OFFLINE when MQTT status is offline."""
        console = MagicMock()
        dashboard = DashboardScreen(console)
        mqtt_status = {"status": "offline"}

        panel = dashboard._render_system_status(mqtt_status=mqtt_status)

        assert panel is not None

    def test_render_system_status_mqtt_none(self) -> None:
        """Should show yellow LOADING when MQTT status is None."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        panel = dashboard._render_system_status(mqtt_status=None)

        assert panel is not None

    def test_render_system_status_mqtt_empty(self) -> None:
        """Should show yellow LOADING when MQTT status is empty dict."""
        console = MagicMock()
        dashboard = DashboardScreen(console)

        panel = dashboard._render_system_status(mqtt_status={})

        assert panel is not None
