"""SmartNest Reports Screen.

Displays system report snapshots in TUI format:
- Daily health
- Sensor summary
- Performance
- Security status
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import Console


class ReportsScreen:
    """Reports screen for SmartNest TUI."""

    def __init__(self, console: Console, http_client: httpx.Client) -> None:
        self.console = console
        self.http_client = http_client
        self.summary: dict[str, Any] = {}
        self._last_fetch_at = 0.0
        self._last_fetch_success = False
        self._fetch_interval_seconds = 2.0

    def fetch_summary(self) -> bool:
        """Fetch dashboard summary report data from API."""
        now = time.monotonic()
        if now - self._last_fetch_at < self._fetch_interval_seconds:
            return self._last_fetch_success

        try:
            response = self.http_client.get("/api/reports/dashboard-summary")
            response.raise_for_status()
            self.summary = response.json()
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError):
            self.summary = {}
            self._last_fetch_at = now
            self._last_fetch_success = False
            return False
        else:
            self._last_fetch_at = now
            self._last_fetch_success = True
            return True

    def refresh_now(self) -> bool:
        """Force-refresh summary outside the throttle interval."""
        self._last_fetch_at = 0.0
        return self.fetch_summary()

    def render_live(self) -> Group:
        """Render reports view for Rich Live updates."""
        api_success = self.fetch_summary()
        return Group(
            self._render_header(),
            Text(),
            self._render_report_table(api_success),
            Text(),
            self._render_actions(),
            Text(),
            self._render_menu(),
        )

    def _render_header(self) -> Panel:
        """Render reports page header."""
        return Panel(
            Text("REPORTS", justify="center", style="bold cyan"),
            border_style="dim",
            padding=(0, 0),
            expand=True,
        )

    def _render_report_table(self, api_success: bool) -> Panel:
        """Render report cards in a compact table."""
        if not api_success:
            return Panel(
                Text("API Error: Unable to fetch report data", style="bold red"),
                title="[bold yellow]REPORTS[/bold yellow]",
                title_align="left",
                border_style="red",
            )

        table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
        table.add_column(style="dim", width=24)
        table.add_column(style="bold")

        table.add_row(
            "Daily Health",
            f"Online {self.summary.get('online_devices', 0)} / Total {self.summary.get('total_devices', 0)}",
        )
        table.add_row("Sensor Summary", f"Sensor Devices: {self.summary.get('sensor_devices', 0)}")
        table.add_row("Performance", f"API Response: {self.summary.get('response_time_ms', 0)} ms")
        table.add_row("Security", "Auth and RBAC enabled")

        return Panel(
            table,
            title="[bold yellow]REPORTS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_menu(self) -> Text:
        """Render reports navigation hints."""
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

    def _render_actions(self) -> Panel:
        """Render reports actions panel."""
        actions = Text()
        actions.append("[R]", style="bold blue")
        actions.append(" Refresh Summary")
        return Panel(
            actions,
            title="[bold yellow]ACTIONS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )
