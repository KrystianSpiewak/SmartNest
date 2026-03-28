"""Shared API error helpers for route handlers.

Centralizes common HTTPException patterns to keep route logic consistent and
reduce duplicated error-mapping code.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status

_BEARER_HEADERS = {"WWW-Authenticate": "Bearer"}


def raise_unauthorized(detail: str = "Invalid credentials") -> NoReturn:
    """Raise a 401 HTTPException with required bearer auth header."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_BEARER_HEADERS,
    )


def raise_not_found(detail: str) -> NoReturn:
    """Raise a 404 HTTPException."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def raise_conflict(detail: str) -> NoReturn:
    """Raise a 409 HTTPException."""
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def raise_bad_request(detail: str) -> NoReturn:
    """Raise a 400 HTTPException."""
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def raise_internal_server_error(detail: str) -> NoReturn:
    """Raise a 500 HTTPException."""
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def map_create_exception(
    exc: Exception,
    *,
    duplicate_detail: str,
    fallback_detail: str,
) -> NoReturn:
    """Map repository create errors to standardized HTTP responses.

    Args:
        exc: Original exception raised by repository create operation.
        duplicate_detail: Error detail for duplicate/unique violations.
        fallback_detail: Error detail for generic/unexpected create failures.
    """
    error_msg = str(exc).lower()
    if "unique" in error_msg or "already exists" in error_msg:
        raise_bad_request(duplicate_detail)
    raise_internal_server_error(fallback_detail)
