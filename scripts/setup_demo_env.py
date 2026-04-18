#!/usr/bin/env python3
"""Prepare local .env values for SmartNest demo runs.

This script:
1) Creates .env from .env.example when missing.
2) Ensures required demo values are present.
3) Prints login credentials for quick TUI verification.
"""

from __future__ import annotations

import argparse
import secrets
import string
from pathlib import Path

ENV_FILE = Path(".env")
TEMPLATE_FILE = Path(".env.example")
PLACEHOLDER_PREFIX = "REPLACE_WITH_"
PASSWORD_LENGTH = 20

REQUIRED_KEYS = (
    "SMARTNEST_ADMIN_USERNAME",
    "SMARTNEST_ADMIN_EMAIL",
    "SMARTNEST_ADMIN_PASSWORD",
    "SMARTNEST_JWT_SECRET",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Create/update local SmartNest demo .env values.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate required values even if .env already has non-placeholder values.",
    )
    return parser.parse_args()


def generate_password(length: int = PASSWORD_LENGTH) -> str:
    """Return a strong demo password with letters and digits."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_demo_values() -> dict[str, str]:
    """Build fresh values for required demo keys."""
    return {
        "SMARTNEST_ADMIN_USERNAME": "admin",
        "SMARTNEST_ADMIN_EMAIL": "admin@smartnest.local",
        "SMARTNEST_ADMIN_PASSWORD": generate_password(),
        "SMARTNEST_JWT_SECRET": secrets.token_urlsafe(48),
    }


def should_replace(value: str, force: bool) -> bool:
    """Return True when a value should be replaced."""
    if force:
        return True
    return value == "" or value.startswith(PLACEHOLDER_PREFIX)


def parse_assignment(line: str) -> tuple[str, str] | None:
    """Parse KEY=VALUE lines, ignoring comments and malformed lines."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    return key.strip(), value.strip()


def ensure_env_file_exists() -> bool:
    """Create .env from template when missing.

    Returns:
        True when .env was newly created, else False.
    """
    if ENV_FILE.exists():
        return False

    if not TEMPLATE_FILE.exists():
        msg = "Missing .env.example. Cannot create demo environment file."
        raise FileNotFoundError(msg)

    ENV_FILE.write_text(TEMPLATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def update_required_values(force: bool) -> dict[str, str]:
    """Update required values in .env and return final required-key values."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    replacements = build_demo_values()

    seen: set[str] = set()
    result_values: dict[str, str] = {}

    for index, line in enumerate(lines):
        assignment = parse_assignment(line)
        if assignment is None:
            continue

        key, value = assignment
        if key not in REQUIRED_KEYS:
            continue

        seen.add(key)

        if should_replace(value, force):
            value = replacements[key]
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{key}={value}{newline}"

        result_values[key] = value

    for key in REQUIRED_KEYS:
        if key in seen:
            continue

        value = replacements[key]
        lines.append(f"{key}={value}\n")
        result_values[key] = value

    ENV_FILE.write_text("".join(lines), encoding="utf-8")
    return result_values


def main() -> int:
    """Run demo environment setup and print resulting credentials."""
    args = parse_args()

    created = ensure_env_file_exists()
    values = update_required_values(force=args.force)

    if created:
        print("Created .env from .env.example")
    else:
        print("Updated existing .env")

    print("SmartNest demo login:")
    print(f"  username: {values['SMARTNEST_ADMIN_USERNAME']}")
    print(f"  email: {values['SMARTNEST_ADMIN_EMAIL']}")
    print(f"  password: {values['SMARTNEST_ADMIN_PASSWORD']}")
    print("JWT secret is configured in .env")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
