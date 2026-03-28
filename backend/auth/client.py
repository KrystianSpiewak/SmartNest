"""Client-side authentication helpers for runtime HTTP clients.

Shared utilities used by TUI and device simulation runner when authenticating
against backend auth endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


def login_and_get_access_token(
    http_client: httpx.Client,
    username: str,
    password: str,
    *,
    login_path: str = "/api/auth/login",
) -> str | None:
    """Authenticate and return access token from auth endpoint.

    Args:
        http_client: HTTP client configured for backend API.
        username: Username to authenticate.
        password: Password to authenticate.
        login_path: Auth endpoint path.

    Returns:
        Access token string when present, otherwise None.

    Raises:
        httpx.HTTPError: For network or non-success HTTP responses.
        ValueError: When response JSON cannot be decoded.
    """
    response = http_client.post(
        login_path,
        json={"username": username, "password": password},
    )
    response.raise_for_status()

    payload: Any = response.json()
    token_value = payload.get("access_token") if isinstance(payload, dict) else None
    token = str(token_value).strip() if token_value is not None else ""
    return token or None


def set_bearer_token(http_client: httpx.Client, access_token: str) -> None:
    """Store bearer token in Authorization header."""
    http_client.headers["Authorization"] = f"Bearer {access_token}"
