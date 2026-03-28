"""Unit tests for client-side auth helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.auth.client import login_and_get_access_token, set_bearer_token


class TestLoginAndGetAccessToken:
    """Tests for login_and_get_access_token()."""

    def test_returns_token_on_success(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"access_token": "abc-123"}
        client.post.return_value = response

        token = login_and_get_access_token(client, "user", "pass")

        assert token == "abc-123"

    def test_strips_whitespace_from_token(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"access_token": "  abc-123  "}
        client.post.return_value = response

        token = login_and_get_access_token(client, "user", "pass")

        assert token == "abc-123"

    def test_returns_none_when_token_missing(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {}
        client.post.return_value = response

        token = login_and_get_access_token(client, "user", "pass")

        assert token is None

    def test_returns_none_when_payload_is_not_dict(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = ["not", "a", "dict"]
        client.post.return_value = response

        token = login_and_get_access_token(client, "user", "pass")

        assert token is None

    def test_uses_custom_login_path(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"access_token": "abc-123"}
        client.post.return_value = response

        token = login_and_get_access_token(client, "user", "pass", login_path="/custom/login")

        assert token == "abc-123"
        client.post.assert_called_once_with(
            "/custom/login",
            json={"username": "user", "password": "pass"},
        )


class TestSetBearerToken:
    """Tests for set_bearer_token()."""

    def test_sets_authorization_header(self) -> None:
        client = MagicMock()
        client.headers = {}

        set_bearer_token(client, "token-xyz")

        assert client.headers["Authorization"] == "Bearer token-xyz"

    @pytest.mark.parametrize("existing", [{"X-Test": "1"}, {"Authorization": "old"}])
    def test_preserves_other_headers_when_setting_bearer(self, existing: dict[str, str]) -> None:
        client = MagicMock()
        client.headers = existing.copy()

        set_bearer_token(client, "token-xyz")

        assert client.headers["Authorization"] == "Bearer token-xyz"
        if "X-Test" in existing:
            assert client.headers["X-Test"] == "1"
