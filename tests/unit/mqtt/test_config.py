"""Unit tests for SmartNest MQTT configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import AppSettings
from backend.mqtt.config import MQTTConfig, get_mqtt_config


class TestMQTTConfigDefaults:
    """Tests for default configuration values."""

    def test_default_broker(self) -> None:
        cfg = MQTTConfig()
        assert cfg.broker == "localhost"

    def test_default_port(self) -> None:
        cfg = MQTTConfig()
        assert cfg.port == 1883

    def test_default_client_id(self) -> None:
        cfg = MQTTConfig()
        assert cfg.client_id == "smartnest_main"

    def test_default_no_credentials(self) -> None:
        cfg = MQTTConfig()
        assert cfg.username is None
        assert cfg.password is None

    def test_default_keepalive(self) -> None:
        cfg = MQTTConfig()
        assert cfg.keepalive == 60

    def test_default_tls_disabled(self) -> None:
        cfg = MQTTConfig()
        assert cfg.tls_enabled is False

    def test_default_reconnect_min_delay(self) -> None:
        cfg = MQTTConfig()
        assert cfg.reconnect_min_delay == 1

    def test_default_reconnect_max_delay(self) -> None:
        cfg = MQTTConfig()
        assert cfg.reconnect_max_delay == 60


class TestMQTTConfigCustom:
    """Tests for custom configuration values."""

    def test_custom_broker_and_port(self) -> None:
        cfg = MQTTConfig(broker="mqtt.example.com", port=8883)
        assert cfg.broker == "mqtt.example.com"
        assert cfg.port == 8883

    def test_custom_credentials(self) -> None:
        cfg = MQTTConfig(username="admin", password="secret")
        assert cfg.username == "admin"
        assert cfg.password == "secret"

    def test_custom_keepalive(self) -> None:
        cfg = MQTTConfig(keepalive=120)
        assert cfg.keepalive == 120

    def test_custom_reconnect_delays(self) -> None:
        cfg = MQTTConfig(reconnect_min_delay=2, reconnect_max_delay=120)
        assert cfg.reconnect_min_delay == 2
        assert cfg.reconnect_max_delay == 120

    def test_tls_enabled(self) -> None:
        cfg = MQTTConfig(tls_enabled=True)
        assert cfg.tls_enabled is True

    def test_username_and_password_with_spaces_are_trim_checked(self) -> None:
        cfg = MQTTConfig(username=" admin ", password=" secret ")
        assert cfg.username == " admin "
        assert cfg.password == " secret "


class TestMQTTConfigValidation:
    """Tests for Pydantic field and cross-field validation."""

    def test_empty_broker_raises(self) -> None:
        with pytest.raises(ValidationError, match="broker"):
            MQTTConfig(broker="")

    def test_port_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="port"):
            MQTTConfig(port=0)

    def test_port_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="port"):
            MQTTConfig(port=-1)

    def test_port_too_high_raises(self) -> None:
        with pytest.raises(ValidationError, match="port"):
            MQTTConfig(port=65536)

    def test_port_boundary_low(self) -> None:
        cfg = MQTTConfig(port=1)
        assert cfg.port == 1

    def test_port_boundary_high(self) -> None:
        cfg = MQTTConfig(port=65535)
        assert cfg.port == 65535

    def test_keepalive_too_low(self) -> None:
        with pytest.raises(ValidationError, match="keepalive"):
            MQTTConfig(keepalive=9)

    def test_keepalive_boundary(self) -> None:
        cfg = MQTTConfig(keepalive=10)
        assert cfg.keepalive == 10

    def test_reconnect_min_delay_zero(self) -> None:
        with pytest.raises(ValidationError, match="reconnect_min_delay"):
            MQTTConfig(reconnect_min_delay=0)

    def test_reconnect_min_delay_negative(self) -> None:
        with pytest.raises(ValidationError, match="reconnect_min_delay"):
            MQTTConfig(reconnect_min_delay=-1)

    def test_reconnect_max_delay_zero(self) -> None:
        with pytest.raises(ValidationError, match="reconnect_max_delay"):
            MQTTConfig(reconnect_max_delay=0)

    def test_reconnect_min_exceeds_max(self) -> None:
        with pytest.raises(
            ValidationError, match=r"reconnect_min_delay.*must be <= reconnect_max_delay"
        ):
            MQTTConfig(reconnect_min_delay=120, reconnect_max_delay=60)

    def test_password_without_username(self) -> None:
        with pytest.raises(ValidationError, match="username and password must be set together"):
            MQTTConfig(password="secret")

    def test_username_without_password_raises(self) -> None:
        with pytest.raises(ValidationError, match="username and password must be set together"):
            MQTTConfig(username="admin")

    def test_blank_username_raises(self) -> None:
        with pytest.raises(ValidationError, match="username cannot be empty"):
            MQTTConfig(username="   ", password="secret")

    def test_blank_password_raises(self) -> None:
        with pytest.raises(ValidationError, match="password cannot be empty"):
            MQTTConfig(username="admin", password="   ")

    def test_frozen_model_prevents_mutation(self) -> None:
        cfg = MQTTConfig()
        with pytest.raises(ValidationError):
            cfg.broker = "other"

    def test_type_coercion_string_port(self) -> None:
        """Pydantic coerces compatible types."""
        cfg = MQTTConfig(port="8883")  # type: ignore[arg-type]
        assert cfg.port == 8883

    def test_model_dump(self) -> None:
        cfg = MQTTConfig(broker="mqtt.local", port=8883)
        data = cfg.model_dump()
        assert data["broker"] == "mqtt.local"
        assert data["port"] == 8883
        assert isinstance(data, dict)


class TestGetMQTTConfig:
    """Tests for building MQTTConfig from application settings."""

    def test_get_mqtt_config_uses_app_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = AppSettings(
            mqtt_broker="mqtt.internal",
            mqtt_port=1884,
            mqtt_client_id="api_service",
            mqtt_username="svc_user",
            mqtt_password="svc_pass",
            mqtt_keepalive=120,
            mqtt_tls_enabled=True,
            mqtt_reconnect_min_delay=2,
            mqtt_reconnect_max_delay=30,
        )
        monkeypatch.setattr("backend.mqtt.config.get_settings", lambda: settings)

        cfg = get_mqtt_config()

        assert cfg.broker == "mqtt.internal"
        assert cfg.port == 1884
        assert cfg.client_id == "api_service"
        assert cfg.username == "svc_user"
        assert cfg.password == "svc_pass"
        assert cfg.keepalive == 120
        assert cfg.tls_enabled is True
        assert cfg.reconnect_min_delay == 2
        assert cfg.reconnect_max_delay == 30
