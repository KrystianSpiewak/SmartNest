"""User Pydantic models for authentication and authorization.

Models handle user registration, login, and profile data with
appropriate validation rules for security.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Used at runtime by Pydantic

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user fields shared across request/response schemas."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    role: str = Field("user", pattern="^(admin|user|readonly)$")


class UserCreate(UserBase):
    """Schema for user registration (input validation).

    Includes password with complexity requirements.
    """

    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        """Ensure password meets complexity requirements.

        Requirements:
        - At least 8 characters
        - Contains at least one digit
        - Contains at least one letter

        Args:
            value: Raw password string

        Returns:
            Validated password

        Raises:
            ValueError: If password doesn't meet complexity requirements
        """
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter")
        return value


class UserResponse(UserBase):
    """Schema for user API responses (output serialization).

    Excludes password_hash for security. Includes ID and timestamps.
    """

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    # Configure Pydantic to work with SQLite Row objects
    model_config = ConfigDict(from_attributes=True)
