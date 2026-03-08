"""Unit tests for authentication API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from backend.api.models.auth import LoginRequest, TokenResponse
from backend.api.models.user import UserResponse
from backend.api.routes.auth import get_me, login

_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

_MOCK_USER = UserResponse(
    id=1,
    username="alice",
    email="alice@example.com",
    role="admin",
    is_active=True,
    created_at=_NOW,
    updated_at=_NOW,
    last_login_at=_NOW,
)


class TestLogin:
    """Tests for POST /api/auth/login endpoint handler."""

    @pytest.mark.asyncio
    async def test_login_success_returns_token(self) -> None:
        """Successful login returns TokenResponse with access_token."""
        request = LoginRequest(username="alice", password="Password1")
        with (
            patch(
                "backend.api.routes.auth.UserRepository.authenticate",
                new_callable=AsyncMock,
                return_value=_MOCK_USER,
            ),
            patch(
                "backend.api.routes.auth.create_access_token",
                return_value="jwt-token-abc",
            ),
        ):
            result = await login(request)

        assert isinstance(result, TokenResponse)
        assert result.access_token == "jwt-token-abc"
        assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password_raises_401(self) -> None:
        """Wrong password → 401 with 'Invalid credentials'."""
        request = LoginRequest(username="alice", password="wrong")
        with (
            patch(
                "backend.api.routes.auth.UserRepository.authenticate",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await login(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_raises_401(self) -> None:
        """Nonexistent username → 401."""
        request = LoginRequest(username="unknown", password="Password1")
        with (
            patch(
                "backend.api.routes.auth.UserRepository.authenticate",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await login(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_success_calls_create_access_token(self) -> None:
        """Login calls create_access_token with correct user fields."""
        request = LoginRequest(username="alice", password="Password1")
        mock_create = patch(
            "backend.api.routes.auth.create_access_token",
            return_value="token",
        )
        with (
            patch(
                "backend.api.routes.auth.UserRepository.authenticate",
                new_callable=AsyncMock,
                return_value=_MOCK_USER,
            ),
            mock_create as mock_fn,
        ):
            await login(request)

        mock_fn.assert_called_once_with(_MOCK_USER.id, _MOCK_USER.username, _MOCK_USER.role)

    @pytest.mark.asyncio
    async def test_login_401_includes_www_authenticate_header(self) -> None:
        """401 response includes WWW-Authenticate: Bearer header."""
        request = LoginRequest(username="alice", password="wrong")
        with (
            patch(
                "backend.api.routes.auth.UserRepository.authenticate",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await login(request)

        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


class TestGetMe:
    """Tests for GET /api/auth/me endpoint handler."""

    @pytest.mark.asyncio
    async def test_get_me_returns_current_user(self) -> None:
        """get_me() returns the injected current user."""
        result = await get_me(current_user=_MOCK_USER)
        assert result == _MOCK_USER

    @pytest.mark.asyncio
    async def test_get_me_returns_same_instance(self) -> None:
        """get_me() returns the exact same UserResponse object."""
        result = await get_me(current_user=_MOCK_USER)
        assert result is _MOCK_USER
