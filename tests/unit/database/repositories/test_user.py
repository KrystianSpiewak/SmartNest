"""Unit tests for UserRepository."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.models.user import UserCreate, UserResponse
from backend.database.repositories.user import UserRepository

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def sample_user_create() -> UserCreate:
    """Sample UserCreate for testing."""
    return UserCreate(
        username="testuser",
        email="test@example.com",
        password="SecurePass123",
        role="user",
    )


@pytest.fixture
def sample_user_row() -> tuple[object, ...]:
    """Sample database row for user (without password_hash)."""
    now = datetime.now()
    return (
        1,  # id
        "testuser",  # username
        "test@example.com",  # email
        "user",  # role
        1,  # is_active
        now.isoformat(),  # created_at
        now.isoformat(),  # updated_at
        now.isoformat(),  # last_login_at
    )


@pytest.fixture
def sample_user_row_with_hash() -> tuple[object, ...]:
    """Sample database row including password_hash (for authenticate)."""
    now = datetime.now()
    return (
        1,  # id
        "testuser",  # username
        "test@example.com",  # email
        "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYFj.N4k/1K",  # password_hash
        "user",  # role
        1,  # is_active
        now.isoformat(),  # created_at
        now.isoformat(),  # updated_at
        None,  # last_login_at
    )


@pytest.fixture
def mock_connection() -> Mock:
    """Mock database connection."""
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.commit = AsyncMock()
    cursor = MagicMock()
    cursor.fetchone = AsyncMock()
    cursor.fetchall = AsyncMock()
    cursor.rowcount = 1
    cursor.lastrowid = 1
    conn.execute.return_value = cursor
    return conn


class TestUserRepositoryCreate:
    """Tests for UserRepository.create()."""

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, sample_user_create: UserCreate, mock_connection: Mock
    ) -> None:
        """Test creating a user successfully."""
        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.hash_password", return_value="hashed_pw"),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.create(sample_user_create)

            # Verify execute was called with correct SQL
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args
            assert "INSERT INTO users" in call_args[0][0]
            assert call_args[0][1][0] == "testuser"
            assert call_args[0][1][1] == "test@example.com"
            assert call_args[0][1][2] == "hashed_pw"

            # Verify commit was called
            mock_connection.commit.assert_called_once()

            # Verify returned UserResponse
            assert isinstance(result, UserResponse)
            assert result.id == 1
            assert result.username == "testuser"
            assert result.is_active is True
            assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_user_admin_role(self, mock_connection: Mock) -> None:
        """Test creating user with admin role."""
        admin_user = UserCreate(
            username="admin",
            email="admin@example.com",
            password="AdminPass123",
            role="admin",
        )

        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.hash_password", return_value="hashed"),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.create(admin_user)

            assert result.role == "admin"


class TestUserRepositoryGetById:
    """Tests for UserRepository.get_by_id()."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self, sample_user_row: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test getting user by ID when it exists."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = sample_user_row

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_by_id(1)

            # Verify query was correct
            mock_connection.execute.assert_called_once()
            assert "SELECT" in mock_connection.execute.call_args[0][0]
            assert "WHERE id = ?" in mock_connection.execute.call_args[0][0]

            # Verify result
            assert result is not None
            assert result.id == 1
            assert result.username == "testuser"
            assert result.is_active is True

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_connection: Mock) -> None:
        """Test getting user by ID when it doesn't exist."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = None

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_by_id(999)

            assert result is None


class TestUserRepositoryGetByUsername:
    """Tests for UserRepository.get_by_username()."""

    @pytest.mark.asyncio
    async def test_get_by_username_found(
        self, sample_user_row: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test getting user by username when it exists."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = sample_user_row

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_by_username("testuser")

            call_args = mock_connection.execute.call_args
            assert "WHERE username = ?" in call_args[0][0]
            assert result is not None
            assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, mock_connection: Mock) -> None:
        """Test getting user by username when it doesn't exist."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = None

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_by_username("nonexistent")

            assert result is None


class TestUserRepositoryGetByEmail:
    """Tests for UserRepository.get_by_email()."""

    @pytest.mark.asyncio
    async def test_get_by_email_found(
        self, sample_user_row: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test getting user by email when it exists."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = sample_user_row

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_by_email("test@example.com")

            call_args = mock_connection.execute.call_args
            assert "WHERE email = ?" in call_args[0][0]
            assert result is not None
            assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self, mock_connection: Mock) -> None:
        """Test getting user by email when it doesn't exist."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = None

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_by_email("nonexistent@example.com")

            assert result is None


class TestUserRepositoryGetAll:
    """Tests for UserRepository.get_all()."""

    @pytest.mark.asyncio
    async def test_get_all_with_results(
        self, sample_user_row: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test getting all users with results."""
        cursor = mock_connection.execute.return_value
        cursor.fetchall.return_value = [sample_user_row, sample_user_row]

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_all()

            # Verify query includes pagination
            call_args = mock_connection.execute.call_args
            assert "LIMIT ? OFFSET ?" in call_args[0][0]
            assert call_args[0][1] == (100, 0)

            assert len(result) == 2
            assert all(isinstance(u, UserResponse) for u in result)

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, mock_connection: Mock) -> None:
        """Test getting users with custom pagination."""
        cursor = mock_connection.execute.return_value
        cursor.fetchall.return_value = []

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            await UserRepository.get_all(skip=20, limit=10)

            call_args = mock_connection.execute.call_args
            assert call_args[0][1] == (10, 20)

    @pytest.mark.asyncio
    async def test_get_all_empty(self, mock_connection: Mock) -> None:
        """Test getting all users when database is empty."""
        cursor = mock_connection.execute.return_value
        cursor.fetchall.return_value = []

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.get_all()

            assert result == []


class TestUserRepositoryUpdate:
    """Tests for UserRepository.update()."""

    @pytest.mark.asyncio
    async def test_update_user_success(
        self,
        sample_user_create: UserCreate,
        sample_user_row: tuple[object, ...],
        mock_connection: Mock,
    ) -> None:
        """Test updating a user successfully."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1
        cursor.fetchone.return_value = sample_user_row

        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.hash_password", return_value="new_hash"),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.update(1, sample_user_create)

            # Verify UPDATE was called
            assert mock_connection.execute.call_count == 2  # UPDATE + SELECT
            update_call = mock_connection.execute.call_args_list[0]
            assert "UPDATE users" in update_call[0][0]

            assert result is not None
            assert result.id == 1

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self, sample_user_create: UserCreate, mock_connection: Mock
    ) -> None:
        """Test updating non-existent user."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.hash_password", return_value="hash"),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.update(999, sample_user_create)

            assert result is None


class TestUserRepositoryDelete:
    """Tests for UserRepository.delete()."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_connection: Mock) -> None:
        """Test deleting a user successfully."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.delete(1)

            call_args = mock_connection.execute.call_args
            assert "DELETE FROM users" in call_args[0][0]
            assert call_args[0][1] == (1,)

            assert result is True

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_connection: Mock) -> None:
        """Test deleting non-existent user."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.delete(999)

            assert result is False


class TestUserRepositoryCount:
    """Tests for UserRepository.count()."""

    @pytest.mark.asyncio
    async def test_count_users(self, mock_connection: Mock) -> None:
        """Test counting users."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = (15,)

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.count()

            call_args = mock_connection.execute.call_args
            assert "SELECT COUNT(*)" in call_args[0][0]
            assert result == 15

    @pytest.mark.asyncio
    async def test_count_zero(self, mock_connection: Mock) -> None:
        """Test counting when no users."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = (0,)

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.count()

            assert result == 0


class TestUserRepositoryAuthenticate:
    """Tests for UserRepository.authenticate()."""

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, sample_user_row_with_hash: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test successful authentication."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = sample_user_row_with_hash

        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.verify_password", return_value=True),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.authenticate("testuser", "correct_password")

            # Verify password was checked
            assert mock_connection.execute.call_count == 2  # SELECT + UPDATE last_login

            assert result is not None
            assert result.username == "testuser"
            assert result.last_login_at is not None

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(
        self, sample_user_row_with_hash: tuple[object, ...], mock_connection: Mock
    ) -> None:
        """Test authentication with wrong password."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = sample_user_row_with_hash

        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.verify_password", return_value=False),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.authenticate("testuser", "wrong_password")

            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_connection: Mock) -> None:
        """Test authentication when user doesn't exist."""
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = None

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.authenticate("nonexistent", "password")

            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, mock_connection: Mock) -> None:
        """Test authentication with inactive user."""
        now = datetime.now()
        inactive_row = (
            1,
            "testuser",
            "test@example.com",
            "hashed_password",
            "user",
            0,  # is_active = False
            now.isoformat(),
            now.isoformat(),
            None,
        )
        cursor = mock_connection.execute.return_value
        cursor.fetchone.return_value = inactive_row

        with (
            patch("backend.database.repositories.user.get_connection") as mock_get_conn,
            patch("backend.database.repositories.user.verify_password", return_value=True),
        ):
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.authenticate("testuser", "password")

            assert result is None


class TestUserRepositoryDeactivate:
    """Tests for UserRepository.deactivate()."""

    @pytest.mark.asyncio
    async def test_deactivate_user_success(self, mock_connection: Mock) -> None:
        """Test deactivating a user."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.deactivate(1)

            call_args = mock_connection.execute.call_args
            assert "UPDATE users" in call_args[0][0]
            assert "SET is_active = ?" in call_args[0][0]
            assert call_args[0][1][0] is False

            assert result is True

    @pytest.mark.asyncio
    async def test_deactivate_user_not_found(self, mock_connection: Mock) -> None:
        """Test deactivating non-existent user."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.deactivate(999)

            assert result is False


class TestUserRepositoryActivate:
    """Tests for UserRepository.activate()."""

    @pytest.mark.asyncio
    async def test_activate_user_success(self, mock_connection: Mock) -> None:
        """Test activating a user."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 1

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.activate(1)

            call_args = mock_connection.execute.call_args
            assert "UPDATE users" in call_args[0][0]
            assert call_args[0][1][0] is True

            assert result is True

    @pytest.mark.asyncio
    async def test_activate_user_not_found(self, mock_connection: Mock) -> None:
        """Test activating non-existent user."""
        cursor = mock_connection.execute.return_value
        cursor.rowcount = 0

        with patch("backend.database.repositories.user.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            result = await UserRepository.activate(999)

            assert result is False


class TestUserRepositoryRowConversion:
    """Tests for UserRepository._row_to_response()."""

    def test_row_to_response_complete(self, sample_user_row: tuple[object, ...]) -> None:
        """Test converting complete database row to response."""
        result = UserRepository._row_to_response(sample_user_row)  # type: ignore[arg-type]

        assert isinstance(result, UserResponse)
        assert result.id == 1
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.is_active is True
        assert isinstance(result.created_at, datetime)
        assert result.last_login_at is not None

    def test_row_to_response_null_last_login(self) -> None:
        """Test converting row with null last_login_at."""
        now = datetime.now()
        row = (
            1,
            "newuser",
            "new@example.com",
            "user",
            1,
            now.isoformat(),
            now.isoformat(),
            None,  # last_login_at is null
        )

        result = UserRepository._row_to_response(row)  # type: ignore[arg-type]

        assert result.last_login_at is None

    def test_row_to_response_inactive_user(self) -> None:
        """Test converting row for inactive user."""
        now = datetime.now()
        row = (
            1,
            "inactive",
            "inactive@example.com",
            "user",
            0,  # is_active = False
            now.isoformat(),
            now.isoformat(),
            None,
        )

        result = UserRepository._row_to_response(row)  # type: ignore[arg-type]

        assert result.is_active is False
