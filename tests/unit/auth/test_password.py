"""Unit tests for password hashing and verification."""

from __future__ import annotations

import pytest

from backend.auth.password import hash_password, verify_password


class TestPasswordHashing:
    """Tests for hash_password function."""

    def test_hash_password_returns_bcrypt_hash(self) -> None:
        """Test that hash_password returns a valid bcrypt hash."""
        password = "securepassword123"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$ or $2a$
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert len(hashed) == 60  # Standard bcrypt hash length

    def test_hash_password_different_hashes_for_same_password(self) -> None:
        """Test that same password produces different hashes (due to salt)."""
        password = "testpassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts produce different hashes

    def test_hash_password_handles_special_characters(self) -> None:
        """Test hashing password with special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)

        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_handles_unicode(self) -> None:
        """Test hashing password with Unicode characters."""
        password = "пароль123"  # noqa: RUF001 - Intentional non-Latin chars for Unicode test
        hashed = hash_password(password)

        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_empty_string(self) -> None:
        """Test hashing empty password (should work but be rejected by validation)."""
        password = ""
        hashed = hash_password(password)

        # Bcrypt allows empty password, but Pydantic validation should prevent this
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


class TestPasswordVerification:
    """Tests for verify_password function."""

    def test_verify_password_correct_password(self) -> None:
        """Test that correct password is verified successfully."""
        password = "mypassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self) -> None:
        """Test that incorrect password fails verification."""
        password = "correctpassword"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_case_sensitive(self) -> None:
        """Test that password verification is case-sensitive."""
        password = "Password123"
        hashed = hash_password(password)

        assert verify_password("password123", hashed) is False
        assert verify_password("PASSWORD123", hashed) is False
        assert verify_password("Password123", hashed) is True

    def test_verify_password_with_special_characters(self) -> None:
        """Test verification with special characters."""
        password = "P@ss!W0rd#2024"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("P@ss!W0rd#2023", hashed) is False

    def test_verify_password_with_unicode(self) -> None:
        """Test verification with Unicode characters."""
        password = "пароль456"  # noqa: RUF001 - Intentional non-Latin chars for Unicode test
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("пароль457", hashed) is False  # noqa: RUF001

    def test_verify_password_empty_password(self) -> None:
        """Test verification with empty password."""
        password = ""
        hashed = hash_password(password)

        assert verify_password("", hashed) is True
        assert verify_password("nonempty", hashed) is False


class TestPasswordRoundTrip:
    """Integration tests for hash + verify workflow."""

    @pytest.mark.parametrize(
        "password",
        [
            "SimplePass1",
            "Complex!P@ssw0rd#123",
            "very_long_password_with_many_characters_1234567890",
            "12345678",  # Only digits with minimum length
            "AbCdEfGh",  # Only letters with minimum length
            "П@роль123",  # noqa: RUF001 - Intentional non-Latin chars for Unicode test
        ],
    )
    def test_hash_verify_roundtrip(self, password: str) -> None:
        """Test that hash and verify work correctly for various passwords."""
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_multiple_password_hashes_verify_independently(self) -> None:
        """Test that different passwords don't cross-verify."""
        password1 = "FirstPassword1"
        password2 = "SecondPassword2"

        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        # Correct verifications
        assert verify_password(password1, hash1) is True
        assert verify_password(password2, hash2) is True

        # Cross-verifications should fail
        assert verify_password(password1, hash2) is False
        assert verify_password(password2, hash1) is False
