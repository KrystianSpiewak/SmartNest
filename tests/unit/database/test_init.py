"""Unit tests for database package imports."""

from __future__ import annotations


class TestDatabasePackageImports:
    """Tests for database package __init__.py imports."""

    def test_imports_get_connection(self) -> None:
        """Test that get_connection is importable from package."""
        from backend.database import get_connection  # noqa: PLC0415

        assert callable(get_connection)

    def test_imports_init_database(self) -> None:
        """Test that init_database is importable from package."""
        from backend.database import init_database  # noqa: PLC0415

        assert callable(init_database)

    def test_imports_schema_ddl(self) -> None:
        """Test that SCHEMA_DDL is importable from package."""
        from backend.database import SCHEMA_DDL  # noqa: PLC0415

        assert isinstance(SCHEMA_DDL, str)

    def test_all_exports(self) -> None:
        """Test that __all__ contains expected exports."""
        from backend.database import __all__  # noqa: PLC0415

        assert "get_connection" in __all__
        assert "init_database" in __all__
        assert "SCHEMA_DDL" in __all__
        assert len(__all__) == 3
