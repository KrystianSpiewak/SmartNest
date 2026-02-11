"""Verify backend database setup.

Quick verification script to test database initialization and connection.
Run with: python -m scripts.verify_database
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_connection, init_database


async def main() -> None:
    """Test database initialization and basic queries."""
    print("🔧 Initializing database...")
    await init_database()
    print("✅ Database initialized")

    print("\n🔍 Testing connection...")
    async with get_connection() as conn, conn.cursor() as cursor:
        # Verify tables exist
        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = await cursor.fetchall()
        print(f"✅ Connection successful - Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['name']}")

        # Verify default admin user
        await cursor.execute("SELECT username, role FROM users WHERE username='admin'")
        admin = await cursor.fetchone()
        if admin:
            print(f"\n✅ Default admin user exists: {admin['username']} ({admin['role']})")
        else:
            print("\n⚠️ Warning: Default admin user not found")

    print("\n🎉 Database setup verification complete!")


if __name__ == "__main__":
    asyncio.run(main())
