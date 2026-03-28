"""FastAPI authentication dependencies.

Provides dependency injection functions for JWT-based authentication
and role-based access control on protected endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.api.models.user import UserResponse
from backend.auth.jwt import decode_access_token
from backend.database.repositories.user import UserRepository
from backend.logging import get_logger
from backend.logging.catalog import MessageCode, format_message

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserResponse:
    """Decode JWT token and return the authenticated user.

    Args:
        token: Bearer token extracted by OAuth2PasswordBearer.

    Returns:
        Authenticated user from the database.

    Raises:
        HTTPException: 401 if token is invalid, expired, or user not found/inactive.
    """
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        logger.warning(
            "auth_token_expired",
            code=MessageCode.AUTH_TOKEN_EXPIRED.value,
            message=format_message(MessageCode.AUTH_TOKEN_EXPIRED),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        logger.warning(
            "auth_token_invalid",
            code=MessageCode.AUTH_TOKEN_INVALID.value,
            message=format_message(MessageCode.AUTH_TOKEN_INVALID),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await UserRepository.get_by_id(int(user_id_str))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(
    *roles: str,
) -> Callable[[UserResponse], Coroutine[Any, Any, UserResponse]]:
    """Create a dependency that enforces role-based access control.

    Args:
        *roles: Allowed role names (e.g. ``"admin"``, ``"user"``).

    Returns:
        FastAPI dependency function that validates the user's role.
    """

    async def _check_role(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
    ) -> UserResponse:
        if current_user.role not in roles:
            logger.warning(
                "auth_insufficient_role",
                code=MessageCode.AUTH_INSUFFICIENT_ROLE.value,
                message=format_message(
                    MessageCode.AUTH_INSUFFICIENT_ROLE,
                    username=current_user.username,
                    role=current_user.role,
                    required=", ".join(roles),
                ),
                username=current_user.username,
                user_role=current_user.role,
                required_roles=list(roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check_role


# Shared guard dependencies to avoid repeating role tuples across routes.
require_writer_role = require_role("admin", "user")
require_admin_role = require_role("admin")
