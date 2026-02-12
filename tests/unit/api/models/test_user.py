"""Unit tests for User Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.api.models.user import UserBase, UserCreate, UserResponse


class TestUserBase:
    """Tests for UserBase model."""

    def test_valid_user_base(self) -> None:
        """Test creating a valid UserBase instance."""
        user = UserBase(
            username="johndoe",
            email="john@example.com",
            role="user",
        )

        assert user.username == "johndoe"
        assert user.email == "john@example.com"
        assert user.role == "user"

    def test_user_base_default_role(self) -> None:
        """Test that default role is 'user'."""
        user = UserBase(  # type: ignore[call-arg]
            username="alice",
            email="alice@example.com",
        )

        assert user.role == "user"

    def test_user_base_admin_role(self) -> None:
        """Test creating user with admin role."""
        user = UserBase(
            username="admin",
            email="admin@example.com",
            role="admin",
        )

        assert user.role == "admin"

    def test_user_base_readonly_role(self) -> None:
        """Test creating user with readonly role."""
        user = UserBase(
            username="viewer",
            email="viewer@example.com",
            role="readonly",
        )

        assert user.role == "readonly"

    def test_user_base_invalid_role(self) -> None:
        """Test that invalid role is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserBase(
                username="user",
                email="user@example.com",
                role="superuser",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("role",)
        assert "match pattern" in errors[0]["msg"].lower()

    def test_user_base_invalid_email(self) -> None:
        """Test that invalid email format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserBase(  # type: ignore[call-arg]
                username="user",
                email="not-an-email",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("email",)

    def test_user_base_username_too_short(self) -> None:
        """Test that username < 3 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserBase(  # type: ignore[call-arg]
                username="ab",
                email="user@example.com",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("username",)
        assert "at least 3 characters" in errors[0]["msg"]

    def test_user_base_username_too_long(self) -> None:
        """Test that username > 50 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserBase(  # type: ignore[call-arg]
                username="a" * 51,
                email="user@example.com",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("username",)
        assert "at most 50 characters" in errors[0]["msg"]


class TestUserCreate:
    """Tests for UserCreate model."""

    def test_valid_user_create(self) -> None:
        """Test creating a valid UserCreate instance."""
        user = UserCreate(
            username="newuser",
            email="newuser@example.com",
            password="SecurePass123",
            role="user",
        )

        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.password == "SecurePass123"
        assert user.role == "user"

    def test_user_create_password_with_digit_and_letter(self) -> None:
        """Test that password with digit and letter is accepted."""
        user = UserCreate(  # type: ignore[call-arg]
            username="user",
            email="user@example.com",
            password="Password1",
        )

        assert user.password == "Password1"

    def test_user_create_password_no_digit(self) -> None:
        """Test that password without digit is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # type: ignore[call-arg]
                username="user",
                email="user@example.com",
                password="PasswordOnly",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "at least one digit" in errors[0]["msg"]

    def test_user_create_password_no_letter(self) -> None:
        """Test that password without letter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # type: ignore[call-arg]
                username="user",
                email="user@example.com",
                password="12345678",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "at least one letter" in errors[0]["msg"]

    def test_user_create_password_too_short(self) -> None:
        """Test that password < 8 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # type: ignore[call-arg]
                username="user",
                email="user@example.com",
                password="Pass1",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "at least 8 characters" in errors[0]["msg"]

    def test_user_create_password_too_long(self) -> None:
        """Test that password > 100 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # type: ignore[call-arg]
                username="user",
                email="user@example.com",
                password="A1" + "x" * 99,  # 101 chars
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "at most 100 characters" in errors[0]["msg"]

    def test_user_create_missing_password(self) -> None:
        """Test that missing password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="user",
                email="user@example.com",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)


class TestUserResponse:
    """Tests for UserResponse model."""

    def test_valid_user_response(self) -> None:
        """Test creating a valid UserResponse instance."""
        now = datetime.now(UTC)
        user = UserResponse(
            id=1,
            username="johndoe",
            email="john@example.com",
            role="user",
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=now,
        )

        assert user.id == 1
        assert user.username == "johndoe"
        assert user.is_active is True
        assert user.created_at == now
        assert user.last_login_at == now

    def test_user_response_never_logged_in(self) -> None:
        """Test UserResponse for user who never logged in."""
        now = datetime.now(UTC)
        user = UserResponse(
            id=2,
            username="newuser",
            email="new@example.com",
            role="user",
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )

        assert user.id == 2
        assert user.last_login_at is None

    def test_user_response_from_dict(self) -> None:
        """Test creating UserResponse from dictionary (simulating DB row)."""
        now = datetime.now(UTC)
        user_data = {
            "id": 3,
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin",
            "is_active": False,
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }

        user = UserResponse(**user_data)  # type: ignore[arg-type]

        assert user.id == 3
        assert user.role == "admin"
        assert user.is_active is False

    def test_user_response_missing_required_fields(self) -> None:
        """Test that missing required fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserResponse(
                id=1,
                username="user",
                email="user@example.com",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        missing_fields = {error["loc"][0] for error in errors}
        assert "is_active" in missing_fields
        assert "created_at" in missing_fields
        assert "updated_at" in missing_fields
