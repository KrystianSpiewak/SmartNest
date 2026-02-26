"""Unit tests for backend main entry point."""

from __future__ import annotations

from unittest.mock import patch

from backend.config import AppSettings
from backend.main import main


class TestMain:
    """Tests for main() entry point."""

    def test_main_gets_settings(self) -> None:
        """main() retrieves application settings."""
        with (
            patch("backend.main.get_settings") as mock_get_settings,
            patch("backend.main.uvicorn.run"),
        ):
            mock_settings = AppSettings()
            mock_get_settings.return_value = mock_settings

            main()

            # Should call get_settings()
            mock_get_settings.assert_called_once()

    def test_main_starts_uvicorn_with_settings(self) -> None:
        """main() starts uvicorn with settings from config."""
        with (
            patch("backend.main.get_settings") as mock_get_settings,
            patch("backend.main.uvicorn.run") as mock_run,
        ):
            mock_settings = AppSettings(host="127.0.0.1", port=9000)
            mock_get_settings.return_value = mock_settings

            main()

            # Should start uvicorn with correct parameters
            mock_run.assert_called_once_with(
                "backend.app:app",
                host="127.0.0.1",
                port=9000,
                reload=True,
                log_level="info",
            )

    def test_main_uses_default_host_and_port(self) -> None:
        """main() uses default host and port from Settings."""
        with (
            patch("backend.main.get_settings") as mock_get_settings,
            patch("backend.main.uvicorn.run") as mock_run,
        ):
            # Use defaults from AppSettings
            mock_settings = AppSettings()
            mock_get_settings.return_value = mock_settings

            main()

            # Should use default host/port
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["host"] == "127.0.0.1"
            assert call_kwargs["port"] == 8000

    def test_main_enables_reload(self) -> None:
        """main() enables auto-reload for development."""
        with (
            patch("backend.main.get_settings"),
            patch("backend.main.uvicorn.run") as mock_run,
        ):
            main()

            # Should have reload=True
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["reload"] is True

    def test_main_sets_log_level_info(self) -> None:
        """main() sets log level to info."""
        with (
            patch("backend.main.get_settings"),
            patch("backend.main.uvicorn.run") as mock_run,
        ):
            main()

            # Should set log_level="info"
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["log_level"] == "info"
