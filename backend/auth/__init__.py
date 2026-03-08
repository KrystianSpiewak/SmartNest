"""Authentication and authorization utilities.

This package provides password hashing, JWT token management,
and user authentication helpers.
"""

from backend.auth.jwt import create_access_token, decode_access_token
from backend.auth.password import hash_password, verify_password

__all__ = ["create_access_token", "decode_access_token", "hash_password", "verify_password"]
