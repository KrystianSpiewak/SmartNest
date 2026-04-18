#!/usr/bin/env python3
"""Wait for SmartNest API health endpoint readiness.

Usage:
    python scripts/wait_for_api_health.py
    npm run smoke:health
"""

from __future__ import annotations

import argparse
import http.client
import json
import time
from typing import Any
from urllib.parse import ParseResult, urlparse

DEFAULT_HEALTH_URL = "http://127.0.0.1:8000/health"
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
HTTP_STATUS_OK = 200


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Wait for SmartNest API health endpoint.")
    parser.add_argument("--url", default=DEFAULT_HEALTH_URL, help="Health endpoint URL")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Seconds to wait before failing",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between health checks",
    )
    return parser.parse_args()


def parse_and_validate_url(url: str) -> ParseResult | None:
    """Return parsed URL when it is safe for local smoke checks."""
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        return None

    if parsed.hostname not in ALLOWED_HOSTS:
        return None

    return parsed


def check_health(url: str) -> tuple[bool, dict[str, Any] | None]:
    """Return health status and decoded payload when available."""
    parsed = parse_and_validate_url(url)
    if parsed is None:
        return False, None

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    connection_cls = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    conn = connection_cls(parsed.hostname, port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        payload = response.read().decode("utf-8")
    except OSError:
        return False, None
    finally:
        conn.close()

    if response.status != HTTP_STATUS_OK:
        return False, None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False, None

    return data.get("status") == "healthy", data


def main() -> int:
    """Poll health endpoint until healthy or timeout."""
    args = parse_args()

    if args.timeout <= 0:
        print("Timeout must be greater than 0 seconds.")
        return 1

    if args.interval <= 0:
        print("Interval must be greater than 0 seconds.")
        return 1

    if parse_and_validate_url(args.url) is None:
        print("Health URL must use http/https and localhost or 127.0.0.1.")
        return 1

    deadline = time.monotonic() + args.timeout

    while time.monotonic() < deadline:
        is_healthy, payload = check_health(args.url)
        if is_healthy:
            print(f"API healthy at {args.url}: {payload}")
            return 0
        time.sleep(args.interval)

    print(f"Timed out after {args.timeout:.1f}s waiting for API health at {args.url}.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
