"""SmartNest FastAPI Application.

This module provides the main FastAPI application with async lifespan management
for database initialization and graceful shutdown.

Usage:
    uvicorn backend.app:app --reload
    # Visit http://localhost:8000/docs for API documentation
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.mqtt_bridge import MQTTBridge
from backend.api.routes import devices_router, users_router
from backend.config import get_settings
from backend.database.connection import init_database
from backend.logging import get_logger
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import get_mqtt_config

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan with startup and shutdown logic.

    Startup:
        - Initialize database (create schema, admin user)
        - Connect to MQTT broker
        - Start MQTT bridge (device discovery → database)

    Shutdown:
        - Stop MQTT bridge
        - Disconnect from MQTT broker

    Args:
        app: FastAPI application instance

    Yields:
        None: Control to the application during its lifetime
    """
    # Startup
    settings = get_settings()
    logger.info("fastapi_starting", host=settings.host, port=settings.port)

    # Initialize database
    await init_database()
    logger.info("database_initialized")

    # Initialize MQTT client and bridge
    mqtt_config = get_mqtt_config()
    mqtt_client = SmartNestMQTTClient(mqtt_config)
    mqtt_client.connect()
    logger.info("mqtt_connected", broker=mqtt_config.broker)

    # Start MQTT bridge for device discovery
    mqtt_bridge = MQTTBridge(mqtt_client)
    await mqtt_bridge.start()
    logger.info("mqtt_bridge_started")

    # Sync any devices discovered before API started
    synced = await mqtt_bridge.sync_discovered_devices()
    logger.info("devices_synced", count=synced)

    logger.info("fastapi_started")

    yield  # Application runs here

    # Shutdown
    logger.info("fastapi_stopping")

    # Stop MQTT bridge
    await mqtt_bridge.stop()
    logger.info("mqtt_bridge_stopped")

    # Disconnect MQTT client
    mqtt_client.disconnect()
    logger.info("mqtt_disconnected")

    logger.info("fastapi_stopped")


# Create FastAPI application
app = FastAPI(
    title="SmartNest API",
    description="Home Automation Management System - IoT device control and monitoring",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for TUI access on localhost
# Note: In production, replace regex pattern with specific allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register API routes
app.include_router(devices_router)
app.include_router(users_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        dict: Status indicator showing the API is operational

    Example:
        ```
        GET / health
        Response: {"status": "healthy"}
        ```
    """
    return {"status": "healthy"}
