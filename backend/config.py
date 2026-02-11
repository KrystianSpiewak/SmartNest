"""SmartNest application settings.

Loads configuration from environment variables and ``.env`` files using
``pydantic-settings``.  All variables are prefixed with ``SMARTNEST_`` to
avoid collisions with system environment.

Usage::

    from backend.config import get_settings

    settings = get_settings()
    print(settings.mqtt_broker)  # from SMARTNEST_MQTT_BROKER
    print(settings.log_level)  # from SMARTNEST_LOG_LEVEL
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application-wide settings loaded from environment and ``.env`` files.

    Environment variables use the ``SMARTNEST_`` prefix.
    Nested MQTT fields use ``SMARTNEST_MQTT_`` prefix, etc.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SMARTNEST_",
        extra="ignore",
    )

    # -- Logging ---------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_renderer: Literal["console", "json"] = "console"

    # -- MQTT ------------------------------------------------------------------
    mqtt_broker: str = "localhost"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_client_id: str = "smartnest_main"
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_keepalive: int = Field(default=60, ge=10)
    mqtt_tls_enabled: bool = False
    mqtt_reconnect_min_delay: int = Field(default=1, gt=0)
    mqtt_reconnect_max_delay: int = Field(default=60, gt=0)

    # -- Database --------------------------------------------------------------
    database_url: str = "smartnest.db"

    # -- Security --------------------------------------------------------------
    jwt_secret: str = Field(
        default="",
        description="JWT signing secret - MUST be set in production",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=15, gt=0)
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)

    # -- Default Admin User ----------------------------------------------------
    # These are ONLY used if users table is empty during init_database()
    admin_username: str = Field(
        default="",
        description="Initial admin username (required for first setup)",
    )
    admin_email: str = Field(
        default="",
        description="Initial admin email (required for first setup)",
    )
    admin_password: str = Field(
        default="",
        description="Initial admin password (required for first setup)",
    )

    # -- Server ----------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached application settings singleton.

    Uses ``lru_cache`` so the settings are loaded once and reused.
    Call ``get_settings.cache_clear()`` in tests to reset.
    """
    return AppSettings()
