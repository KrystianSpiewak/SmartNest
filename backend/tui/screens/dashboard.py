"""SmartNest Dashboard Screen.

Main dashboard displaying system status, device summary, recent activity, and alerts.
"""

from __future__ import annotations

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

    def render(self) -> None:
        """Render the dashboard screen with static content.

        Currently displays placeholder data. Future phases will integrate:
        - API calls for real device counts
        - MQTT live updates for system status
        - Real-time activity feed
        """

        # Header
        header = self._render_header()
        self.console.print(header)
        self.console.print()

        # System Status
        system_status = self._render_system_status()
        self.console.print(system_status)
        self.console.print()

        # Device Summary
        device_summary = self._render_device_summary()
        self.console.print(device_summary)
        self.console.print()

        # Recent Activity
        recent_activity = self._render_recent_activity()
        self.console.print(recent_activity)
        self.console.print()

        # Alerts
        alerts = self._render_alerts()
        self.console.print(alerts)
        self.console.print()

        # Menu
        menu = self._render_menu()
        self.console.print(menu)

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

    def _render_system_status(self) -> Panel:
        """Render system status panel.

        Shows status of MQTT broker, backend API, and database.
        Currently uses placeholder data.

        Returns:
            Rich Panel with system status table
        """
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="left")
        table.add_column(justify="left")
        table.add_column(style="dim", justify="left")

        # MQTT Broker
        table.add_row(
            "MQTT Broker:",
            Text("● CONNECTED", style="bold green"),
            "Uptime: --",
        )

        # Backend API
        table.add_row(
            "Backend API:",
            Text("● LOADING...", style="bold yellow"),
            "Response Time: --",
        )

        # Database
        table.add_row(
            "Database:",
            Text("● LOADING...", style="bold yellow"),
            "Size: --",
        )

        return Panel(
            table,
            title="[bold yellow]SYSTEM STATUS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_device_summary(self) -> Panel:
        """Render device summary panel.

        Shows total devices, online count, and offline count.
        Currently uses placeholder data.

        Returns:
            Rich Panel with device statistics table
        """
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="left")
        table.add_column(justify="left")
        table.add_column(justify="left")

        # Total Devices
        table.add_row(
            "Total Devices:",
            Text("Loading...", style="bold white"),
            "",
        )

        # Online Devices
        table.add_row(
            "Online:",
            Text("--", style="bold green"),
            Text("█" * 10, style="green"),
        )

        # Offline Devices
        table.add_row(
            "Offline:",
            Text("--", style="bold red"),
            "",
        )

        return Panel(
            table,
            title="[bold yellow]DEVICE SUMMARY[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_recent_activity(self) -> Panel:
        """Render recent activity log panel.

        Shows last N device state changes and events.
        Currently uses placeholder data.

        Returns:
            Rich Panel with activity log entries
        """
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

    def _render_alerts(self) -> Panel:
        """Render alerts and warnings panel.

        Shows critical alerts (offline devices, errors, etc.).
        Currently uses placeholder data.

        Returns:
            Rich Panel with alert messages
        """
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
        menu.append("[D]", style="bold blue")
        menu.append(" Devices  ")
        menu.append("[S]", style="bold blue")
        menu.append(" Sensors  ")
        menu.append("[R]", style="bold blue")
        menu.append(" Reports  ")
        menu.append("[L]", style="bold blue")
        menu.append(" Logs  ")
        menu.append("[A]", style="bold blue")
        menu.append(" Settings  ")
        menu.append("[Q]", style="bold blue")
        menu.append(" Quit")

        return menu
