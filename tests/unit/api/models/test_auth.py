"""Unit tests for authentication request and response models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.models.auth import LoginRequest, TokenResponse


class TestLoginRequest:
    """Tests for LoginRequest model."""

    def test_valid_login_request(self) -> None:
        """LoginRequest accepts valid username and password."""
        req = LoginRequest(username="admin", password="secret123")
        assert req.username == "admin"
        assert req.password == "secret123"

    def test_empty_username_rejected(self) -> None:
        """LoginRequest rejects empty username."""
        with pytest.raises(ValidationError):
            LoginRequest(username="", password="secret123")

    def test_empty_password_rejected(self) -> None:
        """LoginRequest rejects empty password."""
        with pytest.raises(ValidationError):
            LoginRequest(username="admin", password="")

    def test_missing_username_rejected(self) -> None:
        """LoginRequest requires username field."""
        with pytest.raises(ValidationError):
            LoginRequest(password="secret123")  # type: ignore[call-arg]

    def test_missing_password_rejected(self) -> None:
        """LoginRequest requires password field."""
        with pytest.raises(ValidationError):
            LoginRequest(username="admin")  # type: ignore[call-arg]


class TestTokenResponse:
    """Tests for TokenResponse model."""

    def test_valid_token_response(self) -> None:
        """TokenResponse accepts access_token and sets default token_type."""
        resp = TokenResponse(access_token="eyJhbGciOi...")
        assert resp.access_token == "eyJhbGciOi..."
        assert resp.token_type == "bearer"

    def test_custom_token_type(self) -> None:
        """TokenResponse accepts custom token_type."""
        resp = TokenResponse(access_token="eyJ...", token_type="custom")
        assert resp.token_type == "custom"

    def test_serialization(self) -> None:
        """TokenResponse serializes to dict with expected keys."""
        resp = TokenResponse(access_token="eyJ...")
        data = resp.model_dump()
        assert data == {"access_token": "eyJ...", "token_type": "bearer"}
