"""Unit tests for database schema DDL."""

from __future__ import annotations

from backend.database.schema import SCHEMA_DDL


class TestSchemaDDL:
    """Tests for SCHEMA_DDL constant."""

    def test_schema_is_string(self) -> None:
        """Test that SCHEMA_DDL is a non-empty string."""
        assert isinstance(SCHEMA_DDL, str)
        assert len(SCHEMA_DDL) > 0

    def test_schema_has_devices_table(self) -> None:
        """Test that schema includes devices table."""
        assert "CREATE TABLE IF NOT EXISTS devices" in SCHEMA_DDL
        assert "id TEXT PRIMARY KEY" in SCHEMA_DDL

    def test_schema_has_sensor_readings_table(self) -> None:
        """Test that schema includes sensor_readings table."""
        assert "CREATE TABLE IF NOT EXISTS sensor_readings" in SCHEMA_DDL

    def test_schema_has_device_state_table(self) -> None:
        """Test that schema includes device_state table."""
        assert "CREATE TABLE IF NOT EXISTS device_state" in SCHEMA_DDL

    def test_schema_has_users_table(self) -> None:
        """Test that schema includes users table."""
        assert "CREATE TABLE IF NOT EXISTS users" in SCHEMA_DDL
        assert "id INTEGER PRIMARY KEY AUTOINCREMENT" in SCHEMA_DDL
        assert "username TEXT NOT NULL UNIQUE" in SCHEMA_DDL
        assert "password_hash TEXT NOT NULL" in SCHEMA_DDL

    def test_schema_has_foreign_keys(self) -> None:
        """Test that schema includes foreign key constraints."""
        assert "FOREIGN KEY" in SCHEMA_DDL
        # sensor_readings references devices
        assert "REFERENCES devices(id)" in SCHEMA_DDL

    def test_schema_has_indexes(self) -> None:
        """Test that schema includes performance indexes."""
        assert "CREATE INDEX" in SCHEMA_DDL
        # Should have device_id indexes for performance
        assert "idx_" in SCHEMA_DDL

    def test_schema_uses_if_not_exists(self) -> None:
        """Test that schema uses IF NOT EXISTS for idempotency."""
        # All CREATE TABLE statements should use IF NOT EXISTS
        create_count = SCHEMA_DDL.count("CREATE TABLE")
        if_not_exists_count = SCHEMA_DDL.count("IF NOT EXISTS")
        # Should have equal or more IF NOT EXISTS (includes CREATE INDEX)
        assert if_not_exists_count >= create_count

    def test_schema_has_timestamps(self) -> None:
        """Test that schema includes timestamp tracking."""
        assert "created_at" in SCHEMA_DDL
        assert "updated_at" in SCHEMA_DDL
        assert "datetime" in SCHEMA_DDL.lower()
