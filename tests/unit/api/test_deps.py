"""Unit tests for authentication dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from backend.api.deps import get_current_user, require_admin_role, require_role, require_writer_role
from backend.api.models.user import UserResponse

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

_VALID_PAYLOAD = {"sub": "1", "username": "alice", "role": "admin", "iat": 0, "exp": 9999999999}

_USER = UserResponse(
    id=1,
    username="alice",
    email="alice@example.com",
    role="admin",
    is_active=True,
    created_at=_NOW,
    updated_at=_NOW,
    last_login_at=None,
)


# ===================================================================
# get_current_user
# ===================================================================


class TestGetCurrentUser:
    """Tests for get_current_user() dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self) -> None:
        """Valid token → decode → fetch user → return UserResponse."""
        with (
            patch("backend.api.deps.decode_access_token", return_value=_VALID_PAYLOAD),
            patch(
                "backend.api.deps.UserRepository.get_by_id",
                new_callable=AsyncMock,
                return_value=_USER,
            ),
        ):
            result = await get_current_user(token="good-token")

        assert result == _USER

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self) -> None:
        """Expired token → 401 with 'Token has expired'."""
        with (
            patch(
                "backend.api.deps.decode_access_token",
                side_effect=pyjwt.ExpiredSignatureError,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(token="expired")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has expired"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self) -> None:
        """Tampered / malformed token → 401 with 'Invalid token'."""
        with (
            patch(
                "backend.api.deps.decode_access_token",
                side_effect=pyjwt.InvalidTokenError,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(token="bad")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    @pytest.mark.asyncio
    async def test_missing_sub_claim_raises_401(self) -> None:
        """Token without 'sub' claim → 401."""
        payload_no_sub = {"username": "alice", "role": "admin"}
        with (
            patch("backend.api.deps.decode_access_token", return_value=payload_no_sub),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(token="no-sub")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self) -> None:
        """Valid token but user deleted from DB → 401."""
        with (
            patch("backend.api.deps.decode_access_token", return_value=_VALID_PAYLOAD),
            patch(
                "backend.api.deps.UserRepository.get_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(token="orphan")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not found"

    @pytest.mark.asyncio
    async def test_inactive_user_raises_401(self) -> None:
        """Valid token but user account deactivated → 401."""
        inactive_user = UserResponse(
            id=1,
            username="alice",
            email="alice@example.com",
            role="admin",
            is_active=False,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )
        with (
            patch("backend.api.deps.decode_access_token", return_value=_VALID_PAYLOAD),
            patch(
                "backend.api.deps.UserRepository.get_by_id",
                new_callable=AsyncMock,
                return_value=inactive_user,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(token="inactive")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User account is inactive"

    @pytest.mark.asyncio
    async def test_empty_sub_claim_raises_401(self) -> None:
        """Token with empty string 'sub' → 401."""
        payload_empty_sub = {"sub": "", "username": "alice", "role": "admin"}
        with (
            patch("backend.api.deps.decode_access_token", return_value=payload_empty_sub),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(token="empty-sub")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"


# ===================================================================
# require_role
# ===================================================================


class TestRequireRole:
    """Tests for require_role() dependency factory."""

    @pytest.mark.asyncio
    async def test_admin_allowed_for_admin_role(self) -> None:
        """Admin user passes require_role('admin')."""
        checker = require_role("admin")
        result = await checker(current_user=_USER)  # type: ignore[call-arg]
        assert result == _USER

    @pytest.mark.asyncio
    async def test_user_rejected_for_admin_only(self) -> None:
        """User role fails require_role('admin') → 403."""
        regular_user = UserResponse(
            id=2,
            username="bob",
            email="bob@example.com",
            role="user",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )
        checker = require_role("admin")
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=regular_user)  # type: ignore[call-arg]

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Insufficient permissions"

    @pytest.mark.asyncio
    async def test_multiple_roles_allow_any_matching(self) -> None:
        """require_role('admin', 'user') accepts either role."""
        regular_user = UserResponse(
            id=2,
            username="bob",
            email="bob@example.com",
            role="user",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )
        checker = require_role("admin", "user")
        result = await checker(current_user=regular_user)  # type: ignore[call-arg]
        assert result == regular_user

    @pytest.mark.asyncio
    async def test_readonly_rejected_for_write_roles(self) -> None:
        """readonly role fails require_role('admin', 'user') → 403."""
        readonly_user = UserResponse(
            id=3,
            username="viewer",
            email="viewer@example.com",
            role="readonly",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )
        checker = require_role("admin", "user")
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=readonly_user)  # type: ignore[call-arg]

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_passes_any_role_check(self) -> None:
        """Admin role passes require_role('admin', 'user', 'readonly')."""
        checker = require_role("admin", "user", "readonly")
        result = await checker(current_user=_USER)  # type: ignore[call-arg]
        assert result == _USER

    @pytest.mark.asyncio
    async def test_role_check_returns_same_user(self) -> None:
        """require_role returns the user object unchanged."""
        checker = require_role("admin")
        result = await checker(current_user=_USER)  # type: ignore[call-arg]
        assert result is _USER


class TestSharedGuardAliases:
    """Tests for reusable role-guard dependency aliases."""

    @pytest.mark.asyncio
    async def test_require_writer_role_allows_user(self) -> None:
        """require_writer_role allows user role (admin,user)."""
        regular_user = UserResponse(
            id=2,
            username="bob",
            email="bob@example.com",
            role="user",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )

        result = await require_writer_role(current_user=regular_user)  # type: ignore[call-arg]
        assert result == regular_user

    @pytest.mark.asyncio
    async def test_require_admin_role_rejects_user(self) -> None:
        """require_admin_role rejects non-admin role."""
        regular_user = UserResponse(
            id=2,
            username="bob",
            email="bob@example.com",
            role="user",
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
            last_login_at=None,
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_admin_role(current_user=regular_user)  # type: ignore[call-arg]

        assert exc_info.value.status_code == 403
