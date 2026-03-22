"""API routes package.

Contains all FastAPI routers for different resource endpoints.
"""

from backend.api.routes.auth import router as auth_router
from backend.api.routes.devices import router as devices_router
from backend.api.routes.reports import router as reports_router
from backend.api.routes.sensors import router as sensors_router
from backend.api.routes.users import router as users_router

__all__ = [
    "auth_router",
    "devices_router",
    "reports_router",
    "sensors_router",
    "users_router",
]
