"""
User repository for database operations.

Provides CRUD operations and authentication for users in the SmartNest system.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.api.models.user import UserCreate, UserResponse
from backend.auth.password import hash_password, verify_password
from backend.database.connection import get_connection

if TYPE_CHECKING:
    import aiosqlite


class UserRepository:
    """Repository for user database operations."""

    @staticmethod
    async def create(user: UserCreate) -> UserResponse:
        """
        Create a new user in the database.

        Args:
            user: User data to create

        Returns:
            Created user with timestamps (password_hash excluded)

        Raises:
            aiosqlite.IntegrityError: If username or email already exists
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        password_hash = hash_password(user.password)

        cursor = await conn.execute(
            """
        INSERT INTO users (
            username, email, password_hash, role, is_active,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user.username,
                user.email,
                password_hash,
                user.role,
                True,  # Default active
                now.isoformat(),
                now.isoformat(),
            ),
        )
        await conn.commit()
        user_id = cursor.lastrowid

        return UserResponse(
            id=user_id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )

    @staticmethod
    async def get_by_id(user_id: int) -> UserResponse | None:
        """
        Get a user by their ID.

        Args:
            user_id: Unique user identifier

        Returns:
            User if found, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
        SELECT id, username, email, role, is_active,
               created_at, updated_at, last_login_at
        FROM users
        WHERE id = ?
        """,
            (user_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return UserRepository._row_to_response(row)

    @staticmethod
    async def get_by_username(username: str) -> UserResponse | None:
        """
        Get a user by their username.

        Args:
            username: Username to search for

        Returns:
            User if found, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
        SELECT id, username, email, role, is_active,
               created_at, updated_at, last_login_at
        FROM users
        WHERE username = ?
        """,
            (username,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return UserRepository._row_to_response(row)

    @staticmethod
    async def get_by_email(email: str) -> UserResponse | None:
        """
        Get a user by their email address.

        Args:
            email: Email to search for

        Returns:
            User if found, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
        SELECT id, username, email, role, is_active,
               created_at, updated_at, last_login_at
        FROM users
        WHERE email = ?
        """,
            (email,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return UserRepository._row_to_response(row)

    @staticmethod
    async def get_all(skip: int = 0, limit: int = 100) -> list[UserResponse]:
        """
        Get all users with pagination.

        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)

        Returns:
            List of users
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
        SELECT id, username, email, role, is_active,
               created_at, updated_at, last_login_at
        FROM users
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
            (limit, skip),
        )
        rows = await cursor.fetchall()

        return [UserRepository._row_to_response(row) for row in rows]

    @staticmethod
    async def update(user_id: int, user: UserCreate) -> UserResponse | None:
        """
        Update an existing user.

        Args:
            user_id: ID of user to update
            user: New user data (including new password if changed)

        Returns:
            Updated user if found, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        password_hash = hash_password(user.password)

        cursor = await conn.execute(
            """
        UPDATE users
        SET username = ?, email = ?, password_hash = ?,
            role = ?, updated_at = ?
        WHERE id = ?
        """,
            (user.username, user.email, password_hash, user.role, now.isoformat(), user_id),
        )
        await conn.commit()

        if cursor.rowcount == 0:
            return None

        return await UserRepository.get_by_id(user_id)

    @staticmethod
    async def delete(user_id: int) -> bool:
        """
        Delete a user by ID.

        Args:
            user_id: ID of user to delete

        Returns:
            True if deleted, False if not found
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await conn.commit()

        return cursor.rowcount > 0  # type: ignore[no-any-return]

    @staticmethod
    async def count() -> int:
        """
        Get total count of users.

        Returns:
            Number of users in database
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    async def authenticate(username: str, password: str) -> UserResponse | None:
        """
        Authenticate a user by username and password.

        Args:
            username: Username to authenticate
            password: Plain text password to verify

        Returns:
            User if authentication successful, None otherwise
        """
        conn = await get_connection()  # type: ignore[misc]
        cursor = await conn.execute(
            """
        SELECT id, username, email, password_hash, role, is_active,
               created_at, updated_at, last_login_at
        FROM users
        WHERE username = ?
        """,
            (username,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        # Check if password matches
        password_hash = row[3]
        if not verify_password(password, password_hash):
            return None

        # Check if user is active
        is_active = bool(row[5])
        if not is_active:
            return None

        # Update last_login_at
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently
        await conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (now.isoformat(), row[0]),
        )
        await conn.commit()

        return UserResponse(
            id=row[0],
            username=row[1],
            email=row[2],
            role=row[4],
            is_active=is_active,
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7]),
            last_login_at=now,
        )

    @staticmethod
    async def deactivate(user_id: int) -> bool:
        """
        Deactivate a user account (soft delete).

        Args:
            user_id: ID of user to deactivate

        Returns:
            True if deactivated, False if not found
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently

        cursor = await conn.execute(
            """
        UPDATE users
        SET is_active = ?, updated_at = ?
        WHERE id = ?
        """,
            (False, now.isoformat(), user_id),
        )
        await conn.commit()

        return cursor.rowcount > 0  # type: ignore[no-any-return]

    @staticmethod
    async def activate(user_id: int) -> bool:
        """
        Activate a user account.

        Args:
            user_id: ID of user to activate

        Returns:
            True if activated, False if not found
        """
        conn = await get_connection()  # type: ignore[misc]
        now = datetime.now()  # noqa: DTZ005 - Naive datetime used consistently

        cursor = await conn.execute(
            """
        UPDATE users
        SET is_active = ?, updated_at = ?
        WHERE id = ?
        """,
            (True, now.isoformat(), user_id),
        )
        await conn.commit()

        return cursor.rowcount > 0  # type: ignore[no-any-return]

    @staticmethod
    def _row_to_response(row: aiosqlite.Row) -> UserResponse:
        """
        Convert database row to UserResponse model.

        Args:
            row: Database row from users table

        Returns:
            UserResponse model instance
        """
        created_at = datetime.fromisoformat(row[5])
        updated_at = datetime.fromisoformat(row[6])
        last_login_at = datetime.fromisoformat(row[7]) if row[7] else None

        return UserResponse(
            id=row[0],
            username=row[1],
            email=row[2],
            role=row[3],
            is_active=bool(row[4]),
            created_at=created_at,
            updated_at=updated_at,
            last_login_at=last_login_at,
        )
