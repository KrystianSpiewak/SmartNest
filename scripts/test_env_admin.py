"""Test environment-based admin user creation.

Verifies that admin credentials are loaded from environment variables
and properly hashed during database initialization.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt

from backend.config import get_settings
from backend.database import get_connection, init_database


async def test_env_admin_creation() -> None:
    """Verify admin user is created from environment variables."""
    # Delete existing database first
    from pathlib import Path  # noqa: PLC0415 - Import in function for test isolation

    db_path = Path("data/smartnest.db")
    if db_path.exists():  # noqa: ASYNC240 - Sync file ops acceptable in test script
        db_path.unlink()  # noqa: ASYNC240 - Sync file ops acceptable in test script
        print("🗑️  Removed existing database")

    # Initialize database
    print("\n🔧 Initializing database with env-based admin user...")
    await init_database()

    # Verify admin user exists
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute(
            "SELECT username, email, password_hash FROM users WHERE username = ?",
            ("admin",),
        )
        row = await cursor.fetchone()

        if not row:
            print("❌ FAIL: Admin user not found")
            return

        username = row["username"]
        email = row["email"]
        password_hash = row["password_hash"]

        print("\n✅ Admin user found:")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Hash: {password_hash[:30]}...")

        # Verify hash format
        if not password_hash.startswith("$2b$"):
            print("❌ FAIL: Invalid hash format (expected bcrypt)")
            return

        print("✅ Valid bcrypt hash ($2b$ prefix)")

        # Verify password matches
        settings = get_settings()
        if bcrypt.checkpw(settings.admin_password.encode("utf-8"), password_hash.encode("utf-8")):
            print("✅ Password verification successful")
        else:
            print("❌ FAIL: Password verification failed")
            return

        # Verify environment variable loading
        print("\n📋 Environment variables:")
        print(f"   SMARTNEST_ADMIN_USERNAME: {settings.admin_username}")
        print(f"   SMARTNEST_ADMIN_EMAIL: {settings.admin_email}")
        print(f"   SMARTNEST_ADMIN_PASSWORD: {'*' * len(settings.admin_password)}")

    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_env_admin_creation())
