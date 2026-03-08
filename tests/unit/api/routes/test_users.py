"""Unit tests for user API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from backend.api.models.user import UserCreate, UserResponse
from backend.api.routes.users import create_user, delete_user, get_user, list_users

_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

_ADMIN_USER = UserResponse(
    id=99,
    username="admin",
    email="admin@example.com",
    role="admin",
    is_active=True,
    created_at=_NOW,
    updated_at=_NOW,
    last_login_at=None,
)


class TestListUsers:
    """Tests for list_users() endpoint handler."""

    @pytest.mark.asyncio
    async def test_list_users_returns_all_users(self) -> None:
        """list_users() returns all users from repository."""
        mock_users = [
            UserResponse(
                id=1,
                username="user1",
                email="user1@example.com",
                role="user",
                is_active=True,
                created_at=_NOW,
                updated_at=_NOW,
                last_login_at=None,
            ),
            UserResponse(
                id=2,
                username="user2",
                email="user2@example.com",
                role="admin",
                is_active=True,
                created_at=_NOW,
                updated_at=_NOW,
                last_login_at=None,
            ),
        ]

        with patch(
            "backend.api.routes.users.UserRepository.get_all",
            new_callable=AsyncMock,
            return_value=mock_users,
        ):
            result = await list_users(_current_user=_ADMIN_USER)

        assert result == mock_users
        assert len(result) == 2


class TestCreateUser:
    """Tests for create_user() endpoint handler."""

    @pytest.mark.asyncio
    async def test_create_user_success(self) -> None:
        """create_user() creates user and returns UserResponse."""
        user_create = UserCreate(
            username="newuser",
            email="new@example.com",
            password="password123",
            role="user",
        )
        mock_response = UserResponse(
            id=1,
            username="newuser",
            email="new@example.com",
            role="user",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )

        with patch(
            "backend.api.routes.users.UserRepository.create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await create_user(user_create, _admin=_ADMIN_USER)

        assert result == mock_response

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username_raises_400(self) -> None:
        """create_user() raises 400 HTTPException for duplicate username."""
        user_create = UserCreate(
            username="duplicate",
            email="dup@example.com",
            password="password123",
            role="user",
        )

        with (
            patch(
                "backend.api.routes.users.UserRepository.create",
                new=AsyncMock(side_effect=Exception("UNIQUE constraint failed")),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_user(user_create, _admin=_ADMIN_USER)

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_user_generic_error_raises_500(self) -> None:
        """create_user() raises 500 HTTPException for unexpected errors."""
        user_create = UserCreate(
            username="erroruser",
            email="error@example.com",
            password="password123",
            role="user",
        )

        with (
            patch(
                "backend.api.routes.users.UserRepository.create",
                new=AsyncMock(side_effect=Exception("Database connection failed")),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_user(user_create, _admin=_ADMIN_USER)

        assert exc_info.value.status_code == 500
        assert "Failed to create user" in exc_info.value.detail


class TestGetUser:
    """Tests for get_user() endpoint handler."""

    @pytest.mark.asyncio
    async def test_get_user_success(self) -> None:
        """get_user() returns user data when found."""
        mock_user = UserResponse(
            id=42,
            username="existinguser",
            email="existing@example.com",
            role="user",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )

        with patch(
            "backend.api.routes.users.UserRepository.get_by_id",
            new=AsyncMock(return_value=mock_user),
        ):
            result = await get_user(42, _current_user=_ADMIN_USER)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_not_found_raises_404(self) -> None:
        """get_user() raises 404 HTTPException when user not found."""
        with (
            patch(
                "backend.api.routes.users.UserRepository.get_by_id",
                new=AsyncMock(return_value=None),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_user(99999, _current_user=_ADMIN_USER)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestDeleteUser:
    """Tests for delete_user() endpoint handler."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self) -> None:
        """delete_user() succeeds without raising exception."""
        with patch(
            "backend.api.routes.users.UserRepository.delete",
            new=AsyncMock(return_value=True),
        ):
            await delete_user(42, _admin=_ADMIN_USER)

        # Should complete without exception

    @pytest.mark.asyncio
    async def test_delete_user_not_found_raises_404(self) -> None:
        """delete_user() raises 404 HTTPException when user not found."""
        with (
            patch(
                "backend.api.routes.users.UserRepository.delete",
                new=AsyncMock(return_value=False),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await delete_user(99999, _admin=_ADMIN_USER)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
