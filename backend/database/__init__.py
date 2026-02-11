"""Database package for SmartNest."""

from backend.database.connection import get_connection, init_database
from backend.database.schema import SCHEMA_DDL

__all__ = ["SCHEMA_DDL", "get_connection", "init_database"]
