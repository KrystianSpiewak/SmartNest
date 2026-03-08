"""JWT token creation and verification.

Provides access token generation and decoding using PyJWT with
settings from application configuration (secret, algorithm, expiry).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from backend.config import get_settings


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: Unique user identifier (stored as ``sub`` claim).
        username: Username for the token payload.
        role: User role (admin, user, readonly).

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dictionary with claims.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed or tampered.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
