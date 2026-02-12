"""Authentication and authorization utilities.

This package provides password hashing, JWT token management,
and user authentication helpers.
"""

from backend.auth.password import hash_password, verify_password

__all__ = ["hash_password", "verify_password"]
