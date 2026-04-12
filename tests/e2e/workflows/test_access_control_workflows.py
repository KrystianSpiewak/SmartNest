"""Baseline e2e workflow scenarios for access-control behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.testclient import TestClient


def test_authorized_write_success(
    e2e_client: TestClient,
    admin_token: str,
    auth_header: Callable[[str], dict[str, str]],
) -> None:
    """Scenario: admin can create a device on a writer-guarded endpoint."""
    response = e2e_client.post(
        "/api/devices",
        json={
            "id": "e2e-light-001",
            "friendly_name": "E2E Light",
            "device_type": "light",
            "mqtt_topic": "smartnest/device/e2e-light-001/state",
            "manufacturer": "SmartNest",
            "model": "E2E",
            "firmware_version": "1.0.0",
            "capabilities": ["power"],
        },
        headers=auth_header(admin_token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "e2e-light-001"
    assert data["friendly_name"] == "E2E Light"


def test_unauthorized_write_denied_for_readonly_user(
    e2e_client: TestClient,
    admin_token: str,
    auth_header: Callable[[str], dict[str, str]],
    login_user: Callable[[str, str], str],
) -> None:
    """Scenario: readonly user is denied on writer-only endpoint."""
    create_user_response = e2e_client.post(
        "/api/users",
        json={
            "username": "e2e-readonly",
            "email": "readonly@e2e.example.com",
            "password": "readonly-pass1",
            "role": "readonly",
        },
        headers=auth_header(admin_token),
    )
    assert create_user_response.status_code == 201

    readonly_token = login_user("e2e-readonly", "readonly-pass1")
    create_device_response = e2e_client.post(
        "/api/devices",
        json={
            "id": "e2e-light-002",
            "friendly_name": "Readonly Should Fail",
            "device_type": "light",
            "mqtt_topic": "smartnest/device/e2e-light-002/state",
            "manufacturer": "SmartNest",
            "model": "E2E",
            "firmware_version": "1.0.0",
            "capabilities": ["power"],
        },
        headers=auth_header(readonly_token),
    )

    assert create_device_response.status_code == 403


def test_authorized_write_persists_and_can_be_read(
    e2e_client: TestClient,
    admin_token: str,
    auth_header: Callable[[str], dict[str, str]],
) -> None:
    """Scenario: writer operation persists and is retrievable through a read endpoint."""
    device_id = "e2e-light-003"
    create_response = e2e_client.post(
        "/api/devices",
        json={
            "id": device_id,
            "friendly_name": "Persisted E2E Device",
            "device_type": "light",
            "mqtt_topic": f"smartnest/device/{device_id}/state",
            "manufacturer": "SmartNest",
            "model": "E2E-PERSIST",
            "firmware_version": "1.0.0",
            "capabilities": ["power"],
        },
        headers=auth_header(admin_token),
    )
    assert create_response.status_code == 201

    get_response = e2e_client.get(f"/api/devices/{device_id}", headers=auth_header(admin_token))

    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == device_id
    assert body["friendly_name"] == "Persisted E2E Device"


def test_non_admin_user_denied_on_admin_only_user_creation(
    e2e_client: TestClient,
    admin_token: str,
    auth_header: Callable[[str], dict[str, str]],
    login_user: Callable[[str, str], str],
) -> None:
    """Scenario: standard user cannot call admin-only user-management route."""
    create_user_response = e2e_client.post(
        "/api/users",
        json={
            "username": "e2e-standard-user",
            "email": "standard@e2e.example.com",
            "password": "standard-pass1",
            "role": "user",
        },
        headers=auth_header(admin_token),
    )
    assert create_user_response.status_code == 201

    user_token = login_user("e2e-standard-user", "standard-pass1")

    forbidden_response = e2e_client.post(
        "/api/users",
        json={
            "username": "e2e-should-not-create",
            "email": "forbidden@e2e.example.com",
            "password": "forbidden-pass1",
            "role": "user",
        },
        headers=auth_header(user_token),
    )

    assert forbidden_response.status_code == 403
