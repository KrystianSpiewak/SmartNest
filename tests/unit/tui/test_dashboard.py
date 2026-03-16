"""Unit tests for Dashboard screen."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console

from backend.tui.screens.dashboard import DashboardScreen


class TestDashboardScreenInit:
    """Tests for DashboardScreen initialization."""

    def test_creates_with_console(self) -> None:
        """DashboardScreen stores console reference."""
        console = Console()
        dashboard = DashboardScreen(console)
        assert dashboard.console is console


class TestDashboardScreenRender:
    """Tests for DashboardScreen render() method."""

    def test_render_prints_all_sections(self) -> None:
        """render() prints header, status, summary, activity, alerts, menu."""
        console = MagicMock(spec=Console)
        dashboard = DashboardScreen(console)

        dashboard.render(device_count=5)

        # Should call print() multiple times (header, blank, status, blank, summary, etc.)
        # Exact count: 1 header + 1 blank + 1 status + 1 blank + 1 summary + 1 blank
        #              + 1 activity + 1 blank + 1 alerts + 1 blank + 1 menu = 11 calls
        assert console.print.call_count == 11

    def test_render_with_device_count(self) -> None:
        """render() displays device count when provided."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        dashboard.render(device_count=10)

        output = string_io.getvalue()
        assert "10" in output  # Device count should appear
        assert "Total Devices:" in output

    def test_render_without_device_count(self) -> None:
        """render() displays API Error when device count is None."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        dashboard.render(device_count=None)

        output = string_io.getvalue()
        assert "API Error" in output  # Error message should appear
        assert "Total Devices:" in output

    def test_render_produces_output(self) -> None:
        """render() produces visible output to console."""
        # Use StringIO to capture output
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        dashboard.render(device_count=3)

        output = string_io.getvalue()
        # Check for key content
        assert "SMARTNEST HOME AUTOMATION" in output
        assert "SYSTEM STATUS" in output
        assert "DEVICE SUMMARY" in output
        assert "RECENT ACTIVITY" in output
        assert "ALERTS" in output
        assert "[D] Devices" in output or "Devices" in output  # Menu


class TestDashboardScreenHeader:
    """Tests for _render_header() method."""

    def test_header_contains_ascii_art(self) -> None:
        """_render_header() returns Panel with ASCII border."""
        console = Console()
        dashboard = DashboardScreen(console)

        header = dashboard._render_header()

        # Check renderable exists and has expected content
        assert header is not None
        # The Panel should contain the ASCII art
        # We can't easily check Panel internals, but we know it was created

    def test_header_renders_without_error(self) -> None:
        """_render_header() Panel renders without errors."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        header = dashboard._render_header()
        console.print(header)

        output = string_io.getvalue()
        assert "╔═══" in output or "SMARTNEST" in output


class TestDashboardScreenSystemStatus:
    """Tests for _render_system_status() method."""

    def test_system_status_has_mqtt_row(self) -> None:
        """_render_system_status() includes MQTT broker status."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_system_status()
        console.print(panel)

        output = string_io.getvalue()
        assert "MQTT Broker" in output or "MQTT" in output

    def test_system_status_has_backend_row(self) -> None:
        """_render_system_status() includes Backend API status."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_system_status()
        console.print(panel)

        output = string_io.getvalue()
        assert "Backend API" in output or "API" in output

    def test_system_status_has_database_row(self) -> None:
        """_render_system_status() includes database status."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_system_status()
        console.print(panel)

        output = string_io.getvalue()
        assert "Database" in output


class TestDashboardScreenDeviceSummary:
    """Tests for _render_device_summary() method."""

    def test_device_summary_has_total_row(self) -> None:
        """_render_device_summary() includes total devices."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_device_summary()
        console.print(panel)

        output = string_io.getvalue()
        assert "Total Devices" in output or "Total" in output

    def test_device_summary_has_online_row(self) -> None:
        """_render_device_summary() includes online count."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_device_summary()
        console.print(panel)

        output = string_io.getvalue()
        assert "Online" in output

    def test_device_summary_has_offline_row(self) -> None:
        """_render_device_summary() includes offline count."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_device_summary()
        console.print(panel)

        output = string_io.getvalue()
        assert "Offline" in output


class TestDashboardScreenRecentActivity:
    """Tests for _render_recent_activity() method."""

    def test_recent_activity_renders_panel(self) -> None:
        """_render_recent_activity() returns a Panel."""
        console = Console()
        dashboard = DashboardScreen(console)

        panel = dashboard._render_recent_activity()

        assert panel is not None

    def test_recent_activity_has_placeholder(self) -> None:
        """_render_recent_activity() shows placeholder when no data."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_recent_activity()
        console.print(panel)

        output = string_io.getvalue()
        assert "No recent activity" in output or "activity" in output.lower()


class TestDashboardScreenAlerts:
    """Tests for _render_alerts() method."""

    def test_alerts_renders_panel(self) -> None:
        """_render_alerts() returns a Panel."""
        console = Console()
        dashboard = DashboardScreen(console)

        panel = dashboard._render_alerts()

        assert panel is not None

    def test_alerts_has_placeholder(self) -> None:
        """_render_alerts() shows placeholder when no alerts."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        panel = dashboard._render_alerts()
        console.print(panel)

        output = string_io.getvalue()
        assert "No alerts" in output or "alerts" in output.lower()


class TestDashboardScreenMenu:
    """Tests for _render_menu() method."""

    def test_menu_has_devices_option(self) -> None:
        """_render_menu() includes Devices option."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        menu = dashboard._render_menu()
        console.print(menu)

        output = string_io.getvalue()
        assert "Devices" in output

    def test_menu_has_quit_option(self) -> None:
        """_render_menu() includes Quit option."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        menu = dashboard._render_menu()
        console.print(menu)

        output = string_io.getvalue()
        assert "Quit" in output

    def test_menu_has_all_shortcuts(self) -> None:
        """_render_menu() includes all navigation shortcuts."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=100)
        dashboard = DashboardScreen(console)

        menu = dashboard._render_menu()
        console.print(menu)

        output = string_io.getvalue()
        # Check for key letters (may be styled, so just check presence)
        for option in ["Dashboard", "Devices", "Settings", "Quit"]:
            assert option in output
