"""
Database repository layer for SmartNest.

This module provides the repository pattern for database access,
abstracting database operations from the business logic.
"""

from __future__ import annotations

from backend.database.repositories.device import DeviceRepository
from backend.database.repositories.user import UserRepository

__all__ = [
    "DeviceRepository",
    "UserRepository",
]
