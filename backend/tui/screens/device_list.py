"""SmartNest Device List Screen.

Tabular device listing with filtering by type and search functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    import httpx
    from rich.console import Console


class DeviceListScreen:
    """Device list screen for SmartNest TUI.

    Displays all devices in table format with:
    - Filtering by device type (lights, sensors, switches, all)
    - Search by name or location
    - Color-coded status indicators
    - Navigation to device detail view

    Attributes:
        console: Rich Console instance for rendering
        http_client: HTTP client for API requests
        devices: Cached list of devices from API
        filter_type: Current filter type (all, lights, sensors, switches)
        search_query: Current search query string
    """

    def __init__(self, console: Console, http_client: httpx.Client) -> None:
        """Initialize device list screen.

        Args:
            console: Rich Console instance for rendering
            http_client: HTTP client for API requests
        """
        self.console = console
        self.http_client = http_client
        self.devices: list[dict[str, Any]] = []
        self.filter_type = "all"
        self.search_query = ""

    def fetch_devices(self) -> bool:
        """Fetch devices from API and cache locally.

        Returns:
            True if successful, False on API error
        """
        try:
            response = self.http_client.get("/api/devices")
            response.raise_for_status()
            data = response.json()
            self.devices = data.get("devices", [])
        except Exception:
            self.devices = []
            return False
        else:
            return True

    def get_filtered_devices(self) -> list[dict[str, Any]]:
        """Get devices filtered by type and search query.

        Returns:
            List of devices matching current filters
        """
        filtered = self.devices

        # Filter by type
        if self.filter_type == "lights":
            filtered = [d for d in filtered if d.get("device_type") == "smart_light"]
        elif self.filter_type == "sensors":
            filtered = [
                d
                for d in filtered
                if d.get("device_type") in ("temperature_sensor", "motion_sensor")
            ]
        elif self.filter_type == "switches":
            filtered = [d for d in filtered if d.get("device_type") == "smart_switch"]

        # Filter by search query
        if self.search_query:
            query_lower = self.search_query.lower()
            filtered = [
                d
                for d in filtered
                if query_lower in str(d.get("name", "")).lower()
                or query_lower in str(d.get("location", "")).lower()
            ]

        return filtered

    def set_filter(self, filter_type: str) -> None:
        """Set device type filter.

        Args:
            filter_type: Filter type (all, lights, sensors, switches)
        """
        if filter_type in ("all", "lights", "sensors", "switches"):
            self.filter_type = filter_type

    def set_search(self, query: str) -> None:
        """Set search query.

        Args:
            query: Search string (case-insensitive)
        """
        self.search_query = query

    def render(self) -> None:
        """Render the device list screen.

        Displays:
        - Device table (ID, Name, Type, Status, Location, Last Seen)
        - Active filter indicator
        - Search query display
        - Navigation instructions
        """
        # Fetch latest devices
        success = self.fetch_devices()

        # Header
        header = self._render_header()
        self.console.print(header)
        self.console.print()

        # Filter bar
        filter_bar = self._render_filter_bar()
        self.console.print(filter_bar)
        self.console.print()

        # Device table
        device_table = self._render_device_table(success)
        self.console.print(device_table)
        self.console.print()

        # Instructions
        instructions = self._render_instructions()
        self.console.print(instructions)
        self.console.print()

        # Menu
        menu = self._render_menu()
        self.console.print(menu)

    def render_live(self) -> Group:
        """Render device list as live-updatable Group.

        Returns:
            Rich Group containing all panels
        """
        success = self.fetch_devices()

        return Group(
            self._render_filter_bar(),
            Text(),  # Blank line
            self._render_device_table(success),
            Text(),  # Blank line
            self._render_instructions(),
            Text(),  # Blank line
            self._render_menu(),
        )

    def _render_header(self) -> Panel:
        """Render device list header.

        Returns:
            Rich Panel with title
        """
        header_text = Text("DEVICE LIST", justify="center", style="bold cyan")
        return Panel(
            header_text,
            border_style="dim",
            padding=(0, 0),
            expand=True,
        )

    def _render_filter_bar(self) -> Panel:
        """Render filter status bar.

        Returns:
            Rich Panel with active filter and search query
        """
        filter_text = Text()
        filter_text.append("Filter: ", style="dim")
        filter_text.append(self.filter_type.upper(), style="bold yellow")

        if self.search_query:
            filter_text.append("  |  Search: ", style="dim")
            filter_text.append(f'"{self.search_query}"', style="bold cyan")

        return Panel(
            filter_text,
            title="[bold yellow]FILTERS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_device_table(self, api_success: bool) -> Panel:
        """Render device list table.

        Args:
            api_success: Whether API fetch was successful

        Returns:
            Rich Panel with device table or error message
        """
        if not api_success:
            error_text = Text("API Error: Unable to fetch devices", style="bold red")
            return Panel(
                error_text,
                title="[bold yellow]DEVICES[/bold yellow]",
                title_align="left",
                border_style="red",
            )

        # Get filtered devices
        filtered_devices = self.get_filtered_devices()

        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("ID", style="dim", width=10)
        table.add_column("Name", style="bold", width=25)
        table.add_column("Type", width=20)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Location", style="dim", width=20)
        table.add_column("Last Seen", style="dim", width=12)

        for device in filtered_devices:
            # Status styling
            status = str(device.get("status", "unknown"))
            if status == "online":
                status_text = Text("● ONLINE", style="bold green")
            elif status == "offline":
                status_text = Text("● OFFLINE", style="bold red")
            else:
                status_text = Text("● UNKNOWN", style="bold yellow")

            # Format device_type for display
            device_type = str(device.get("device_type", "unknown"))
            device_type_display = device_type.replace("_", " ").title()

            # Format last_seen (show just time if available)
            last_seen = device.get("last_seen_at")
            last_seen_display = str(last_seen)[11:19] if last_seen else "Never"  # HH:MM:SS

            table.add_row(
                str(device.get("device_id", "")),
                str(device.get("name", "")),
                device_type_display,
                status_text,
                str(device.get("location", "")),
                last_seen_display,
            )

        return Panel(
            table,
            title=f"[bold yellow]DEVICES ({len(filtered_devices)}/{len(self.devices)})[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_instructions(self) -> Panel:
        """Render instructions panel.

        Returns:
            Rich Panel with keyboard shortcuts
        """
        instructions = Text()
        instructions.append("[L]", style="bold blue")
        instructions.append(" Lights  ")
        instructions.append("[S]", style="bold blue")
        instructions.append(" Sensors  ")
        instructions.append("[W]", style="bold blue")
        instructions.append(" Switches  ")
        instructions.append("[A]", style="bold blue")
        instructions.append(" All  ")
        instructions.append("[/]", style="bold blue")
        instructions.append(" Search  ")
        instructions.append("[Enter]", style="bold blue")
        instructions.append(" Details")

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
        menu.append("[F1]", style="bold blue")
        menu.append(" Dashboard  ")
        menu.append("[F2]", style="bold blue")
        menu.append(" Settings  ")
        menu.append("[F3]", style="bold blue")
        menu.append(" Devices  ")
        menu.append("[Q]", style="bold blue")
        menu.append(" Quit")

        return menu
