"""Database connection management for SmartNest.

This module provides async database connection management using aiosqlite.
The database is initialized with the schema on first connection and provides
connection pooling for concurrent access.

Usage:
    # Initialize database (call once during app startup)
    await init_database()

    # Get connection for queries
    async with get_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM devices")
            rows = await cursor.fetchall()
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
import bcrypt

from backend.config import get_settings
from backend.database.schema import SCHEMA_DDL

# Database configuration
DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "smartnest.db"
_initialized = False
_init_lock = asyncio.Lock()


async def _create_default_admin_user(conn: aiosqlite.Connection) -> None:
    """Create default admin user if no users exist.

    Reads credentials from environment variables (SMARTNEST_ADMIN_*).
    Password is hashed with bcrypt using configured cost factor.

    Args:
        conn: Active database connection

    Raises:
        ValueError: If admin credentials are not configured (empty values)

    Note:
        Only creates user if users table is empty.
        Credentials must be set via environment variables before first run.
    """
    settings = get_settings()

    # Check if any users exist
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row is not None, "COUNT(*) should always return a row"
        user_count = row[0]

        if user_count > 0:
            return  # Users already exist, skip creation

        # Validate admin credentials are configured
        if not settings.admin_username or not settings.admin_email or not settings.admin_password:
            raise ValueError(
                "Admin credentials not configured. Set environment variables:\n"
                "  SMARTNEST_ADMIN_USERNAME=your_username\n"
                "  SMARTNEST_ADMIN_EMAIL=your_email@domain.com\n"
                "  SMARTNEST_ADMIN_PASSWORD=your_secure_password"
            )

        # Hash password with bcrypt
        password_hash = bcrypt.hashpw(
            settings.admin_password.encode("utf-8"),
            bcrypt.gensalt(rounds=settings.bcrypt_rounds),
        )

        # Insert default admin user
        await cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                settings.admin_username,
                settings.admin_email,
                password_hash.decode("utf-8"),
                "admin",
            ),
        )
        await conn.commit()


async def init_database() -> None:
    """Initialize the database with schema.

    Creates the database file and tables if they don't exist.
    This is idempotent - safe to call multiple times.

    Raises:
        aiosqlite.Error: If database initialization fails
    """
    global _initialized  # noqa: PLW0603 - Module-level state for initialization tracking

    async with _init_lock:
        if _initialized:
            return

        # Ensure data directory exists
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Create database and execute schema
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            # Enable foreign keys
            await conn.execute("PRAGMA foreign_keys = ON")

            # Execute schema DDL (CREATE TABLE IF NOT EXISTS)
            await conn.executescript(SCHEMA_DDL)
            await conn.commit()

            # Create default admin user if no users exist
            await _create_default_admin_user(conn)

        _initialized = True


@asynccontextmanager
async def get_connection() -> AsyncGenerator[aiosqlite.Connection]:
    """Get a database connection.

    This is an async context manager that yields an aiosqlite connection.
    The connection is automatically closed when the context exits.

    Yields:
        aiosqlite.Connection: An async database connection

    Raises:
        RuntimeError: If database has not been initialized
        aiosqlite.Error: If connection fails

    Example:
        async with get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM devices")
                rows = await cursor.fetchall()
    """
    if not _initialized:
        raise RuntimeError("Database not initialized. Call init_database() during app startup.")

    async with aiosqlite.connect(DATABASE_PATH) as conn:
        # Enable foreign keys for this connection
        await conn.execute("PRAGMA foreign_keys = ON")

        # Enable row factory for dict-like access
        conn.row_factory = aiosqlite.Row

        yield conn
