"""Integration tests for user API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.database.connection import get_connection, init_database

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_database() -> None:
    """Initialize and clean database before each test."""
    await init_database()
    async with get_connection() as conn:
        await conn.execute("DELETE FROM users WHERE username != 'admin'")
        await conn.commit()


class TestListUsers:
    """Tests for GET /api/users endpoint."""

    async def test_list_users_returns_admin_by_default(self) -> None:
        """GET /api/users returns at least the admin user."""
        response = client.get("/api/users")

        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        # Admin user should exist from init_database()
        assert len(users) >= 1
        assert any(user["username"] == "admin" for user in users)

    async def test_list_users_includes_new_user(self) -> None:
        """GET /api/users includes newly created users."""
        # Create a test user
        create_response = client.post(
            "/api/users",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123",
                "role": "user",
            },
        )
        assert create_response.status_code == 201

        # List users
        response = client.get("/api/users")

        assert response.status_code == 200
        users = response.json()
        assert any(user["username"] == "testuser" for user in users)


class TestCreateUser:
    """Tests for POST /api/users endpoint."""

    async def test_create_user_success(self) -> None:
        """POST /api/users creates a new user and returns 201."""
        response = client.post(
            "/api/users",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
                "role": "user",
            },
        )

        assert response.status_code == 201
        user = response.json()
        assert user["username"] == "newuser"
        assert user["email"] == "new@example.com"
        assert user["role"] == "user"
        assert "password" not in user
        assert "password_hash" not in user
        assert user["is_active"] is True
        assert "id" in user
        assert "created_at" in user

    async def test_create_user_duplicate_username(self) -> None:
        """POST /api/users returns 400 for duplicate username."""
        # Create first user
        client.post(
            "/api/users",
            json={
                "username": "duplicate",
                "email": "first@example.com",
                "password": "password123",
                "role": "user",
            },
        )

        # Try to create user with same username
        response = client.post(
            "/api/users",
            json={
                "username": "duplicate",
                "email": "second@example.com",
                "password": "password456",
                "role": "user",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    async def test_create_user_invalid_password(self) -> None:
        """POST /api/users returns 422 for weak password."""
        response = client.post(
            "/api/users",
            json={
                "username": "weakpass",
                "email": "weak@example.com",
                "password": "short",  # Too short
                "role": "user",
            },
        )

        assert response.status_code == 422

    async def test_create_user_invalid_role(self) -> None:
        """POST /api/users returns 422 for invalid role."""
        response = client.post(
            "/api/users",
            json={
                "username": "badrole",
                "email": "badrole@example.com",
                "password": "password123",
                "role": "superuser",  # Not a valid role
            },
        )

        assert response.status_code == 422


class TestGetUser:
    """Tests for GET /api/users/{user_id} endpoint."""

    async def test_get_user_success(self) -> None:
        """GET /api/users/{id} returns user data."""
        # Create a user first
        create_response = client.post(
            "/api/users",
            json={
                "username": "getme",
                "email": "getme@example.com",
                "password": "password123",
                "role": "user",
            },
        )
        user_id = create_response.json()["id"]

        # Get the user
        response = client.get(f"/api/users/{user_id}")

        assert response.status_code == 200
        user = response.json()
        assert user["username"] == "getme"
        assert user["id"] == user_id

    async def test_get_user_not_found(self) -> None:
        """GET /api/users/{id} returns 404 for nonexistent user."""
        response = client.get("/api/users/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteUser:
    """Tests for DELETE /api/users/{user_id} endpoint."""

    async def test_delete_user_success(self) -> None:
        """DELETE /api/users/{id} removes user and returns 204."""
        # Create a user first
        create_response = client.post(
            "/api/users",
            json={
                "username": "deleteme",
                "email": "deleteme@example.com",
                "password": "password123",
                "role": "user",
            },
        )
        user_id = create_response.json()["id"]

        # Delete the user
        response = client.delete(f"/api/users/{user_id}")

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/users/{user_id}")
        assert get_response.status_code == 404

    async def test_delete_user_not_found(self) -> None:
        """DELETE /api/users/{id} returns 404 for nonexistent user."""
        response = client.delete("/api/users/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
