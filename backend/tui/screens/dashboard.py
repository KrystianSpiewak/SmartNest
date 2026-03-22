"""SmartNest Dashboard Screen.

Main dashboard displaying system status, device summary, recent activity, and alerts.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class DashboardScreen:
    """Main dashboard screen for SmartNest TUI.

    Displays:
    - System status (MQTT, Backend API, Database)
    - Device summary (total, online, offline)
    - Recent activity log
    - Alerts and warnings
    - Navigation menu
    """

    def __init__(self, console: Console) -> None:
        """Initialize dashboard screen.

        Args:
            console: Rich Console instance for rendering
        """
        self.console = console

    def render(
        self,
        device_count: int | None = None,
        system_status: dict[str, Any] | None = None,
        summary: dict[str, Any] | None = None,
    ) -> None:
        """Render the dashboard screen with static content.

        Currently displays placeholder data. Future phases will integrate:
        - API calls for real device counts
        - MQTT live updates for system status
        - Real-time activity feed

        Args:
            device_count: Total number of devices (None if API unavailable)
        """

        # Header
        header = self._render_header()
        self.console.print(header)
        self.console.print()

        # System Status
        status_panel = self._render_system_status(mqtt_status=system_status, summary=summary)
        self.console.print(status_panel)
        self.console.print()

        # Device Summary
        device_summary = self._render_device_summary(device_count=device_count, summary=summary)
        self.console.print(device_summary)
        self.console.print()

        # Recent Activity
        recent_activity = self._render_recent_activity(summary=summary)
        self.console.print(recent_activity)
        self.console.print()

        # Alerts
        alerts = self._render_alerts(summary=summary)
        self.console.print(alerts)
        self.console.print()

        # Menu
        menu = self._render_menu()
        self.console.print(menu)

    def render_live(
        self,
        device_count: int | None = None,
        system_status: dict[str, Any] | None = None,
        summary: dict[str, Any] | None = None,
    ) -> Group:
        """Render dashboard as a live-updatable Group.

        Used with Rich Live for real-time updates at 4 FPS.

        Args:
            device_count: Total number of devices (None if API unavailable)
            system_status: System status from MQTT (None if not connected)

        Returns:
            Rich Group containing all dashboard panels
        """
        return Group(
            self._render_header(),
            Text(),  # Blank line
            self._render_system_status(mqtt_status=system_status, summary=summary),
            Text(),  # Blank line
            self._render_device_summary(device_count=device_count, summary=summary),
            Text(),  # Blank line
            self._render_recent_activity(summary=summary),
            Text(),  # Blank line
            self._render_alerts(summary=summary),
            Text(),  # Blank line
            self._render_menu(),
            Text(),  # Blank line
            Text("Press [q] or Ctrl+C to exit.", style="dim", justify="center"),
        )

    def _render_header(self) -> Panel:
        """Render ASCII art header with title.

        Returns:
            Rich Panel with ASCII border and title
        """
        header_art = Text(justify="center")
        header_art.append(
            "╔═══════════════════════════════════════════════════════════════════════╗\n",
            style="cyan",
        )
        header_art.append(
            "║                      SMARTNEST HOME AUTOMATION                        ║\n",
            style="cyan",
        )
        header_art.append(
            "╚═══════════════════════════════════════════════════════════════════════╝",
            style="cyan",
        )

        return Panel(
            header_art,
            border_style="dim",
            padding=(0, 0),
            expand=True,
        )

    def _render_system_status(
        self,
        mqtt_status: dict[str, Any] | None = None,
        summary: dict[str, Any] | None = None,
    ) -> Panel:
        """Render system status panel.

        Shows status of MQTT broker, backend API, and database.
        Displays real-time data from MQTT messages or placeholders.

        Args:
            mqtt_status: System status from MQTT (None if not connected)

        Returns:
            Rich Panel with system status table
        """
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="left")
        table.add_column(justify="left")
        table.add_column(style="dim", justify="left")

        # MQTT Broker - prefer explicit status payload, fall back to connection state.
        status_value = (mqtt_status or {}).get("status")
        if status_value == "online":
            mqtt_text = Text("● CONNECTED", style="bold green")
        elif status_value == "offline":
            mqtt_text = Text("● OFFLINE", style="bold red")
        elif (mqtt_status or {}).get("connected") is True:
            mqtt_text = Text("● CONNECTED", style="bold green")
        else:
            mqtt_text = Text("● WAITING", style="bold yellow")

        uptime = (mqtt_status or {}).get("uptime", "--")
        table.add_row("MQTT Broker:", mqtt_text, f"Uptime: {uptime}")

        # Backend API
        table.add_row(
            "Backend API:",
            Text(
                f"● {str((summary or {}).get('backend_status', 'loading')).upper()}",
                style=(
                    "bold green"
                    if (summary or {}).get("backend_status") == "online"
                    else "bold yellow"
                ),
            ),
            f"Response Time: {(summary or {}).get('response_time_ms', '--')} ms",
        )

        # Database
        table.add_row(
            "Database:",
            Text(
                f"● {str((summary or {}).get('database_status', 'loading')).upper()}",
                style=(
                    "bold green"
                    if (summary or {}).get("database_status") == "online"
                    else "bold yellow"
                ),
            ),
            f"Size: {(summary or {}).get('database_size_mb', '--')} MB",
        )

        return Panel(
            table,
            title="[bold yellow]SYSTEM STATUS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_device_summary(
        self,
        device_count: int | None = None,
        summary: dict[str, Any] | None = None,
    ) -> Panel:
        """Render device summary panel.

        Shows total devices, online count, and offline count.
        Currently uses placeholder data for online/offline counts.

        Args:
            device_count: Total number of devices (None if API unavailable)

        Returns:
            Rich Panel with device statistics table
        """
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="left")
        table.add_column(justify="left")
        table.add_column(justify="left")

        # Total Devices - show count from API or error message
        if device_count is not None:
            count_text = Text(str(device_count), style="bold white")
        else:
            count_text = Text("API Error", style="bold red")

        table.add_row(
            "Total Devices:",
            count_text,
            "",
        )

        online_count = int((summary or {}).get("online_devices", 0))
        offline_count = int((summary or {}).get("offline_devices", 0))

        # Online Devices
        table.add_row(
            "Online:",
            Text(str(online_count), style="bold green"),
            "",
        )

        # Offline Devices
        table.add_row(
            "Offline:",
            Text(str(offline_count), style="bold red"),
            "",
        )

        table.add_row(
            "Sensor Devices:",
            Text(str((summary or {}).get("sensor_devices", 0)), style="bold cyan"),
            "",
        )

        return Panel(
            table,
            title="[bold yellow]DEVICE SUMMARY[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_recent_activity(self, summary: dict[str, Any] | None = None) -> Panel:
        """Render recent activity log panel.

        Shows last N device state changes and events.
        Currently uses placeholder data.

        Returns:
            Rich Panel with activity log entries
        """
        activity = (summary or {}).get("recent_activity", [])
        if activity:
            activity_lines = [Text(line, style="dim") for line in activity]
        else:
            activity_lines = [
                Text("--:--:-- ", style="dim") + Text("No recent activity", style="dim italic"),
            ]

        content = Group(*activity_lines)

        return Panel(
            content,
            title="[bold yellow]RECENT ACTIVITY[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_alerts(self, summary: dict[str, Any] | None = None) -> Panel:
        """Render alerts and warnings panel.

        Shows critical alerts (offline devices, errors, etc.).
        Currently uses placeholder data.

        Returns:
            Rich Panel with alert messages
        """
        alerts = (summary or {}).get("alerts", [])
        if alerts:
            alert_lines = [Text(f"• {alert}", style="bold yellow") for alert in alerts]
        else:
            alert_lines = [
                Text("No alerts", style="dim italic"),
            ]

        content = Group(*alert_lines)

        return Panel(
            content,
            title="[bold yellow]ALERTS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_menu(self) -> Text:
        """Render navigation menu at bottom.

        Shows keyboard shortcuts for navigation.

        Returns:
            Rich Text with menu options
        """
        menu = Text()
        menu.append("[1]", style="bold blue")
        menu.append(" Dashboard  ")
        menu.append("[2]", style="bold blue")
        menu.append(" Devices  ")
        menu.append("[3]", style="bold blue")
        menu.append(" Settings  ")
        menu.append("[4]", style="bold blue")
        menu.append(" Sensors  ")
        menu.append("[5]", style="bold blue")
        menu.append(" Reports  ")
        menu.append("[Q]", style="bold blue")
        menu.append(" Quit")

        return menu
