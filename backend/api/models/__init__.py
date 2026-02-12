"""Pydantic models for API request/response validation.

This package contains data models used for:
- Request validation (input schemas)
- Response serialization (output schemas)
- Documentation generation (OpenAPI schemas)
"""

from backend.api.models.device import (
    DeviceBase,
    DeviceCreate,
    DeviceList,
    DeviceResponse,
)
from backend.api.models.user import UserBase, UserCreate, UserResponse

__all__ = [
    "DeviceBase",
    "DeviceCreate",
    "DeviceList",
    "DeviceResponse",
    "UserBase",
    "UserCreate",
    "UserResponse",
]
