"""SmartNest MQTT Client Configuration.

Uses Pydantic ``BaseModel`` for declarative validation, type coercion,
and serialization of MQTT broker connection parameters.
"""

from __future__ import annotations

import contextlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.logging import get_logger

logger = get_logger(__name__)


class MQTTConfig(BaseModel):
    """MQTT broker connection configuration.

    Attributes:
        broker: Hostname or IP address of the MQTT broker.
        port: TCP port (1-65535).
        client_id: MQTT client identifier sent to the broker.
        username: Broker authentication username (``None`` to skip auth).
        password: Broker authentication password.
        keepalive: Maximum seconds between broker pings (≥ 10).
        tls_enabled: Whether to use TLS/SSL for the connection.
        reconnect_min_delay: Initial reconnect wait in seconds (> 0).
        reconnect_max_delay: Maximum reconnect wait in seconds (> 0).
    """

    model_config = ConfigDict(frozen=True)

    broker: str = Field(default="localhost", min_length=1)
    port: int = Field(default=1883, ge=1, le=65535)
    client_id: str = "smartnest_main"
    username: str | None = None
    password: str | None = None
    keepalive: int = Field(default=60, ge=10)
    tls_enabled: bool = False
    reconnect_min_delay: int = Field(default=1, gt=0)
    reconnect_max_delay: int = Field(default=60, gt=0)

    @model_validator(mode="after")
    def _validate_cross_field_constraints(self) -> MQTTConfig:
        """Validate constraints that span multiple fields."""
        if self.reconnect_min_delay > self.reconnect_max_delay:
            msg = (
                f"reconnect_min_delay ({self.reconnect_min_delay}) "
                f"must be <= reconnect_max_delay ({self.reconnect_max_delay})"
            )
            raise ValueError(msg)

        if self.password is not None and self.username is None:
            msg = "password requires username to be set"
            raise ValueError(msg)

        with contextlib.suppress(OSError, ValueError):
            # Logging may not be configured (e.g., during mutation testing).
            logger.debug(
                "MQTTConfig created",
                broker=self.broker,
                port=self.port,
                client_id=self.client_id,
            )

        return self
