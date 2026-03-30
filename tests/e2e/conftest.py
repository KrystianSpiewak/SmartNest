"""Shared fixtures for SmartNest end-to-end tests.

These fixtures provide a reproducible app environment with test settings,
isolated database state, and auth helpers for cross-domain scenarios.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config import AppSettings

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path


@pytest.fixture
def e2e_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AppSettings:
    """Provide deterministic app settings and isolated DB for e2e scenarios."""
    settings = AppSettings(
        admin_username="e2e-admin",
        admin_email="admin@e2e.example.com",
        admin_password="e2e-admin-pass",
        jwt_secret="e2e-jwt-secret-for-tests-1234567890",
        jwt_expire_minutes=15,
        bcrypt_rounds=4,
        host="127.0.0.1",
        port=8000,
        _env_file=None,  # type: ignore[call-arg]
    )

    def settings_fn() -> AppSettings:
        return settings

    # Patch every module that binds get_settings at import-time.
    monkeypatch.setattr("backend.config.get_settings", settings_fn)
    monkeypatch.setattr("backend.app.get_settings", settings_fn)
    monkeypatch.setattr("backend.database.connection.get_settings", settings_fn)
    monkeypatch.setattr("backend.auth.jwt.get_settings", settings_fn)
    monkeypatch.setattr("backend.auth.password.get_settings", settings_fn)

    test_db = tmp_path / "e2e_test.db"
    monkeypatch.setattr("backend.database.connection.DATABASE_PATH", test_db)
    monkeypatch.setattr("backend.database.connection._initialized", False)
    return settings


@pytest.fixture
def e2e_client(
    e2e_settings: AppSettings,  # noqa: ARG001 - ensures fixture side effects
) -> Generator[TestClient]:
    """Create a TestClient with MQTT dependencies mocked for stable e2e runs."""
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

        app.dependency_overrides.clear()
        with TestClient(app) as client:
            yield client
        app.dependency_overrides.clear()


@pytest.fixture
def auth_header() -> Callable[[str], dict[str, str]]:
    """Return a small helper for building Bearer auth headers."""

    def _auth_header(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _auth_header


@pytest.fixture
def login_user(e2e_client: TestClient) -> Callable[[str, str], str]:
    """Return a helper to authenticate any existing user and get a token."""

    def _login_user(username: str, password: str) -> str:
        response = e2e_client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert isinstance(token, str)
        return token

    return _login_user


@pytest.fixture
def admin_token(login_user: Callable[[str, str], str]) -> str:
    """Authenticate with seeded admin credentials and return JWT token."""
    return login_user("e2e-admin", "e2e-admin-pass")
