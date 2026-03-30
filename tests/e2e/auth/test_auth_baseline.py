"""Baseline e2e authentication scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.testclient import TestClient


def test_login_and_authenticated_read(
    e2e_client: TestClient,
    admin_token: str,
    auth_header: Callable[[str], dict[str, str]],
) -> None:
    """Scenario: login succeeds and token grants authenticated read access."""
    response = e2e_client.get("/api/auth/me", headers=auth_header(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "e2e-admin"
    assert body["role"] == "admin"


def test_anonymous_access_denied(e2e_client: TestClient) -> None:
    """Scenario: anonymous access to protected route is denied."""
    response = e2e_client.get("/api/devices")

    assert response.status_code == 401
