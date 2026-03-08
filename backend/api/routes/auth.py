"""Authentication API endpoints.

Provides login and current-user retrieval using JWT tokens.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_current_user
from backend.api.models.auth import LoginRequest, TokenResponse
from backend.api.models.user import UserResponse
from backend.auth.jwt import create_access_token
from backend.database.repositories.user import UserRepository
from backend.logging import get_logger
from backend.logging.catalog import MessageCode, format_message

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate a user and return a JWT access token.

    Args:
        request: Login credentials (username + password).

    Returns:
        JWT access token with bearer type.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    user = await UserRepository.authenticate(request.username, request.password)
    if not user:
        logger.warning(
            "auth_login_failed",
            code=MessageCode.AUTH_LOGIN_FAILED.value,
            message=format_message(MessageCode.AUTH_LOGIN_FAILED, username=request.username),
            username=request.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id, user.username, user.role)
    logger.info(
        "auth_login_success",
        code=MessageCode.AUTH_LOGIN_SUCCESS.value,
        message=format_message(MessageCode.AUTH_LOGIN_SUCCESS, username=user.username),
        username=user.username,
        user_id=user.id,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=None)
async def get_me(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
    """Return the currently authenticated user's profile.

    Args:
        current_user: Injected by get_current_user dependency.

    Returns:
        Current user profile.
    """
    return current_user
