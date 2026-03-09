"""Unit tests for JWT token creation and verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest

from backend.auth.jwt import create_access_token, decode_access_token
from backend.config import AppSettings


@pytest.fixture
def jwt_settings() -> AppSettings:
    """Settings with a known secret for deterministic tests."""
    return AppSettings(
        jwt_secret="test-secret-key-for-unit-tests!!",
        jwt_algorithm="HS256",
        jwt_expire_minutes=15,
        _env_file=None,  # type: ignore[call-arg]
    )


class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_returns_string(self, jwt_settings: AppSettings) -> None:
        """create_access_token() returns an encoded JWT string."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_sub_claim(self, jwt_settings: AppSettings) -> None:
        """Token payload contains sub claim with user_id as string."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=42, username="testuser", role="user")
            payload = decode_access_token(token)

        assert payload["sub"] == "42"

    def test_token_contains_username_claim(self, jwt_settings: AppSettings) -> None:
        """Token payload contains username claim."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")
            payload = decode_access_token(token)

        assert payload["username"] == "admin"

    def test_token_contains_role_claim(self, jwt_settings: AppSettings) -> None:
        """Token payload contains role claim."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")
            payload = decode_access_token(token)

        assert payload["role"] == "admin"

    def test_token_contains_iat_claim(self, jwt_settings: AppSettings) -> None:
        """Token payload contains iat (issued at) claim."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")
            payload = decode_access_token(token)

        assert "iat" in payload
        assert isinstance(payload["iat"], int)

    def test_token_contains_exp_claim(self, jwt_settings: AppSettings) -> None:
        """Token payload contains exp (expiration) claim."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")
            payload = decode_access_token(token)

        assert "exp" in payload
        assert isinstance(payload["exp"], int)

    def test_exp_is_after_iat(self, jwt_settings: AppSettings) -> None:
        """Expiration time is after issued-at time."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")
            payload = decode_access_token(token)

        assert payload["exp"] > payload["iat"]

    def test_exp_matches_configured_minutes(self, jwt_settings: AppSettings) -> None:
        """Expiration is approximately jwt_expire_minutes after iat."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")
            payload = decode_access_token(token)

        diff = payload["exp"] - payload["iat"]
        expected = jwt_settings.jwt_expire_minutes * 60
        # Allow 2 seconds of drift for test execution time
        assert abs(diff - expected) <= 2

    def test_different_users_produce_different_tokens(self, jwt_settings: AppSettings) -> None:
        """Different user_ids produce different tokens."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token1 = create_access_token(user_id=1, username="user1", role="user")
            token2 = create_access_token(user_id=2, username="user2", role="admin")

        assert token1 != token2

    def test_uses_configured_algorithm(self, jwt_settings: AppSettings) -> None:
        """Token is signed with the configured algorithm."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")

        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    def test_algorithm_kwarg_is_forwarded(self) -> None:
        """Removing algorithm= kwarg changes the header when non-default algo used."""
        settings = AppSettings(
            jwt_secret="test-secret-key-for-unit-tests-hs384-needs-48-bytes!!",
            jwt_algorithm="HS384",
            jwt_expire_minutes=15,
            _env_file=None,  # type: ignore[call-arg]
        )
        with patch("backend.auth.jwt.get_settings", return_value=settings):
            token = create_access_token(user_id=1, username="admin", role="admin")

        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "HS384"


class TestDecodeAccessToken:
    """Tests for decode_access_token()."""

    def test_round_trip(self, jwt_settings: AppSettings) -> None:
        """Token created by create_access_token decodes correctly."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=5, username="roundtrip", role="readonly")
            payload = decode_access_token(token)

        assert payload["sub"] == "5"
        assert payload["username"] == "roundtrip"
        assert payload["role"] == "readonly"

    def test_expired_token_raises(self, jwt_settings: AppSettings) -> None:
        """decode_access_token raises ExpiredSignatureError for expired tokens."""
        expired_payload = {
            "sub": "1",
            "username": "admin",
            "role": "admin",
            "iat": datetime.now(UTC) - timedelta(hours=1),
            "exp": datetime.now(UTC) - timedelta(minutes=30),
        }
        token = pyjwt.encode(
            expired_payload,
            jwt_settings.jwt_secret,
            algorithm=jwt_settings.jwt_algorithm,
        )

        with (
            patch("backend.auth.jwt.get_settings", return_value=jwt_settings),
            pytest.raises(pyjwt.ExpiredSignatureError),
        ):
            decode_access_token(token)

    def test_tampered_token_raises(self, jwt_settings: AppSettings) -> None:
        """decode_access_token raises InvalidTokenError for tampered tokens."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")

        tampered = token[:-5] + "XXXXX"

        with (
            patch("backend.auth.jwt.get_settings", return_value=jwt_settings),
            pytest.raises(pyjwt.InvalidTokenError),
        ):
            decode_access_token(tampered)

    def test_wrong_secret_raises(self, jwt_settings: AppSettings) -> None:
        """decode_access_token raises InvalidSignatureError for wrong secret."""
        with patch("backend.auth.jwt.get_settings", return_value=jwt_settings):
            token = create_access_token(user_id=1, username="admin", role="admin")

        wrong_settings = AppSettings(
            jwt_secret="wrong-secret-but-still-32-bytes!",
            jwt_algorithm="HS256",
            jwt_expire_minutes=15,
            _env_file=None,  # type: ignore[call-arg]
        )

        with (
            patch("backend.auth.jwt.get_settings", return_value=wrong_settings),
            pytest.raises(pyjwt.InvalidSignatureError),
        ):
            decode_access_token(token)

    def test_completely_invalid_token_raises(self, jwt_settings: AppSettings) -> None:
        """decode_access_token raises DecodeError for non-JWT strings."""
        with (
            patch("backend.auth.jwt.get_settings", return_value=jwt_settings),
            pytest.raises(pyjwt.DecodeError),
        ):
            decode_access_token("not-a-jwt-token")

    def test_empty_token_raises(self, jwt_settings: AppSettings) -> None:
        """decode_access_token raises DecodeError for empty string."""
        with (
            patch("backend.auth.jwt.get_settings", return_value=jwt_settings),
            pytest.raises(pyjwt.DecodeError),
        ):
            decode_access_token("")
