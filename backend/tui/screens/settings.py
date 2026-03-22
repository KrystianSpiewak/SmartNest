"""SmartNest Settings Screen.

User management interface with CRUD operations for user accounts.
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


class SettingsScreen:
    """Settings screen for SmartNest TUI.

    Provides user management functionality:
    - List all users in table format
    - Add new users via form input
    - Remove users with confirmation
    - View user details

    Attributes:
        console: Rich Console instance for rendering
        http_client: HTTP client for API requests
        users: Cached list of users from API
    """

    def __init__(self, console: Console, http_client: httpx.Client) -> None:
        """Initialize settings screen.

        Args:
            console: Rich Console instance for rendering
            http_client: HTTP client for API requests
        """
        self.console = console
        self.http_client = http_client
        self.users: list[dict[str, Any]] = []
        self._last_fetch_at = 0.0
        self._last_fetch_success = False
        self._fetch_interval_seconds = 2.0

    def fetch_users(self) -> bool:
        """Fetch users from API and cache locally.

        Returns:
            True if successful, False on API error
        """
        now = time.monotonic()
        if now - self._last_fetch_at < self._fetch_interval_seconds:
            return self._last_fetch_success

        try:
            response = self.http_client.get("/api/users")
            response.raise_for_status()
            self.users = response.json()
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError):
            self.users = []
            self._last_fetch_at = now
            self._last_fetch_success = False
            return False
        else:
            self._last_fetch_at = now
            self._last_fetch_success = True
            return True

    def prompt_add_user(self) -> bool:
        """Prompt for new user details and create via API.

        Must be called outside the Rich Live context to allow console input.

        Returns:
            True if user was created successfully, False otherwise.
        """
        username = self.console.input("[bold]Username:[/bold] ")
        if not username.strip():
            return False
        email_default = f"{username.strip()}@example.com"
        email = (
            self.console.input(f"[bold]Email (default: {email_default}):[/bold] ") or email_default
        )
        if not email.strip():
            return False
        password = self.console.input("[bold]Password:[/bold] ", password=True)
        if not password.strip():
            return False
        role = (
            self.console.input("[bold]Role (admin/user/readonly, default: user):[/bold] ") or "user"
        )

        try:
            response = self.http_client.post(
                "/api/users",
                json={
                    "username": username.strip(),
                    "email": email.strip(),
                    "password": password.strip(),
                    "role": role.strip() or "user",
                },
            )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
        except httpx.HTTPStatusError:
            # Show backend validation details (e.g., password complexity, invalid email).
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            if detail:
                self.console.print(f"[bold red]Add user failed:[/bold red] {detail}")
            return False
        else:
            self._last_fetch_at = 0.0
            return True

    def prompt_delete_user(self) -> bool:
        """Prompt for a user ID and delete that user via API.

        Must be called outside the Rich Live context to allow console input.

        Returns:
            True if user was deleted successfully, False otherwise.
        """
        if not self.users:
            return False

        user_id_str = self.console.input("[bold]User ID to delete:[/bold] ")
        if not user_id_str.strip():
            return False

        try:
            user_id = int(user_id_str.strip())
            response = self.http_client.delete(f"/api/users/{user_id}")
            response.raise_for_status()
        except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException, ValueError):
            return False
        else:
            self._last_fetch_at = 0.0
            return True

    def render(self) -> None:
        """Render the settings screen with user management.

        Displays:
        - User list table (ID, Username, Email, Role, Active, Created)
        - Instructions for user management
        - Navigation menu
        """
        # Fetch latest users
        success = self.fetch_users()

        # Header
        header = self._render_header()
        self.console.print(header)
        self.console.print()

        # User List
        user_table = self._render_user_table(success)
        self.console.print(user_table)
        self.console.print()

        # Instructions
        instructions = self._render_instructions()
        self.console.print(instructions)
        self.console.print()

        # Menu
        menu = self._render_menu()
        self.console.print(menu)

    def render_live(self) -> Group:
        """Render settings screen as live-updatable Group.

        Used with Rich Live for real-time updates.

        Returns:
            Rich Group containing all settings panels
        """
        # Fetch latest users
        success = self.fetch_users()

        return Group(
            self._render_header(),
            Text(),  # Blank line
            self._render_user_table(success),
            Text(),  # Blank line
            self._render_instructions(),
            Text(),  # Blank line
            self._render_menu(),
        )

    def _render_header(self) -> Panel:
        """Render settings screen header.

        Returns:
            Rich Panel with title
        """
        header_text = Text("USER MANAGEMENT", justify="center", style="bold cyan")
        return Panel(
            header_text,
            border_style="dim",
            padding=(0, 0),
            expand=True,
        )

    def _render_user_table(self, api_success: bool) -> Panel:
        """Render user list table.

        Args:
            api_success: Whether API fetch was successful

        Returns:
            Rich Panel with user table or error message
        """
        if not api_success:
            error_text = Text("API Error: Unable to fetch users", style="bold red")
            return Panel(
                error_text,
                title="[bold yellow]USERS[/bold yellow]",
                title_align="left",
                border_style="red",
            )

        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("ID", justify="right", style="dim")
        table.add_column("Username", style="bold")
        table.add_column("Email", style="dim")
        table.add_column("Role", justify="center")
        table.add_column("Active", justify="center")
        table.add_column("Created", style="dim")

        for user in self.users:
            # Role styling
            role = str(user["role"])
            if role == "admin":
                role_text = Text(role.upper(), style="bold red")
            elif role == "user":
                role_text = Text(role.upper(), style="bold green")
            else:
                role_text = Text(role.upper(), style="bold yellow")

            # Active status
            active_text = Text("✓", style="green") if user["is_active"] else Text("✗", style="red")

            # Format created_at timestamp
            created = str(user["created_at"])[:10]  # YYYY-MM-DD

            table.add_row(
                str(user["id"]),
                user["username"],
                user["email"],
                role_text,
                active_text,
                created,
            )

        return Panel(
            table,
            title=f"[bold yellow]USERS ({len(self.users)})[/bold yellow]",
            title_align="left",
            border_style="blue",
        )

    def _render_instructions(self) -> Panel:
        """Render instructions panel.

        Returns:
            Rich Panel with keyboard shortcuts
        """
        instructions = Text()
        instructions.append("[A]", style="bold blue")
        instructions.append(" Add User  ")
        instructions.append("[D]", style="bold blue")
        instructions.append(" Delete User  ")
        instructions.append("[R]", style="bold blue")
        instructions.append(" Refresh List")

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
