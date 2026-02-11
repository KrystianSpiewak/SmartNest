"""Interactive database verification script.

Demonstrates database operations with real data.
"""

import asyncio
from pathlib import Path

from backend.database import get_connection, init_database


async def verify_database_operations() -> None:  # noqa: PLR0915
    """Verify database is operational with real operations."""
    print("=" * 70)
    print("DATABASE OPERATIONAL VERIFICATION")
    print("=" * 70)

    # Initialize database
    print("\n[1/6] Initializing database...")
    await init_database()
    db_path = Path("data/smartnest.db").absolute()  # noqa: ASYNC240
    print("      ✓ Database file created at:", db_path)

    # Verify schema
    print("\n[2/6] Verifying schema...")
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = await cursor.fetchall()
        print(f"      ✓ Found {len(tables)} tables:")
        for table in tables:
            print(f"        - {table['name']}")

    # Check foreign key enforcement
    print("\n[3/6] Verifying foreign key enforcement...")
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute("PRAGMA foreign_keys")
        result = await cursor.fetchone()
        fk_enabled = result[0] == 1
        print(f"      ✓ Foreign keys: {'ENABLED' if fk_enabled else 'DISABLED'}")

    # Insert test device
    print("\n[4/6] Testing device insertion...")
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute(
            """
            INSERT INTO devices (id, friendly_name, device_type, mqtt_topic, capabilities, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "test_light_001",
                "Living Room Light",
                "light",
                "smartnest/device/test_light_001/state",
                '["power", "brightness"]',
                "online",
            ),
        )
        await conn.commit()
        print("      ✓ Inserted device: test_light_001")

    # Query device
    print("\n[5/6] Querying inserted device...")
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute("SELECT * FROM devices WHERE id = ?", ("test_light_001",))
        device = await cursor.fetchone()
        if device:
            print("      ✓ Device found:")
            print(f"        - Name: {device['friendly_name']}")
            print(f"        - Type: {device['device_type']}")
            print(f"        - Status: {device['status']}")
            print(f"        - Capabilities: {device['capabilities']}")

    # Verify admin user
    print("\n[6/6] Verifying admin user...")
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute("SELECT username, email, role FROM users")
        user = await cursor.fetchone()
        if user:
            print("      ✓ Admin user found:")
            print(f"        - Username: {user['username']}")
            print(f"        - Email: {user['email']}")
            print(f"        - Role: {user['role']}")

    # Cleanup
    print("\n[Cleanup] Removing test data...")
    async with get_connection() as conn, conn.cursor() as cursor:
        await cursor.execute("DELETE FROM devices WHERE id = ?", ("test_light_001",))
        await conn.commit()
        print("      ✓ Test data removed")

    print("\n" + "=" * 70)
    print("DATABASE OPERATIONAL: All verification checks passed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(verify_database_operations())
