"""API routes package.

Contains all FastAPI routers for different resource endpoints.
"""

from backend.api.routes.devices import router as devices_router

__all__ = ["devices_router"]
