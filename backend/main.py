"""
SmartNest Backend API Server Entry Point

Starts the FastAPI application with uvicorn.
"""

import uvicorn

from backend.config import get_settings


def main() -> None:
    """Start the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
