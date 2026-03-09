"""Unit tests for backend.tui.__main__ entry point."""

from __future__ import annotations

import inspect
import logging
from unittest.mock import MagicMock, patch

import backend.tui.__main__


class TestTUIMain:
    """Tests for TUI __main__ entry point."""

    def test_main_entry_point_imports_correctly(self) -> None:
        """__main__ module can be imported."""
        # This test verifies the __main__.py file structure is valid
        # Module already imported at module level, just verify it exists
        assert hasattr(backend.tui.__main__, "main")

    def test_main_entry_point_calls_main(self) -> None:
        """Running __main__ calls main() function."""
        # The __name__ == "__main__" block is only executed when running
        # as a module, not during import. We test that the block exists
        # and would call main() by checking the module structure.
        source = inspect.getsource(backend.tui.__main__)
        # Verify the module has the __main__ guard and calls main()
        assert 'if __name__ == "__main__"' in source
        assert "main()" in source

    @patch("backend.tui.__main__.configure_logging")
    @patch("backend.tui.app.main")
    def test_main_function_configures_logging(
        self, mock_tui_main: MagicMock, mock_configure_logging: MagicMock
    ) -> None:
        """main() configures logging before launching TUI."""
        backend.tui.__main__.main()

        # Verify logging was configured
        mock_configure_logging.assert_called_once_with(level="CRITICAL", renderer="console")
        # Verify TUI was launched
        mock_tui_main.assert_called_once()

    @patch.dict("os.environ", {"SMARTNEST_TUI_LOG_LEVEL": "DEBUG"})
    @patch("backend.tui.__main__.configure_logging")
    @patch("backend.tui.app.main")
    def test_main_function_respects_log_level_env_var(
        self, mock_tui_main: MagicMock, mock_configure_logging: MagicMock
    ) -> None:
        """main() uses SMARTNEST_TUI_LOG_LEVEL environment variable."""
        backend.tui.__main__.main()

        # Verify logging was configured with custom level
        mock_configure_logging.assert_called_once_with(level="DEBUG", renderer="console")
        mock_tui_main.assert_called_once()

    @patch("backend.tui.__main__.configure_logging")
    @patch("backend.tui.app.main")
    def test_main_function_silences_paho_loggers(
        self, mock_tui_main: MagicMock, mock_configure_logging: MagicMock
    ) -> None:
        """main() silences Paho MQTT loggers to prevent terminal interference."""
        # Reset logger levels first to avoid test pollution from earlier main() calls
        logging.getLogger("paho").setLevel(logging.NOTSET)
        logging.getLogger("paho.mqtt").setLevel(logging.NOTSET)
        logging.getLogger("paho.mqtt.client").setLevel(logging.NOTSET)

        backend.tui.__main__.main()

        # Verify Paho loggers are set to CRITICAL
        assert logging.getLogger("paho").level == logging.CRITICAL
        assert logging.getLogger("paho.mqtt").level == logging.CRITICAL
        assert logging.getLogger("paho.mqtt.client").level == logging.CRITICAL
