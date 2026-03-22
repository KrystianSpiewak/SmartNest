"""SmartNest Sensor View Screen.

Aggregated sensor data display with 24-hour statistics.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import Console


class SensorViewScreen:
    """Sensor view screen for SmartNest TUI.

    Displays aggregated sensor data with:
    - Latest readings for all sensors
    - 24-hour statistics (min, max, average)
    - Temperature and motion sensor support
    - Historical data visualization

    Attributes:
        console: Rich Console instance for rendering
        http_client: HTTP client for API requests
        sensor_data: Cached sensor readings from API
        sensor_stats: 24-hour statistics for sensors
    """

    def __init__(self, console: Console, http_client: httpx.Client) -> None:
        """Initialize sensor view screen.

        Args:
            console: Rich Console instance for rendering
            http_client: HTTP client for API requests
        """
        self.console = console
        self.http_client = http_client
        self.sensor_data: list[dict[str, Any]] = []
        self.sensor_stats: dict[str, Any] = {}
        self._sensor_data_last_fetch = 0.0
        self._sensor_data_last_success = False
        self._sensor_stats_last_fetch = 0.0
        self._sensor_stats_last_success = False
        self._fetch_interval_seconds = 2.0
        self._action_status = ""

    def fetch_sensor_data(self) -> bool:
        """Fetch latest sensor readings from API.

        Returns:
            True if successful, False on API error
        """
        now = time.monotonic()
        if now - self._sensor_data_last_fetch < self._fetch_interval_seconds:
            return self._sensor_data_last_success

        try:
            response = self.http_client.get("/api/sensors/latest")
            response.raise_for_status()
            data = response.json()
            self.sensor_data = data.get("readings", [])
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError):
            self.sensor_data = []
            self._sensor_data_last_fetch = now
            self._sensor_data_last_success = False
            return False
        else:
            self._sensor_data_last_fetch = now
            self._sensor_data_last_success = True
            return True

    def fetch_sensor_stats(self) -> bool:
        """Fetch 24-hour sensor statistics from API.

        Returns:
            True if successful, False on API error
        """
        now = time.monotonic()
        if now - self._sensor_stats_last_fetch < self._fetch_interval_seconds:
            return self._sensor_stats_last_success

        try:
            response = self.http_client.get("/api/sensors/stats/24h")
            response.raise_for_status()
            data = response.json()
            self.sensor_stats = data.get("stats", {})
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError):
            self.sensor_stats = {}
            self._sensor_stats_last_fetch = now
            self._sensor_stats_last_success = False
            return False
        else:
            self._sensor_stats_last_fetch = now
            self._sensor_stats_last_success = True
            return True

    def render(self) -> None:
        """Render the sensor view screen.

        Displays:
        - Latest sensor readings table
        - 24-hour statistics panel
        - Navigation instructions
        """
        # Fetch latest data
        data_success = self.fetch_sensor_data()
        stats_success = self.fetch_sensor_stats()

        # Header
        header = self._render_header()
        self.console.print(header)
        self.console.print()

        # Latest readings table
        readings_table = self._render_readings_table(data_success)
        self.console.print(readings_table)
        self.console.print()

        # 24-hour statistics
        stats_panel = self._render_statistics(stats_success)
        self.console.print(stats_panel)
        self.console.print()

        # Instructions
        instructions = self._render_instructions()
        self.console.print(instructions)
        self.console.print()

        # Menu
        menu = self._render_menu()
        self.console.print(menu)

    def render_live(self) -> Group:
        """Render sensor view as live-updatable Group.

        Returns:
            Rich Group containing all panels
        """
        data_success = self.fetch_sensor_data()
        stats_success = self.fetch_sensor_stats()

        return Group(
            self._render_header(),
            Text(),  # Blank line
            self._render_readings_table(data_success),
            Text(),  # Blank line
            self._render_statistics(stats_success),
            Text(),  # Blank line
            self._render_instructions(),
            Text(),  # Blank line
            self._render_menu(),
        )

    def _render_header(self) -> Panel:
        """Render sensor view header.

        Returns:
            Rich Panel with title
        """
        header_text = Text("SENSOR DATA", justify="center", style="bold cyan")
        return Panel(
            header_text,
            border_style="dim",
            padding=(0, 0),
            expand=True,
        )

    def _render_readings_table(self, api_success: bool) -> Panel:
        """Render latest sensor readings table.

        Args:
            api_success: Whether API fetch was successful

        Returns:
            Rich Panel with sensor readings or error message
        """
        if not api_success:
            error_text = Text("API Error: Unable to fetch sensor data", style="bold red")
            return Panel(
                error_text,
                title="[bold yellow]LATEST READINGS[/bold yellow]",
                title_align="left",
                border_style="red",
            )

        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Sensor", style="bold", width=25)
        table.add_column("Type", width=20)
        table.add_column("Value", justify="right", width=15)
        table.add_column("Timestamp", style="dim", width=20)

        for reading in self.sensor_data:
            # Format sensor type
            sensor_type = str(reading.get("sensor_type", "unknown"))
            sensor_type_display = sensor_type.replace("_", " ").title()

            # Format value with unit
            value = reading.get("value")
            unit = reading.get("unit", "")
            value_display = f"{value} {unit}" if value is not None else "N/A"

            # Format timestamp
            timestamp = reading.get("timestamp")
            timestamp_display = str(timestamp) if timestamp else "N/A"

            table.add_row(
                str(reading.get("device_name", "Unknown")),
                sensor_type_display,
                value_display,
                timestamp_display,
            )

        return Panel(
            table,
            title=f"[bold yellow]LATEST READINGS ({len(self.sensor_data)})[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_statistics(self, api_success: bool) -> Panel:
        """Render 24-hour sensor statistics panel.

        Args:
            api_success: Whether API fetch was successful

        Returns:
            Rich Panel with statistics or error message
        """
        if not api_success:
            error_text = Text("API Error: Unable to fetch statistics", style="bold red")
            return Panel(
                error_text,
                title="[bold yellow]24-HOUR STATISTICS[/bold yellow]",
                title_align="left",
                border_style="red",
            )

        if not self.sensor_stats:
            empty_text = Text("No statistics available", style="dim")
            return Panel(
                empty_text,
                title="[bold yellow]24-HOUR STATISTICS[/bold yellow]",
                title_align="left",
                border_style="blue",
            )

        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Sensor", style="bold", width=25)
        table.add_column("Min", justify="right", width=15)
        table.add_column("Max", justify="right", width=15)
        table.add_column("Avg", justify="right", width=15)
        table.add_column("Count", justify="right", width=10)

        for sensor_name, stats in self.sensor_stats.items():
            min_val = stats.get("min")
            max_val = stats.get("max")
            avg_val = stats.get("average")
            count = stats.get("count", 0)
            unit = stats.get("unit", "")

            # Format values with unit
            min_display = f"{min_val} {unit}" if min_val is not None else "N/A"
            max_display = f"{max_val} {unit}" if max_val is not None else "N/A"
            avg_display = f"{avg_val:.2f} {unit}" if avg_val is not None else "N/A"

            table.add_row(
                sensor_name,
                min_display,
                max_display,
                avg_display,
                str(count),
            )

        return Panel(
            table,
            title="[bold yellow]24-HOUR STATISTICS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_instructions(self) -> Panel:
        """Render instructions panel.

        Returns:
            Rich Panel with keyboard shortcuts
        """
        instructions = Text()
        instructions.append("[R]", style="bold blue")
        instructions.append(" Refresh  ")
        instructions.append("[E]", style="bold blue")
        instructions.append(" Export to CSV")

        if self._action_status:
            instructions.append("\nStatus: ", style="dim")
            instructions.append(self._action_status, style="bold cyan")

        return Panel(
            instructions,
            title="[bold yellow]ACTIONS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_menu(self) -> Text:
        """Render navigation menu at bottom.

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

    def refresh_now(self) -> bool:
        """Force refresh of both sensor readings and statistics.

        Returns:
            True if both data fetches succeed, False otherwise.
        """
        self._sensor_data_last_fetch = 0.0
        self._sensor_stats_last_fetch = 0.0
        data_ok = self.fetch_sensor_data()
        stats_ok = self.fetch_sensor_stats()
        self._action_status = "Refreshed" if data_ok and stats_ok else "Refresh failed"
        return data_ok and stats_ok

    def export_csv(self) -> str | None:
        """Export current sensor readings and statistics to a CSV file.

        Returns:
            Exported file path string on success, otherwise None.
        """
        # Ensure export has fresh data without requiring another render cycle.
        self.refresh_now()

        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = reports_dir / f"sensor_export_{timestamp}.csv"

        try:
            with export_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(
                    [
                        "record_type",
                        "name",
                        "sensor_type",
                        "value",
                        "unit",
                        "timestamp",
                        "min",
                        "max",
                        "average",
                        "count",
                    ]
                )

                for reading in self.sensor_data:
                    writer.writerow(
                        [
                            "reading",
                            reading.get("device_name", ""),
                            reading.get("sensor_type", ""),
                            reading.get("value", ""),
                            reading.get("unit", ""),
                            reading.get("timestamp", ""),
                            "",
                            "",
                            "",
                            "",
                        ]
                    )

                for sensor_name, stats in self.sensor_stats.items():
                    writer.writerow(
                        [
                            "stat",
                            sensor_name,
                            "",
                            "",
                            stats.get("unit", ""),
                            "",
                            stats.get("min", ""),
                            stats.get("max", ""),
                            stats.get("average", ""),
                            stats.get("count", ""),
                        ]
                    )
        except OSError:
            self._action_status = "Export failed"
            return None

        self._action_status = f"Exported: {export_path}"
        return str(export_path)
