"""Unit tests for SmartNest application settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import AppSettings, get_settings


class TestAppSettingsDefaults:
    """Tests for default settings values."""

    def test_default_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear environment to test true defaults
        monkeypatch.delenv("SMARTNEST_LOG_LEVEL", raising=False)
        settings = AppSettings(
            _env_file=None  # type: ignore[call-arg]  # Disable .env file loading for test
        )
        assert settings.log_level == "INFO"

    def test_default_log_renderer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_LOG_RENDERER", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_renderer == "console"

    def test_default_mqtt_broker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_MQTT_BROKER", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.mqtt_broker == "localhost"

    def test_default_mqtt_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_MQTT_PORT", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.mqtt_port == 1883

    def test_default_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_DATABASE_URL", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url == "smartnest.db"

    def test_default_jwt_expire_minutes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_JWT_EXPIRE_MINUTES", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.jwt_expire_minutes == 15

    def test_default_server_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_HOST", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.host == "127.0.0.1"


class TestAppSettingsCustom:
    """Tests for custom settings values."""

    def test_custom_mqtt_settings(self) -> None:
        settings = AppSettings(
            mqtt_broker="mqtt.example.com",
            mqtt_port=8883,
            mqtt_username="admin",
            mqtt_password="secret",
        )
        assert settings.mqtt_broker == "mqtt.example.com"
        assert settings.mqtt_port == 8883
        assert settings.mqtt_username == "admin"
        assert settings.mqtt_password == "secret"

    def test_custom_log_settings(self) -> None:
        settings = AppSettings(log_level="DEBUG", log_renderer="json")
        assert settings.log_level == "DEBUG"
        assert settings.log_renderer == "json"


class TestAppSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_log_level(self) -> None:
        with pytest.raises(ValidationError, match="log_level"):
            AppSettings(log_level="TRACE")  # type: ignore[arg-type]

    def test_invalid_log_renderer(self) -> None:
        with pytest.raises(ValidationError, match="log_renderer"):
            AppSettings(log_renderer="yaml")  # type: ignore[arg-type]

    def test_invalid_mqtt_port(self) -> None:
        with pytest.raises(ValidationError, match="mqtt_port"):
            AppSettings(mqtt_port=0)

    def test_invalid_jwt_expire(self) -> None:
        with pytest.raises(ValidationError, match="jwt_expire_minutes"):
            AppSettings(jwt_expire_minutes=0)

    def test_invalid_bcrypt_rounds_low(self) -> None:
        with pytest.raises(ValidationError, match="bcrypt_rounds"):
            AppSettings(bcrypt_rounds=3)

    def test_invalid_bcrypt_rounds_high(self) -> None:
        with pytest.raises(ValidationError, match="bcrypt_rounds"):
            AppSettings(bcrypt_rounds=32)


class TestAppSettingsFromEnv:
    """Tests for environment variable loading."""

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMARTNEST_LOG_LEVEL", "WARNING")
        monkeypatch.setenv("SMARTNEST_MQTT_BROKER", "env-broker")
        settings = AppSettings()
        assert settings.log_level == "WARNING"
        assert settings.mqtt_broker == "env-broker"

    def test_env_prefix_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Variables without SMARTNEST_ prefix are ignored."""
        monkeypatch.setenv("LOG_LEVEL", "ERROR")
        monkeypatch.delenv("SMARTNEST_LOG_LEVEL", raising=False)
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]  # Disable .env file
        assert settings.log_level == "INFO"  # default, not "ERROR"


class TestGetSettings:
    """Tests for the get_settings() cached singleton."""

    def test_returns_app_settings(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, AppSettings)

    def test_cached_singleton(self) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()
