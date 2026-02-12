"""Password hashing and verification using bcrypt.

Provides secure password handling with configurable cost factor
for performance tuning (lower cost for testing, higher for production).
"""

from __future__ import annotations

import bcrypt

from backend.config import get_settings

# Encoding constant for bcrypt operations
UTF8_ENCODING = "utf-8"


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Uses the cost factor from application settings (default 12 rounds).
    Lower rounds for testing (4), higher for production (12-14).

    Args:
        plain_password: Plain-text password to hash

    Returns:
        Bcrypt hash string (UTF-8 encoded)

    Example:
        >>> hashed = hash_password("securepassword123")
        >>> hashed.startswith("$2b$")
        True
    """
    settings = get_settings()
    password_bytes = plain_password.encode(UTF8_ENCODING)
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode(UTF8_ENCODING)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: Plain-text password to verify
        hashed_password: Bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("mypassword")
        >>> verify_password("mypassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    password_bytes = plain_password.encode(UTF8_ENCODING)
    hashed_bytes = hashed_password.encode(UTF8_ENCODING)
    return bcrypt.checkpw(password_bytes, hashed_bytes)
