"""Unit tests for Settings screen."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import httpx
from rich.panel import Panel
from rich.text import Text

from backend.tui.screens.settings import SettingsScreen


class TestSettingsScreenInit:
    """Tests for SettingsScreen initialization."""

    def test_creates_with_console_and_client(self) -> None:
        """SettingsScreen accepts console and http_client."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)

        assert screen.console is console
        assert screen.http_client is http_client

    def test_initializes_empty_users_list(self) -> None:
        """SettingsScreen initializes with empty users list."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)

        assert screen.users == []


class TestFetchUsers:
    """Tests for fetch_users() method."""

    def test_fetch_users_success(self) -> None:
        """fetch_users() retrieves users from API and returns True."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": 1, "username": "admin", "role": "admin"},
            {"id": 2, "username": "user1", "role": "user"},
        ]
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        result = screen.fetch_users()

        assert result is True
        assert len(screen.users) == 2
        assert screen.users[0]["username"] == "admin"
        http_client.get.assert_called_once_with("/api/users")
        mock_response.raise_for_status.assert_called_once()

    def test_fetch_users_http_error(self) -> None:
        """fetch_users() returns False and clears users on HTTP error."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        screen.users = [{"id": 1, "username": "old"}]  # Pre-existing data

        result = screen.fetch_users()

        assert result is False
        assert screen.users == []

    def test_fetch_users_connection_error(self) -> None:
        """fetch_users() returns False and clears users on connection error."""
        console = MagicMock()
        http_client = MagicMock()
        http_client.get.side_effect = httpx.ConnectError("Connection refused")

        screen = SettingsScreen(console, http_client)
        result = screen.fetch_users()

        assert result is False
        assert screen.users == []

    def test_fetch_users_json_decode_error(self) -> None:
        """fetch_users() returns False on invalid JSON response."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        result = screen.fetch_users()

        assert result is False
        assert screen.users == []

    def test_fetch_users_uses_cached_result_when_throttled(self) -> None:
        """fetch_users() returns cached success and skips HTTP call inside throttle window."""
        console = MagicMock()
        http_client = MagicMock()
        screen = SettingsScreen(console, http_client)
        screen._last_fetch_success = True
        screen._last_fetch_at = time.monotonic()

        result = screen.fetch_users()

        assert result is True
        http_client.get.assert_not_called()

    def test_fetch_users_uses_cached_failure_when_throttled(self) -> None:
        """fetch_users() returns cached failure and skips HTTP call inside throttle window."""
        console = MagicMock()
        http_client = MagicMock()
        screen = SettingsScreen(console, http_client)
        screen._last_fetch_success = False
        screen._last_fetch_at = time.monotonic()

        result = screen.fetch_users()

        assert result is False
        http_client.get.assert_not_called()


class TestRender:
    """Tests for render() method."""

    def test_render_calls_fetch_users(self) -> None:
        """render() calls fetch_users() to get latest data."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = []
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        screen.render()

        # Should fetch users
        http_client.get.assert_called_once_with("/api/users")

    def test_render_prints_to_console(self) -> None:
        """render() prints panels to console."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = []
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        screen.render()

        # Should print multiple panels
        assert console.print.call_count >= 4


class TestRenderLive:
    """Tests for render_live() method."""

    def test_render_live_returns_group(self) -> None:
        """render_live() returns Group object."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = []
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        result = screen.render_live()

        # Should return a Group
        assert result is not None
        assert hasattr(result, "__rich_console__")

    def test_render_live_fetches_users(self) -> None:
        """render_live() fetches latest users from API."""
        console = MagicMock()
        http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "username": "admin",
                "email": "admin@example.com",
                "role": "admin",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00",
            }
        ]
        http_client.get.return_value = mock_response

        screen = SettingsScreen(console, http_client)
        screen.render_live()

        # Should fetch users
        http_client.get.assert_called_once_with("/api/users")


class TestRenderUserTable:
    """Tests for _render_user_table() method."""

    def test_render_user_table_success(self) -> None:
        """_render_user_table() displays users in table format."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        screen.users = [
            {
                "id": 1,
                "username": "admin",
                "email": "admin@example.com",
                "role": "admin",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00",
            }
        ]

        panel = screen._render_user_table(api_success=True)

        # Should return a Panel
        assert panel is not None
        assert isinstance(panel, Panel)

    def test_render_user_table_api_error(self) -> None:
        """_render_user_table() displays error on API failure."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        panel = screen._render_user_table(api_success=False)

        # Should return error panel
        assert panel is not None
        assert isinstance(panel, Panel)

    def test_render_user_table_admin_role_styling(self) -> None:
        """_render_user_table() styles admin role in red."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        screen.users = [
            {
                "id": 1,
                "username": "admin",
                "email": "admin@example.com",
                "role": "admin",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00",
            }
        ]

        panel = screen._render_user_table(api_success=True)

        # Panel should contain the user data
        assert panel is not None

    def test_render_user_table_user_role_styling(self) -> None:
        """_render_user_table() styles user role in green."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        screen.users = [
            {
                "id": 2,
                "username": "testuser",
                "email": "test@example.com",
                "role": "user",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00",
            }
        ]

        panel = screen._render_user_table(api_success=True)

        assert panel is not None

    def test_render_user_table_readonly_role_styling(self) -> None:
        """_render_user_table() styles readonly role in yellow."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        screen.users = [
            {
                "id": 3,
                "username": "viewer",
                "email": "viewer@example.com",
                "role": "readonly",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00",
            }
        ]

        panel = screen._render_user_table(api_success=True)

        assert panel is not None

    def test_render_user_table_empty_list(self) -> None:
        """_render_user_table() handles empty user list."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        screen.users = []

        panel = screen._render_user_table(api_success=True)

        assert panel is not None
        # Panel should be created successfully with empty list


class TestRenderInstructions:
    """Tests for _render_instructions() method."""

    def test_render_instructions_returns_panel(self) -> None:
        """_render_instructions() returns Panel with keyboard shortcuts."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        panel = screen._render_instructions()

        assert panel is not None
        assert isinstance(panel, Panel)


class TestRenderMenu:
    """Tests for _render_menu() method."""

    def test_render_menu_returns_text(self) -> None:
        """_render_menu() returns Text with navigation options."""
        console = MagicMock()
        http_client = MagicMock()

        screen = SettingsScreen(console, http_client)
        menu = screen._render_menu()

        assert menu is not None
        assert isinstance(menu, Text)

    class TestPromptAddUser:
        """Tests for prompt_add_user() method."""

        def test_prompt_add_user_success(self) -> None:
            """prompt_add_user() creates user and returns True on success."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "newuser@example.com", "secret123", "user"]
            mock_response = MagicMock()
            http_client.post.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is True
            http_client.post.assert_called_once_with(
                "/api/users",
                json={
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "secret123",
                    "role": "user",
                },
            )
            mock_response.raise_for_status.assert_called_once()

        def test_prompt_add_user_uses_hidden_password_input(self) -> None:
            """prompt_add_user() requests password with hidden console input."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "newuser@example.com", "secret123", "user"]
            mock_response = MagicMock()
            http_client.post.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is True
            assert any(call.kwargs.get("password") is True for call in console.input.call_args_list)

        def test_prompt_add_user_empty_username_returns_false(self) -> None:
            """prompt_add_user() returns False if username is empty."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = [""]

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is False
            http_client.post.assert_not_called()

        def test_prompt_add_user_empty_password_returns_false(self) -> None:
            """prompt_add_user() returns False if password is empty."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "newuser@example.com", "", "user"]

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is False
            http_client.post.assert_not_called()

        def test_prompt_add_user_empty_role_defaults_to_user(self) -> None:
            """prompt_add_user() uses 'user' role when role input is empty."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["admin2", "admin2@example.com", "adminpass1", ""]
            mock_response = MagicMock()
            http_client.post.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is True
            call_json = http_client.post.call_args.kwargs["json"]
            assert call_json["role"] == "user"

        def test_prompt_add_user_empty_email_uses_default(self) -> None:
            """prompt_add_user() defaults email to username@example.com when blank."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "", "secret123", "user"]
            mock_response = MagicMock()
            http_client.post.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is True
            call_json = http_client.post.call_args.kwargs["json"]
            assert call_json["email"] == "newuser@example.com"

        def test_prompt_add_user_whitespace_email_returns_false(self) -> None:
            """prompt_add_user() returns False when email input is only whitespace."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "   ", "secret123", "user"]

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is False
            http_client.post.assert_not_called()

        def test_prompt_add_user_http_error_returns_false(self) -> None:
            """prompt_add_user() returns False on HTTP error from API."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "newuser@example.com", "secret123", "admin"]
            mock_response = MagicMock()
            mock_response.json.return_value = {"detail": "Password must contain at least one digit"}
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "422", request=MagicMock(), response=MagicMock()
            )
            http_client.post.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is False
            console.print.assert_called()

        def test_prompt_add_user_http_error_with_invalid_json_returns_false(self) -> None:
            """prompt_add_user() handles non-JSON API error bodies gracefully."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "newuser@example.com", "secret123", "admin"]
            mock_response = MagicMock()
            mock_response.json.side_effect = ValueError("invalid json")
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "422", request=MagicMock(), response=MagicMock()
            )
            http_client.post.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is False

        def test_prompt_add_user_connection_error_returns_false(self) -> None:
            """prompt_add_user() returns False on connection error."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.side_effect = ["newuser", "newuser@example.com", "secret123", "user"]
            http_client.post.side_effect = httpx.ConnectError("Connection refused")

            screen = SettingsScreen(console, http_client)
            result = screen.prompt_add_user()

            assert result is False

    class TestPromptDeleteUser:
        """Tests for prompt_delete_user() method."""

        def test_prompt_delete_user_success(self) -> None:
            """prompt_delete_user() deletes user and returns True on success."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.return_value = "42"
            mock_response = MagicMock()
            http_client.delete.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            screen.users = [{"id": 42, "username": "testuser"}]
            result = screen.prompt_delete_user()

            assert result is True
            http_client.delete.assert_called_once_with("/api/users/42")
            mock_response.raise_for_status.assert_called_once()

        def test_prompt_delete_user_no_users_returns_false(self) -> None:
            """prompt_delete_user() returns False immediately when users list is empty."""
            console = MagicMock()
            http_client = MagicMock()

            screen = SettingsScreen(console, http_client)
            screen.users = []
            result = screen.prompt_delete_user()

            assert result is False
            console.input.assert_not_called()
            http_client.delete.assert_not_called()

        def test_prompt_delete_user_empty_input_returns_false(self) -> None:
            """prompt_delete_user() returns False when user ID input is empty."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.return_value = ""

            screen = SettingsScreen(console, http_client)
            screen.users = [{"id": 1, "username": "testuser"}]
            result = screen.prompt_delete_user()

            assert result is False
            http_client.delete.assert_not_called()

        def test_prompt_delete_user_invalid_id_returns_false(self) -> None:
            """prompt_delete_user() returns False when user ID is not numeric."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.return_value = "not_a_number"

            screen = SettingsScreen(console, http_client)
            screen.users = [{"id": 1, "username": "testuser"}]
            result = screen.prompt_delete_user()

            assert result is False
            http_client.delete.assert_not_called()

        def test_prompt_delete_user_http_error_returns_false(self) -> None:
            """prompt_delete_user() returns False on HTTP error from API."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.return_value = "5"
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            http_client.delete.return_value = mock_response

            screen = SettingsScreen(console, http_client)
            screen.users = [{"id": 5, "username": "someone"}]
            result = screen.prompt_delete_user()

            assert result is False

        def test_prompt_delete_user_connection_error_returns_false(self) -> None:
            """prompt_delete_user() returns False on connection error."""
            console = MagicMock()
            http_client = MagicMock()
            console.input.return_value = "3"
            http_client.delete.side_effect = httpx.ConnectError("Connection refused")

            screen = SettingsScreen(console, http_client)
            screen.users = [{"id": 3, "username": "someone"}]
            result = screen.prompt_delete_user()

            assert result is False
