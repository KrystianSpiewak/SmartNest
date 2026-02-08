"""SmartNest MQTT Client Configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Validation constants
_PORT_MIN = 1
_PORT_MAX = 65535
_KEEPALIVE_MIN = 10


@dataclass
class MQTTConfig:
    """MQTT broker connection configuration.

    Attributes:
        broker: Hostname or IP address of the MQTT broker.
        port: TCP port (1-65 535).
        client_id: MQTT client identifier sent to the broker.
        username: Broker authentication username (``None`` to skip auth).
        password: Broker authentication password.
        keepalive: Maximum seconds between broker pings (≥ 10).
        tls_enabled: Whether to use TLS/SSL for the connection.
        reconnect_min_delay: Initial reconnect wait in seconds (> 0).
        reconnect_max_delay: Maximum reconnect wait in seconds (> 0).
    """

    broker: str = "localhost"
    port: int = 1883
    client_id: str = "smartnest_main"
    username: str | None = None
    password: str | None = None
    keepalive: int = 60
    tls_enabled: bool = False
    reconnect_min_delay: int = 1
    reconnect_max_delay: int = 60

    def __post_init__(self) -> None:
        """Validate configuration values after dataclass init."""
        if not self.broker:
            msg = "broker must not be empty"
            raise ValueError(msg)

        if not _PORT_MIN <= self.port <= _PORT_MAX:
            msg = f"Invalid port: {self.port}. Must be {_PORT_MIN}\u2013{_PORT_MAX}."
            raise ValueError(msg)

        if self.keepalive < _KEEPALIVE_MIN:
            msg = f"Invalid keepalive: {self.keepalive}. Must be >= {_KEEPALIVE_MIN} seconds."
            raise ValueError(msg)

        if self.reconnect_min_delay <= 0:
            msg = "reconnect_min_delay must be > 0"
            raise ValueError(msg)

        if self.reconnect_max_delay <= 0:
            msg = "reconnect_max_delay must be > 0"
            raise ValueError(msg)

        if self.reconnect_min_delay > self.reconnect_max_delay:
            msg = (
                f"reconnect_min_delay ({self.reconnect_min_delay}) "
                f"must be <= reconnect_max_delay ({self.reconnect_max_delay})"
            )
            raise ValueError(msg)

        if self.password is not None and self.username is None:
            msg = "password requires username to be set"
            raise ValueError(msg)

        logger.debug(
            "MQTTConfig created: broker=%s:%d client_id=%s",
            self.broker,
            self.port,
            self.client_id,
        )
