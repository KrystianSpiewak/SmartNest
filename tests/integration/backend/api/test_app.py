"""Integration tests for FastAPI application lifecycle and health endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path

from backend.config import AppSettings


@pytest.fixture
def mock_settings_for_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[AppSettings, Path]:
    """Provide test settings for API tests with temporary database.

    Returns:
        Tuple of (AppSettings, database_path) for use in tests
    """
    settings = AppSettings(
        admin_username="testadmin",
        admin_email="test@example.com",
        admin_password="testpass123",
        bcrypt_rounds=4,  # Faster for testing
        host="127.0.0.1",
        port=8000,
        _env_file=None,  # type: ignore[call-arg]
    )
    # Mock settings before importing app
    monkeypatch.setattr("backend.config.get_settings", lambda: settings)

    # Mock database path to use temp directory
    test_db_path = tmp_path / "test_smartnest.db"
    monkeypatch.setattr("backend.database.connection.DATABASE_PATH", test_db_path)

    # Reset database initialization state to allow re-initialization per test
    monkeypatch.setattr("backend.database.connection._initialized", False)

    return settings, test_db_path


@pytest.fixture
def test_app(mock_settings_for_api: tuple[AppSettings, Path]) -> TestClient:  # noqa: ARG001 - Fixture dependency
    """Provide FastAPI TestClient with mocked settings."""
    from backend.app import app  # noqa: PLC0415 - Import after monkeypatch

    return TestClient(app)


class TestFastAPIApplication:
    """Tests for FastAPI application initialization and configuration."""

    def test_app_starts_successfully(
        self,
        test_app: TestClient,
    ) -> None:
        """Test that FastAPI application starts without errors."""
        # TestClient handles lifespan context automatically
        with test_app:
            assert test_app is not None

    def test_health_endpoint_returns_200(
        self,
        test_app: TestClient,
    ) -> None:
        """Test health check endpoint returns healthy status."""
        with test_app as client:
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

    def test_health_endpoint_content_type(
        self,
        test_app: TestClient,
    ) -> None:
        """Test health endpoint returns JSON content type."""
        with test_app as client:
            response = client.get("/health")

            assert "application/json" in response.headers["content-type"]

    def test_database_initialized_on_startup(
        self,
        test_app: TestClient,
        mock_settings_for_api: tuple[AppSettings, Path],
    ) -> None:
        """Test that database is initialized during application startup."""
        _, db_path = mock_settings_for_api

        with test_app:
            # Database file should exist after lifespan startup
            assert db_path.exists(), f"Database file not found at {db_path}"

    def test_cors_headers_configured(
        self,
        test_app: TestClient,
    ) -> None:
        """Test CORS middleware is properly configured."""
        with test_app as client:
            response = client.get(
                "/health",
                headers={"Origin": "http://localhost:3000"},
            )

            # CORS headers should be present (case-insensitive check)
            headers_lower = {k.lower(): v for k, v in response.headers.items()}
            assert "access-control-allow-origin" in headers_lower

    def test_openapi_docs_accessible(
        self,
        test_app: TestClient,
    ) -> None:
        """Test OpenAPI documentation endpoint is accessible."""
        with test_app as client:
            response = client.get("/docs")

            assert response.status_code == 200

    def test_openapi_schema_metadata(
        self,
        test_app: TestClient,
    ) -> None:
        """Test OpenAPI schema contains correct metadata."""
        with test_app as client:
            response = client.get("/openapi.json")
            data = response.json()

            assert data["info"]["title"] == "SmartNest API"
            assert data["info"]["version"] == "0.1.0"
            assert "description" in data["info"]
