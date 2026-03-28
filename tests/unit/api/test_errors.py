"""Unit tests for shared API error helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api.errors import (
    map_create_exception,
    raise_bad_request,
    raise_conflict,
    raise_internal_server_error,
    raise_not_found,
    raise_unauthorized,
)


class TestRaiseUnauthorized:
    def test_raises_401_with_bearer_header(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            raise_unauthorized()

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_raises_401_with_custom_detail(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            raise_unauthorized("Custom detail")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Custom detail"


class TestSimpleRaisers:
    def test_raise_not_found(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            raise_not_found("missing")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "missing"

    def test_raise_conflict(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            raise_conflict("conflict")

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "conflict"

    def test_raise_bad_request(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            raise_bad_request("bad")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "bad"

    def test_raise_internal_server_error(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            raise_internal_server_error("oops")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "oops"


class TestMapCreateException:
    def test_unique_error_maps_to_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            map_create_exception(
                Exception("UNIQUE constraint failed"),
                duplicate_detail="already exists",
                fallback_detail="failed",
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "already exists"

    def test_already_exists_error_maps_to_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            map_create_exception(
                Exception("Record already exists"),
                duplicate_detail="already exists",
                fallback_detail="failed",
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "already exists"

    def test_generic_error_maps_to_500(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            map_create_exception(
                Exception("connection lost"),
                duplicate_detail="already exists",
                fallback_detail="failed",
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "failed"
