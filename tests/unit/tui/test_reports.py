"""Unit tests for ReportsScreen."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from backend.tui.screens.reports import ReportsScreen


@pytest.fixture
def mock_console() -> MagicMock:
    """Create mock Console for testing."""
    return MagicMock()


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client for testing."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def reports_screen(mock_console: MagicMock, mock_http_client: MagicMock) -> ReportsScreen:
    """Create ReportsScreen instance for testing."""
    return ReportsScreen(mock_console, mock_http_client)


class TestReportsScreenFetchSummary:
    """Tests for fetch_summary()."""

    def test_fetch_summary_success(
        self, reports_screen: ReportsScreen, mock_http_client: MagicMock
    ) -> None:
        """fetch_summary() stores API payload and returns True."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total_devices": 5,
            "online_devices": 4,
            "offline_devices": 1,
            "sensor_devices": 2,
            "response_time_ms": 12,
        }
        mock_http_client.get.return_value = mock_response

        result = reports_screen.fetch_summary()

        assert result is True
        assert reports_screen.summary["total_devices"] == 5
        mock_http_client.get.assert_called_once_with("/api/reports/dashboard-summary")

    def test_fetch_summary_error(
        self, reports_screen: ReportsScreen, mock_http_client: MagicMock
    ) -> None:
        """fetch_summary() clears state and returns False on error."""
        reports_screen.summary = {"stale": True}
        mock_http_client.get.side_effect = httpx.ConnectError("refused")

        result = reports_screen.fetch_summary()

        assert result is False
        assert reports_screen.summary == {}

    def test_fetch_summary_uses_cached_result_within_interval(
        self, reports_screen: ReportsScreen, mock_http_client: MagicMock
    ) -> None:
        """fetch_summary() returns cached status when called again within throttle window."""
        reports_screen._last_fetch_at = 100.0
        reports_screen._last_fetch_success = True
        reports_screen._fetch_interval_seconds = 2.0

        with patch("backend.tui.screens.reports.time.monotonic", return_value=101.0):
            result = reports_screen.fetch_summary()

        assert result is True
        mock_http_client.get.assert_not_called()

    def test_refresh_now_forces_fetch(self, reports_screen: ReportsScreen) -> None:
        """refresh_now() resets throttle state and calls fetch_summary()."""
        reports_screen._last_fetch_at = 100.0
        reports_screen.fetch_summary = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = reports_screen.refresh_now()

        assert result is True
        assert reports_screen._last_fetch_at == 0.0
        reports_screen.fetch_summary.assert_called_once_with()


class TestReportsScreenRendering:
    """Tests for render helpers and live rendering."""

    def test_render_live_success(self, reports_screen: ReportsScreen) -> None:
        """render_live() returns Group with report data on success."""
        reports_screen.summary = {
            "total_devices": 7,
            "online_devices": 6,
            "offline_devices": 1,
            "sensor_devices": 3,
            "response_time_ms": 20,
        }
        reports_screen.fetch_summary = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = reports_screen.render_live()

        assert isinstance(result, Group)

    def test_render_live_error(self, reports_screen: ReportsScreen) -> None:
        """render_live() returns Group on API error path too."""
        reports_screen.fetch_summary = MagicMock(return_value=False)  # type: ignore[method-assign]

        result = reports_screen.render_live()

        assert isinstance(result, Group)

    def test_render_report_table_success(self, reports_screen: ReportsScreen) -> None:
        """_render_report_table() returns Panel for populated summary."""
        reports_screen.summary = {
            "total_devices": 10,
            "online_devices": 8,
            "offline_devices": 2,
            "sensor_devices": 4,
            "response_time_ms": 33,
        }

        panel = reports_screen._render_report_table(api_success=True)

        assert isinstance(panel, Panel)

    def test_render_report_table_error(self, reports_screen: ReportsScreen) -> None:
        """_render_report_table() returns error panel on fetch failure."""
        panel = reports_screen._render_report_table(api_success=False)

        assert isinstance(panel, Panel)

    def test_render_header(self, reports_screen: ReportsScreen) -> None:
        """_render_header() returns Panel."""
        header = reports_screen._render_header()
        assert isinstance(header, Panel)

    def test_render_actions(self, reports_screen: ReportsScreen) -> None:
        """_render_actions() returns Panel."""
        actions = reports_screen._render_actions()
        assert isinstance(actions, Panel)

    def test_render_menu(self, reports_screen: ReportsScreen) -> None:
        """_render_menu() returns Text navigation helper."""
        menu = reports_screen._render_menu()
        assert isinstance(menu, Text)
