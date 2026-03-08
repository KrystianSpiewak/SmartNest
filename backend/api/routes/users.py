"""User management API endpoints.

Provides REST API for user CRUD operations, including
registration, listing, and deletion.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_current_user, require_role
from backend.api.models.user import UserCreate, UserResponse
from backend.database.repositories.user import UserRepository

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> list[UserResponse]:
    """
    List all users in the system.

    Requires authentication.

    Returns:
        List of all users (passwords excluded)
    """
    users = await UserRepository.get_all()
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    _admin: Annotated[UserResponse, Depends(require_role("admin"))],
) -> UserResponse:
    """
    Create a new user.

    Args:
        user: User data including username, email, password, role

    Returns:
        Created user (password excluded)

    Raises:
        HTTPException: 400 if username or email already exists
    """
    try:
        created_user = await UserRepository.create(user)
    except Exception as e:
        # Check for unique constraint violation
        error_msg = str(e).lower()
        if "unique" in error_msg or "already exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        ) from e
    else:
        return created_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    _admin: Annotated[UserResponse, Depends(require_role("admin"))],
) -> None:
    """
    Delete a user by ID.

    Args:
        user_id: Unique user identifier

    Raises:
        HTTPException: 404 if user not found
    """
    success = await UserRepository.delete(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
    """
    Get a user by ID.

    Args:
        user_id: Unique user identifier

    Returns:
        User data (password excluded)

    Raises:
        HTTPException: 404 if user not found
    """
    user = await UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    return user
