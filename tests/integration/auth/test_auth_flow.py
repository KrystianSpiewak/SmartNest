"""Integration tests for authentication flow.

Tests the complete authentication lifecycle: login, token usage,
protected endpoint access, and role-based access control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config import AppSettings

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def mock_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AppSettings:
    """Provide test settings with real JWT secret and admin credentials."""
    settings = AppSettings(
        admin_username="testadmin",
        admin_email="admin@test.com",
        admin_password="adminpass123",
        jwt_secret="test-secret-key-for-integration-tests",
        jwt_expire_minutes=15,
        bcrypt_rounds=4,
        host="127.0.0.1",
        port=8000,
        _env_file=None,  # type: ignore[call-arg]
    )

    def settings_fn() -> AppSettings:
        return settings

    monkeypatch.setattr("backend.config.get_settings", settings_fn)
    monkeypatch.setattr("backend.app.get_settings", settings_fn)
    monkeypatch.setattr("backend.database.connection.get_settings", settings_fn)
    monkeypatch.setattr("backend.auth.jwt.get_settings", settings_fn)
    monkeypatch.setattr("backend.auth.password.get_settings", settings_fn)
    test_db = tmp_path / "auth_test.db"
    monkeypatch.setattr("backend.database.connection.DATABASE_PATH", test_db)
    monkeypatch.setattr("backend.database.connection._initialized", False)
    return settings


@pytest.fixture
def auth_client(mock_settings: AppSettings) -> Generator[TestClient]:  # noqa: ARG001 - Fixture dependency
    """Provide FastAPI TestClient with real auth dependencies."""
    from backend.app import app  # noqa: PLC0415

    with (
        patch("backend.app.SmartNestMQTTClient") as mock_mqtt_class,
        patch("backend.app.MQTTBridge") as mock_bridge_class,
    ):
        mock_mqtt_client = Mock()
        mock_mqtt_class.return_value = mock_mqtt_client

        mock_bridge = Mock()
        mock_bridge.start = AsyncMock(return_value=None)
        mock_bridge.sync_discovered_devices = AsyncMock(return_value=0)
        mock_bridge.stop = AsyncMock(return_value=None)
        mock_bridge_class.return_value = mock_bridge

        # Clear any leftover dependency overrides
        app.dependency_overrides.clear()
        yield TestClient(app)
        app.dependency_overrides.clear()


def _login(client: TestClient, username: str, password: str) -> dict[str, Any]:
    """Helper to login and return the response JSON."""
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    return {"status_code": response.status_code, "json": response.json()}


def _auth_header(token: str) -> dict[str, str]:
    """Build Authorization header from token."""
    return {"Authorization": f"Bearer {token}"}


class TestLoginFlow:
    """Tests for POST /api/auth/login endpoint."""

    def test_admin_login_returns_token(self, auth_client: TestClient) -> None:
        """Admin user can login and receive a JWT token."""
        with auth_client as client:
            result = _login(client, "testadmin", "adminpass123")

        assert result["status_code"] == 200
        assert "access_token" in result["json"]
        assert result["json"]["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, auth_client: TestClient) -> None:
        """Wrong password returns 401 Unauthorized."""
        with auth_client as client:
            result = _login(client, "testadmin", "wrongpassword")

        assert result["status_code"] == 401

    def test_login_nonexistent_user_returns_401(self, auth_client: TestClient) -> None:
        """Non-existent username returns 401 Unauthorized."""
        with auth_client as client:
            result = _login(client, "nobody", "password123")

        assert result["status_code"] == 401


class TestTokenUsage:
    """Tests for using JWT tokens on protected endpoints."""

    def test_get_me_with_valid_token(self, auth_client: TestClient) -> None:
        """GET /api/auth/me returns user info with valid token."""
        with auth_client as client:
            login_result = _login(client, "testadmin", "adminpass123")
            token = login_result["json"]["access_token"]

            response = client.get("/api/auth/me", headers=_auth_header(token))

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"

    def test_get_me_without_token_returns_401(self, auth_client: TestClient) -> None:
        """GET /api/auth/me without token returns 401."""
        with auth_client as client:
            response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self, auth_client: TestClient) -> None:
        """GET /api/auth/me with invalid token returns 401."""
        with auth_client as client:
            response = client.get(
                "/api/auth/me",
                headers=_auth_header("invalid.jwt.token"),
            )

        assert response.status_code == 401

    def test_protected_device_endpoint_with_token(self, auth_client: TestClient) -> None:
        """GET /api/devices with valid token succeeds."""
        with auth_client as client:
            login_result = _login(client, "testadmin", "adminpass123")
            token = login_result["json"]["access_token"]

            response = client.get("/api/devices", headers=_auth_header(token))

        assert response.status_code == 200

    def test_protected_device_endpoint_without_token(self, auth_client: TestClient) -> None:
        """GET /api/devices without token returns 401."""
        with auth_client as client:
            response = client.get("/api/devices")

        assert response.status_code == 401


class TestRoleBasedAccess:
    """Tests for role-based access control on protected endpoints."""

    def test_admin_can_create_user(self, auth_client: TestClient) -> None:
        """Admin role can access POST /api/users."""
        with auth_client as client:
            login_result = _login(client, "testadmin", "adminpass123")
            token = login_result["json"]["access_token"]

            response = client.post(
                "/api/users",
                json={
                    "username": "newuser",
                    "email": "new@test.com",
                    "password": "password123",
                    "role": "user",
                },
                headers=_auth_header(token),
            )

        assert response.status_code == 201

    def test_regular_user_cannot_create_user(self, auth_client: TestClient) -> None:
        """User role cannot access admin-only POST /api/users (403)."""
        with auth_client as client:
            # Login as admin to create a regular user
            admin_result = _login(client, "testadmin", "adminpass123")
            admin_token = admin_result["json"]["access_token"]

            client.post(
                "/api/users",
                json={
                    "username": "regularuser",
                    "email": "regular@test.com",
                    "password": "password123",
                    "role": "user",
                },
                headers=_auth_header(admin_token),
            )

            # Login as the regular user
            user_result = _login(client, "regularuser", "password123")
            user_token = user_result["json"]["access_token"]

            # Try to create another user — should be forbidden
            response = client.post(
                "/api/users",
                json={
                    "username": "anotheruser",
                    "email": "another@test.com",
                    "password": "password123",
                    "role": "user",
                },
                headers=_auth_header(user_token),
            )

        assert response.status_code == 403

    def test_regular_user_can_list_devices(self, auth_client: TestClient) -> None:
        """User role can access GET /api/devices (any authenticated user)."""
        with auth_client as client:
            # Create regular user via admin
            admin_result = _login(client, "testadmin", "adminpass123")
            admin_token = admin_result["json"]["access_token"]

            client.post(
                "/api/users",
                json={
                    "username": "deviceuser",
                    "email": "device@test.com",
                    "password": "password123",
                    "role": "user",
                },
                headers=_auth_header(admin_token),
            )

            # Login as regular user
            user_result = _login(client, "deviceuser", "password123")
            user_token = user_result["json"]["access_token"]

            # Access devices — should succeed
            response = client.get("/api/devices", headers=_auth_header(user_token))

        assert response.status_code == 200
