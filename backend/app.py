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

from backend.config import get_settings
from backend.database.connection import init_database
from backend.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan with startup and shutdown logic.

    Startup:
        - Initialize database (create schema, admin user)
        - TODO: Start MQTT client (Phase 6)

    Shutdown:
        - TODO: Stop MQTT client (Phase 6)

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

    logger.info("fastapi_started")

    yield  # Application runs here

    # Shutdown
    logger.info("fastapi_stopping")
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
