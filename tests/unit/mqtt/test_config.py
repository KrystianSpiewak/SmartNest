"""Unit tests for SmartNest MQTT configuration."""

from __future__ import annotations

import pytest

from backend.mqtt.config import MQTTConfig


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

    def test_username_without_password(self) -> None:
        cfg = MQTTConfig(username="admin")
        assert cfg.username == "admin"
        assert cfg.password is None


class TestMQTTConfigValidation:
    """Tests for configuration validation in __post_init__."""

    def test_empty_broker_raises(self) -> None:
        with pytest.raises(ValueError, match="broker must not be empty"):
            MQTTConfig(broker="")

    def test_port_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid port"):
            MQTTConfig(port=0)

    def test_port_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid port"):
            MQTTConfig(port=-1)

    def test_port_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid port"):
            MQTTConfig(port=65536)

    def test_port_boundary_low(self) -> None:
        cfg = MQTTConfig(port=1)
        assert cfg.port == 1

    def test_port_boundary_high(self) -> None:
        cfg = MQTTConfig(port=65535)
        assert cfg.port == 65535

    def test_keepalive_too_low(self) -> None:
        with pytest.raises(ValueError, match="Invalid keepalive"):
            MQTTConfig(keepalive=9)

    def test_keepalive_boundary(self) -> None:
        cfg = MQTTConfig(keepalive=10)
        assert cfg.keepalive == 10

    def test_reconnect_min_delay_zero(self) -> None:
        with pytest.raises(ValueError, match="reconnect_min_delay must be > 0"):
            MQTTConfig(reconnect_min_delay=0)

    def test_reconnect_min_delay_negative(self) -> None:
        with pytest.raises(ValueError, match="reconnect_min_delay must be > 0"):
            MQTTConfig(reconnect_min_delay=-1)

    def test_reconnect_max_delay_zero(self) -> None:
        with pytest.raises(ValueError, match="reconnect_max_delay must be > 0"):
            MQTTConfig(reconnect_max_delay=0)

    def test_reconnect_min_exceeds_max(self) -> None:
        with pytest.raises(
            ValueError, match=r"reconnect_min_delay.*must be <= reconnect_max_delay"
        ):
            MQTTConfig(reconnect_min_delay=120, reconnect_max_delay=60)

    def test_password_without_username(self) -> None:
        with pytest.raises(ValueError, match="password requires username"):
            MQTTConfig(password="secret")
