"""Unit tests for backend package version."""

from __future__ import annotations

import json
from pathlib import Path

import backend


class TestBackendVersion:
    """Tests for backend package version."""

    def test_version_exists(self) -> None:
        """Backend package has __version__ attribute."""
        assert hasattr(backend, "__version__")

    def test_version_format(self) -> None:
        """Version follows semantic versioning format."""
        version = backend.__version__
        # Should be in format X.Y.Z
        parts = version.split(".")
        assert len(parts) == 3
        # All parts should be numeric
        for part in parts:
            assert part.isdigit()

    def test_version_matches_package_json(self) -> None:
        """Version matches package.json."""
        package_json_path = Path(__file__).parent.parent.parent / "package.json"
        with open(package_json_path) as f:
            package_data = json.load(f)

        assert backend.__version__ == package_data["version"]
