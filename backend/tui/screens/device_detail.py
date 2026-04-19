"""SmartNest Device Detail Screen.

Detailed device view with interactive controls for smart lights.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import Console


class DeviceDetailScreen:
    """Device detail screen for SmartNest TUI.

    Shows comprehensive device information and provides interactive controls
    for device-specific operations (e.g., brightness, color temp for lights).

    Attributes:
        console: Rich Console instance for rendering
        http_client: HTTP client for API requests
        device_id: Currently displayed device ID
        device: Cached device data from API
        device_state: Current device state from API
    """

    def __init__(self, console: Console, http_client: httpx.Client) -> None:
        """Initialize device detail screen.

        Args:
            console: Rich Console instance for rendering
            http_client: HTTP client for API requests
        """
        self.console = console
        self.http_client = http_client
        self.device_id: str | None = None
        self.device: dict[str, Any] | None = None
        self.device_state: dict[str, Any] | None = None
        self.live_state: dict[str, Any] | None = None
        self.live_state_source: str | None = None

    def set_device(self, device_id: str) -> None:
        """Set the device to display.

        Args:
            device_id: Device ID to display
        """
        self.device_id = device_id
        self.device = None
        self.device_state = None
        self.live_state = None
        self.live_state_source = None

    def apply_live_state_update(self, state: dict[str, Any], source: str = "mqtt") -> None:
        """Apply real-time state update received from MQTT callbacks.

        Args:
            state: Incoming live device state payload.
            source: Event source label (e.g., mqtt_state, sensor_data).
        """
        self.live_state = dict(state)
        self.live_state_source = source

    @staticmethod
    def _device_field(device: dict[str, Any], *keys: str, default: str = "N/A") -> str:
        """Return first non-empty string value from preferred device field names."""
        for key in keys:
            value = device.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return default

    def _effective_state(self) -> dict[str, Any] | None:
        """Return merged state where live MQTT values override API values."""
        if not self.device_state and not self.live_state:
            return None

        merged: dict[str, Any] = {}
        if isinstance(self.device_state, dict):
            merged.update(self.device_state)
        if isinstance(self.live_state, dict):
            merged.update(self.live_state)
        return merged

    def _is_smart_light(self) -> bool:
        """Return True when selected device is a smart light category."""
        if not self.device:
            return False
        device_type = str(self.device.get("device_type", "")).strip().lower()
        return device_type in {"smart_light", "light"}

    def fetch_device_data(self) -> bool:
        """Fetch device data and state from API.

        Returns:
            True if successful, False on API error
        """
        if not self.device_id:
            return False

        try:
            # Fetch device info
            response = self.http_client.get(f"/api/devices/{self.device_id}")
            response.raise_for_status()
            self.device = response.json()
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException):
            self.device = None
            self.device_state = None
            return False

        # Fetch device state as best-effort: detail screen should still render
        # basic device info when state endpoint is unavailable.
        self.device_state = None
        try:
            state_response = self.http_client.get(f"/api/devices/{self.device_id}/state")
            state_response.raise_for_status()
            state_payload = state_response.json()
            if isinstance(state_payload, dict):
                self.device_state = state_payload
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError):
            self.device_state = None

        return True

    def send_command(self, command: str, parameters: dict[str, Any]) -> bool:
        """Send command to device via API.

        Args:
            command: Command name (e.g., "set_power", "set_brightness")
            parameters: Command parameters

        Returns:
            True if successful, False on error
        """
        if not self.device_id:
            return False

        try:
            response = self.http_client.post(
                f"/api/devices/{self.device_id}/command",
                json={"command": command, "parameters": parameters},
            )
            response.raise_for_status()
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException):
            return False
        else:
            return True

    def render(self) -> None:
        """Render the device detail screen.

        Displays:
        - Device info (ID, name, type, status, location)
        - Current state (power, brightness, color temp for lights)
        - Interactive controls
        - Command history (if available)
        """
        # Fetch latest device data
        success = self.fetch_device_data()

        # Header
        header = self._render_header()
        self.console.print(header)
        self.console.print()

        # Device info
        device_info = self._render_device_info(success)
        self.console.print(device_info)
        self.console.print()

        # Device state
        if success:
            state_panel = self._render_light_state()
            self.console.print(state_panel)
            self.console.print()

        # Controls for smart lights
        if success and self._is_smart_light():
            controls = self._render_light_controls()
            self.console.print(controls)
            self.console.print()

        # Instructions
        instructions = self._render_instructions()
        self.console.print(instructions)
        self.console.print()

        # Menu
        menu = self._render_menu()
        self.console.print(menu)

    def render_live(self) -> Group:
        """Render device detail as live-updatable Group.

        Returns:
            Rich Group containing all panels
        """
        success = self.fetch_device_data()

        if success and self._is_smart_light():
            return Group(
                self._render_header(),
                Text(),  # Blank line
                self._render_device_info(success),
                Text(),  # Blank line
                self._render_light_state(),
                Text(),  # Blank line
                self._render_light_controls(),
                Text(),  # Blank line
                self._render_instructions(),
                Text(),  # Blank line
                self._render_menu(),
            )
        if success:
            return Group(
                self._render_header(),
                Text(),  # Blank line
                self._render_device_info(success),
                Text(),  # Blank line
                self._render_light_state(),
                Text(),  # Blank line
                self._render_instructions(),
                Text(),  # Blank line
                self._render_menu(),
            )
        else:
            return Group(
                self._render_header(),
                Text(),  # Blank line
                self._render_device_info(success),
                Text(),  # Blank line
                self._render_instructions(),
                Text(),  # Blank line
                self._render_menu(),
            )

    def _render_header(self) -> Panel:
        """Render device detail header.

        Returns:
            Rich Panel with title
        """
        if self.device:
            device_name = self._device_field(self.device, "friendly_name", "name")
        else:
            device_name = "Device Detail"
        header_text = Text(f"DEVICE: {device_name}", justify="center", style="bold cyan")
        return Panel(
            header_text,
            border_style="dim",
            padding=(0, 0),
            expand=True,
        )

    def _render_device_info(self, api_success: bool) -> Panel:
        """Render device information panel.

        Args:
            api_success: Whether API fetch was successful

        Returns:
            Rich Panel with device info or error message
        """
        if not api_success or not self.device:
            error_text = Text("API Error: Unable to fetch device", style="bold red")
            return Panel(
                error_text,
                title="[bold yellow]DEVICE INFO[/bold yellow]",
                title_align="left",
                border_style="red",
            )

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim", width=20)
        table.add_column("Value", style="bold")

        # Device ID
        table.add_row("Device ID:", self._device_field(self.device, "id", "device_id"))

        # Name
        table.add_row("Name:", self._device_field(self.device, "friendly_name", "name"))

        # Type
        device_type = str(self.device.get("device_type", "unknown"))
        device_type_display = device_type.replace("_", " ").title()
        table.add_row("Type:", device_type_display)

        # Status
        status = str(self.device.get("status", "unknown"))
        if status == "online":
            status_text = Text("● ONLINE", style="bold green")
        elif status == "offline":
            status_text = Text("● OFFLINE", style="bold red")
        else:
            status_text = Text("● UNKNOWN", style="bold yellow")
        table.add_row("Status:", status_text)

        # Location
        table.add_row("Location:", self._device_field(self.device, "location"))

        # Last Seen
        last_seen = self.device.get("last_seen_at") or self.device.get("updated_at")
        last_seen_display = str(last_seen) if last_seen else "Never"
        table.add_row("Last Seen:", last_seen_display)

        if self.live_state_source:
            table.add_row("State Source:", self.live_state_source)

        return Panel(
            table,
            title="[bold yellow]DEVICE INFO[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_light_state(self) -> Panel:
        """Render smart light state panel.

        Returns:
            Rich Panel with light state
        """
        current_state = self._effective_state()
        if not current_state:
            return Panel(
                Text("State unavailable", style="dim"),
                title="[bold yellow]DEVICE STATE[/bold yellow]",
                title_align="left",
                border_style="blue",
            )

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim", width=20)
        table.add_column("Value", style="bold")

        # Power
        power = current_state.get("power")
        power_is_on = power in {"on", "ON", "true", "True", True}
        if power is None:
            power_text = Text("UNKNOWN", style="bold yellow")
        elif power_is_on:
            power_text = Text("ON", style="bold green")
        else:
            power_text = Text("OFF", style="bold red")
        table.add_row("Power:", power_text)

        # Brightness (if available)
        brightness = current_state.get("brightness")
        if brightness is not None:
            brightness_bar = self._render_progress_bar(int(brightness), 100)
            table.add_row("Brightness:", brightness_bar)

        # Color Temperature (if available)
        color_temp = current_state.get("color_temperature")
        if color_temp is None:
            color_temp = current_state.get("color_temp")
        if color_temp is not None:
            table.add_row("Color Temp:", f"{color_temp}K")

        # Render any additional state keys not covered by the special rows above.
        for key in sorted(current_state):
            if key in {"power", "brightness", "color_temperature", "color_temp"}:
                continue
            table.add_row(f"{key}:", str(current_state[key]))

        return Panel(
            table,
            title="[bold yellow]DEVICE STATE[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_light_controls(self) -> Panel:
        """Render smart light controls panel.

        Returns:
            Rich Panel with control instructions
        """
        controls = Text()
        controls.append("[P]", style="bold blue")
        controls.append(" Toggle Power  ")
        controls.append("[+/-]", style="bold blue")
        controls.append(" Brightness (±10%)  ")
        controls.append("[↑/↓]", style="bold blue")
        controls.append(" Color Temp (±500K)")

        return Panel(
            controls,
            title="[bold yellow]CONTROLS[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_instructions(self) -> Panel:
        """Render instructions panel.

        Returns:
            Rich Panel with keyboard shortcuts
        """
        instructions = Text()
        instructions.append("[Esc]", style="bold blue")
        instructions.append(" Back to Device List  ")
        instructions.append("[R]", style="bold blue")
        instructions.append(" Refresh")

        return Panel(
            instructions,
            title="[bold yellow]NAVIGATION[/bold yellow]",
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

    def _render_progress_bar(self, value: int, max_value: int, width: int = 30) -> Text:
        """Render a simple progress bar.

        Args:
            value: Current value
            max_value: Maximum value
            width: Bar width in characters

        Returns:
            Rich Text with progress bar
        """
        filled = int((value / max_value) * width)
        bar = Text()
        bar.append("█" * filled, style="bold cyan")
        bar.append("░" * (width - filled), style="dim")
        bar.append(f" {value}%", style="bold")
        return bar
