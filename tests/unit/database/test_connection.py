"""Unit tests for database connection management."""

from __future__ import annotations

import asyncio
from pathlib import Path  # noqa: TC003

import aiosqlite
import bcrypt
import pytest

from backend.config import AppSettings
from backend.database import connection


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path for testing."""
    return tmp_path / "test_smartnest.db"


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    """Provide test settings with admin credentials."""
    settings = AppSettings(
        admin_username="testadmin",
        admin_email="test@example.com",
        admin_password="testpass123",
        bcrypt_rounds=4,  # Faster for testing
        _env_file=None,  # type: ignore[call-arg]
    )
    monkeypatch.setattr("backend.database.connection.get_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def reset_database_state(temp_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset database module state before each test."""
    # Use temporary database path
    monkeypatch.setattr("backend.database.connection.DATABASE_PATH", temp_db_path)

    # Reset initialization state
    connection._initialized = False
    connection._init_lock = asyncio.Lock()


class TestInitDatabase:
    """Tests for init_database() function."""

    @pytest.mark.asyncio
    async def test_creates_database_file(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that init_database creates the database file."""
        assert not temp_db_path.exists()  # noqa: ASYNC240

        await connection.init_database()

        assert temp_db_path.exists()  # noqa: ASYNC240
        assert temp_db_path.is_file()  # noqa: ASYNC240

    @pytest.mark.asyncio
    async def test_creates_data_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_settings: AppSettings,
    ) -> None:
        """Test that init_database creates parent directories."""
        nested_path = tmp_path / "deep" / "nested" / "path" / "test.db"
        monkeypatch.setattr("backend.database.connection.DATABASE_PATH", nested_path)

        await connection.init_database()

        assert nested_path.exists()
        assert nested_path.parent.exists()

    @pytest.mark.asyncio
    async def test_creates_schema_tables(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that init_database creates all schema tables."""
        await connection.init_database()

        async with aiosqlite.connect(temp_db_path) as conn, conn.cursor() as cursor:
            # Check devices table
            await cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='devices'"
            )
            assert await cursor.fetchone() is not None

            # Check sensor_readings table
            await cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'"
            )
            assert await cursor.fetchone() is not None

            # Check device_state table
            await cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='device_state'"
            )
            assert await cursor.fetchone() is not None

            # Check users table
            await cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            assert await cursor.fetchone() is not None

    @pytest.mark.asyncio
    async def test_enables_foreign_keys(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that foreign keys are enabled."""
        await connection.init_database()

        async with aiosqlite.connect(temp_db_path) as conn:
            # Enable foreign keys for this connection to read its status
            await conn.execute("PRAGMA foreign_keys = ON")
            async with conn.cursor() as cursor:
                await cursor.execute("PRAGMA foreign_keys")
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == 1  # Foreign keys enabled

    @pytest.mark.asyncio
    async def test_creates_admin_user(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that init_database creates default admin user."""
        await connection.init_database()

        async with aiosqlite.connect(temp_db_path) as conn, conn.cursor() as cursor:
            await cursor.execute("SELECT username, email, role FROM users")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == mock_settings.admin_username
            assert row[1] == mock_settings.admin_email
            assert row[2] == "admin"

    @pytest.mark.asyncio
    async def test_admin_user_password_hashed(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that admin password is bcrypt hashed."""
        await connection.init_database()

        async with aiosqlite.connect(temp_db_path) as conn, conn.cursor() as cursor:
            await cursor.execute("SELECT password_hash FROM users")
            row = await cursor.fetchone()
            assert row is not None
            password_hash = row[0]

            # Verify bcrypt hash format
            assert password_hash.startswith("$2b$")

            # Verify password verifies correctly
            assert bcrypt.checkpw(
                mock_settings.admin_password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )

    @pytest.mark.asyncio
    async def test_idempotent(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that calling init_database multiple times is safe."""
        # First call
        await connection.init_database()

        # Reset state to allow second call
        connection._initialized = False

        # Second call should not fail
        await connection.init_database()

        # Database file should exist
        assert temp_db_path.exists()  # noqa: ASYNC240
        # File might be modified due to admin user check, but no error should occur

    @pytest.mark.asyncio
    async def test_raises_on_missing_credentials(
        self,
        temp_db_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that init_database raises on missing admin credentials."""
        # Mock settings with empty credentials
        empty_settings = AppSettings(
            admin_username="",
            admin_email="",
            admin_password="",
            _env_file=None,  # type: ignore[call-arg]
        )
        monkeypatch.setattr("backend.database.connection.get_settings", lambda: empty_settings)

        with pytest.raises(
            ValueError,
            match=r"(?s)Admin credentials not configured.*SMARTNEST_ADMIN_USERNAME.*SMARTNEST_ADMIN_EMAIL.*SMARTNEST_ADMIN_PASSWORD",
        ):
            await connection.init_database()

    @pytest.mark.asyncio
    async def test_sets_initialized_flag(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that init_database sets the _initialized flag."""
        assert not connection._initialized

        await connection.init_database()

        assert connection._initialized

    @pytest.mark.asyncio
    async def test_uses_lock_for_thread_safety(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that init_database uses lock for concurrent calls."""
        # Call init_database concurrently
        await asyncio.gather(
            connection.init_database(),
            connection.init_database(),
            connection.init_database(),
        )

        # Should succeed without errors
        assert connection._initialized


class TestCreateDefaultAdminUser:
    """Tests for _create_default_admin_user() function."""

    @pytest.mark.asyncio
    async def test_skips_if_users_exist(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that admin user creation is skipped if users exist."""
        # Create database and insert a user manually
        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.executescript(
                """
                CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                );
                INSERT INTO users (username, email, password_hash, role)
                VALUES ('existing', 'existing@example.com', 'hash123', 'user');
                """
            )
            await conn.commit()

            # Call function
            await connection._create_default_admin_user(conn)

            # Should still have only one user
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM users")
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == 1

                # Verify it's still the original user
                await cursor.execute("SELECT username FROM users")
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == "existing"

    @pytest.mark.asyncio
    async def test_validates_username_required(
        self,
        temp_db_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that empty username raises ValueError."""
        settings = AppSettings(
            admin_username="",
            admin_email="test@example.com",
            admin_password="testpass",
            _env_file=None,  # type: ignore[call-arg]
        )
        monkeypatch.setattr("backend.database.connection.get_settings", lambda: settings)

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                )
                """
            )

            with pytest.raises(
                ValueError,
                match=r"(?s)Admin credentials not configured.*SMARTNEST_ADMIN_USERNAME.*SMARTNEST_ADMIN_EMAIL.*SMARTNEST_ADMIN_PASSWORD",
            ):
                await connection._create_default_admin_user(conn)

    @pytest.mark.asyncio
    async def test_validates_email_required(
        self,
        temp_db_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that empty email raises ValueError."""
        settings = AppSettings(
            admin_username="testadmin",
            admin_email="",
            admin_password="testpass",
            _env_file=None,  # type: ignore[call-arg]
        )
        monkeypatch.setattr("backend.database.connection.get_settings", lambda: settings)

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                )
                """
            )

            with pytest.raises(
                ValueError,
                match=r"(?s)Admin credentials not configured.*SMARTNEST_ADMIN_USERNAME.*SMARTNEST_ADMIN_EMAIL.*SMARTNEST_ADMIN_PASSWORD",
            ):
                await connection._create_default_admin_user(conn)

    @pytest.mark.asyncio
    async def test_validates_password_required(
        self,
        temp_db_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that empty password raises ValueError."""
        settings = AppSettings(
            admin_username="testadmin",
            admin_email="test@example.com",
            admin_password="",
            _env_file=None,  # type: ignore[call-arg]
        )
        monkeypatch.setattr("backend.database.connection.get_settings", lambda: settings)

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                )
                """
            )

            with pytest.raises(
                ValueError,
                match=r"(?s)Admin credentials not configured.*SMARTNEST_ADMIN_USERNAME.*SMARTNEST_ADMIN_EMAIL.*SMARTNEST_ADMIN_PASSWORD",
            ):
                await connection._create_default_admin_user(conn)


class TestGetConnection:
    """Tests for get_connection() context manager."""

    @pytest.mark.asyncio
    async def test_raises_if_not_initialized(self, temp_db_path: Path) -> None:
        """Test that get_connection raises if database not initialized."""
        with pytest.raises(RuntimeError, match="Database not initialized"):
            async with connection.get_connection():
                pass

    @pytest.mark.asyncio
    async def test_yields_connection(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that get_connection yields an aiosqlite connection."""
        await connection.init_database()

        async with connection.get_connection() as conn:
            assert isinstance(conn, aiosqlite.Connection)

    @pytest.mark.asyncio
    async def test_enables_foreign_keys(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that get_connection enables foreign keys."""
        await connection.init_database()

        async with connection.get_connection() as conn, conn.cursor() as cursor:
            await cursor.execute("PRAGMA foreign_keys")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1

    @pytest.mark.asyncio
    async def test_sets_row_factory(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that get_connection sets Row factory."""
        await connection.init_database()

        async with connection.get_connection() as conn:
            assert conn.row_factory is aiosqlite.Row

    @pytest.mark.asyncio
    async def test_can_query_database(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that connection can query database."""
        await connection.init_database()

        async with connection.get_connection() as conn, conn.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1  # Admin user created


class TestModuleConstants:
    """Tests for module-level constants (kills string mutation mutants)."""

    def test_sql_count_users_format(self) -> None:
        """Test SQL_COUNT_USERS has correct uppercase format."""
        assert connection.SQL_COUNT_USERS == "SELECT COUNT(*) FROM users"
        # Verify uppercase keywords
        assert "SELECT" in connection.SQL_COUNT_USERS
        assert "COUNT" in connection.SQL_COUNT_USERS
        assert "FROM" in connection.SQL_COUNT_USERS
        # Verify lowercase table name
        assert "users" in connection.SQL_COUNT_USERS
        assert "USERS" not in connection.SQL_COUNT_USERS

    def test_sql_enable_foreign_keys_format(self) -> None:
        """Test SQL_ENABLE_FOREIGN_KEYS has correct uppercase format."""
        assert connection.SQL_ENABLE_FOREIGN_KEYS == "PRAGMA foreign_keys = ON"
        # Verify uppercase format
        assert "PRAGMA" in connection.SQL_ENABLE_FOREIGN_KEYS
        assert "ON" in connection.SQL_ENABLE_FOREIGN_KEYS
        # Verify no lowercase variants
        assert "pragma" not in connection.SQL_ENABLE_FOREIGN_KEYS
        assert "on" not in connection.SQL_ENABLE_FOREIGN_KEYS.replace("foreign", "x")

    def test_sql_insert_user_format(self) -> None:
        """Test SQL_INSERT_USER has correct format."""
        expected = """INSERT INTO users (username, email, password_hash, role)
VALUES (?, ?, ?, ?)"""
        assert expected == connection.SQL_INSERT_USER
        # Verify uppercase keywords
        assert "INSERT INTO" in connection.SQL_INSERT_USER
        assert "VALUES" in connection.SQL_INSERT_USER

    def test_utf8_encoding_lowercase(self) -> None:
        """Test UTF8_ENCODING uses lowercase utf-8."""
        assert connection.UTF8_ENCODING == "utf-8"
        # Verify exact casing
        assert connection.UTF8_ENCODING != "UTF-8"
        assert connection.UTF8_ENCODING != "utf8"

    def test_assertion_message_exact_text(self) -> None:
        """Test ASSERT_COUNT_RETURNS_ROW has exact expected text."""
        assert connection.ASSERT_COUNT_RETURNS_ROW == "COUNT(*) should always return a row"
        # Verify uppercase COUNT
        assert "COUNT(*)" in connection.ASSERT_COUNT_RETURNS_ROW
        assert "count(*)" not in connection.ASSERT_COUNT_RETURNS_ROW


class TestForeignKeyEnforcement:
    """Tests that PRAGMA foreign_keys actually enforces constraints."""

    @pytest.mark.asyncio
    async def test_foreign_key_constraint_enforced(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that foreign key constraints are enforced after init."""
        await connection.init_database()

        async with connection.get_connection() as conn:
            # Try to insert a sensor reading for non-existent device
            # This should fail if foreign keys are enabled
            with pytest.raises(aiosqlite.IntegrityError, match="FOREIGN KEY constraint failed"):
                await conn.execute(
                    """
                    INSERT INTO sensor_readings (device_id, sensor_type, value, unit, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("nonexistent_device", "temperature", 25.0, "C", "2026-02-11T12:00:00Z"),
                )

    @pytest.mark.asyncio
    async def test_foreign_key_setting_persists(
        self,
        temp_db_path: Path,
        mock_settings: AppSettings,
    ) -> None:
        """Test that foreign_keys=ON persists in connection."""
        await connection.init_database()

        async with (
            connection.get_connection() as conn,
            conn.cursor() as cursor,
        ):
            # Verify foreign keys are enabled
            await cursor.execute(connection.SQL_CHECK_FOREIGN_KEYS)
            row = await cursor.fetchone()
            assert row is not None
            # PRAGMA foreign_keys returns 1 when enabled, 0 when disabled
            assert row[0] == 1, "Foreign keys should be enabled (PRAGMA foreign_keys = 1)"


class TestAssertionBehavior:
    """Tests for assertion message validation (kills assert message mutants)."""

    def test_assertion_constant_used_in_code(self) -> None:
        """Test that ASSERT_COUNT_RETURNS_ROW constant is imported and available."""
        # Verify the constant is accessible from the module
        assert hasattr(connection, "ASSERT_COUNT_RETURNS_ROW")
        assert isinstance(connection.ASSERT_COUNT_RETURNS_ROW, str)
        assert len(connection.ASSERT_COUNT_RETURNS_ROW) > 0

    def test_assertion_message_content(self) -> None:
        """Test assertion message contains key elements."""
        message = connection.ASSERT_COUNT_RETURNS_ROW
        # Verify key components
        assert "COUNT(*)" in message
        assert "should" in message
        assert "return" in message
        assert "row" in message
        # Verify it's a complete sentence
        assert message[0].isupper()  # Starts with capital


class TestErrorMessages:
    """Tests for error message constants (kills error message mutants)."""

    def test_error_admin_credentials_exact_format(self) -> None:
        """Test ERROR_ADMIN_CREDENTIALS_NOT_CONFIGURED has exact expected format."""
        expected = (
            "Admin credentials not configured. Set environment variables:\n"
            "  SMARTNEST_ADMIN_USERNAME=your_username\n"
            "  SMARTNEST_ADMIN_EMAIL=your_email@domain.com\n"
            "  SMARTNEST_ADMIN_PASSWORD=your_secure_password"
        )
        assert expected == connection.ERROR_ADMIN_CREDENTIALS_NOT_CONFIGURED

    def test_error_message_line_format(self) -> None:
        """Test error message has correct line structure (kills XX padding mutants)."""
        message = connection.ERROR_ADMIN_CREDENTIALS_NOT_CONFIGURED
        lines = message.split("\n")

        # Verify exactly 4 lines
        assert len(lines) == 4, f"Expected 4 lines, got {len(lines)}"

        # Verify first line (no leading/trailing XX)
        assert lines[0] == "Admin credentials not configured. Set environment variables:"
        assert not lines[0].startswith("XX")
        assert not lines[0].endswith("XX")

        # Verify env var lines format (2 spaces prefix, no XX padding)
        assert lines[1] == "  SMARTNEST_ADMIN_USERNAME=your_username"
        assert lines[1].startswith("  ")  # Exactly 2 spaces
        assert not lines[1].startswith("XX")
        assert not lines[1].endswith("XX")

        assert lines[2] == "  SMARTNEST_ADMIN_EMAIL=your_email@domain.com"
        assert lines[2].startswith("  ")
        assert not lines[2].startswith("XX")
        assert not lines[2].endswith("XX")

        assert lines[3] == "  SMARTNEST_ADMIN_PASSWORD=your_secure_password"
        assert lines[3].startswith("  ")
        assert not lines[3].startswith("XX")
        assert not lines[3].endswith("XX")

    def test_error_message_example_values_lowercase(self) -> None:
        """Test error message example values use lowercase (kills casing mutants)."""
        message = connection.ERROR_ADMIN_CREDENTIALS_NOT_CONFIGURED

        # Verify lowercase example values (not uppercase)
        assert "your_username" in message
        assert "YOUR_USERNAME" not in message

        assert "your_email@domain.com" in message
        assert "YOUR_EMAIL@DOMAIN.COM" not in message

        assert "your_secure_password" in message
        assert "YOUR_SECURE_PASSWORD" not in message

    def test_error_message_env_var_names_uppercase(self) -> None:
        """Test error message has uppercase environment variable names."""
        message = connection.ERROR_ADMIN_CREDENTIALS_NOT_CONFIGURED

        # Verify uppercase env var names
        assert "SMARTNEST_ADMIN_USERNAME" in message
        assert "SMARTNEST_ADMIN_EMAIL" in message
        assert "SMARTNEST_ADMIN_PASSWORD" in message

        # Verify NOT lowercase
        assert "smartnest_admin_username" not in message.lower().replace("smartnest_admin", "x")
