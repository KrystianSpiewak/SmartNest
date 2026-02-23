"""Unit tests for SmartNest TUI application."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

from rich.console import Console

from backend.logging.catalog import MessageCode
from backend.tui.app import SmartNestTUI


class TestSmartNestTUIInit:
    """Tests for SmartNestTUI initialization."""

    def test_creates_console(self) -> None:
        """TUI creates Rich Console instance."""
        tui = SmartNestTUI()
        assert isinstance(tui.console, Console)

    def test_initially_not_running(self) -> None:
        """TUI is not running before startup() called."""
        tui = SmartNestTUI()
        assert tui.is_running is False

    def test_logs_initialization(self) -> None:
        """TUI logs initialization with correct message code."""
        with patch("backend.tui.app.log_with_code") as mock_log:
            SmartNestTUI()
            # Verify log_with_code was called with TUI_INITIALIZED
            assert mock_log.call_count == 1
            call_args = mock_log.call_args
            # Check message code (3rd positional argument)
            assert call_args.args[2] == MessageCode.TUI_INITIALIZED
            # Check log level (2nd positional argument)
            assert call_args.args[1] == "debug"


class TestSmartNestTUIStartup:
    """Tests for TUI startup."""

    def test_startup_sets_running_flag(self) -> None:
        """startup() sets is_running to True."""
        tui = SmartNestTUI()
        tui.startup()
        assert tui.is_running is True

    def test_startup_logs_with_code(self) -> None:
        """startup() logs TUI_STARTED message code."""
        tui = SmartNestTUI()
        with patch("backend.tui.app.log_with_code") as mock_log:
            # Clear initialization log call
            mock_log.reset_mock()
            tui.startup()
            # Should log TUI_STARTED
            assert any(call.args[2] == MessageCode.TUI_STARTED for call in mock_log.call_args_list)

    def test_startup_prints_welcome(self) -> None:
        """startup() prints welcome message to console."""
        tui = SmartNestTUI()
        with patch.object(tui.console, "print") as mock_print:
            tui.startup()
            # Should print welcome message
            assert mock_print.call_count >= 1
            # First call should contain "SmartNest TUI"
            first_call_arg = str(mock_print.call_args_list[0].args[0])
            assert "SmartNest TUI" in first_call_arg


class TestSmartNestTUIShutdown:
    """Tests for TUI shutdown."""

    def test_shutdown_clears_running_flag(self) -> None:
        """shutdown() sets is_running to False."""
        tui = SmartNestTUI()
        tui.is_running = True
        with patch("sys.exit"):  # Prevent actual exit
            tui.shutdown()
        assert tui.is_running is False

    def test_shutdown_idempotent(self) -> None:
        """shutdown() can be called multiple times safely."""
        tui = SmartNestTUI()
        tui.is_running = True
        with patch("sys.exit"):
            tui.shutdown()
            # Second call should be no-op
            tui.shutdown()
        assert tui.is_running is False

    def test_shutdown_logs_with_code(self) -> None:
        """shutdown() logs TUI_SHUTDOWN message code."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch("sys.exit"),
        ):
            # Clear initialization log call
            mock_log.reset_mock()
            tui.shutdown()
            # Should log TUI_SHUTDOWN
            assert any(call.args[2] == MessageCode.TUI_SHUTDOWN for call in mock_log.call_args_list)

    def test_shutdown_prints_goodbye(self) -> None:
        """shutdown() prints goodbye message to console."""
        tui = SmartNestTUI()
        tui.is_running = True
        with (
            patch.object(tui.console, "print") as mock_print,
            patch("sys.exit"),
        ):
            tui.shutdown()
            # Should print shutdown message
            assert mock_print.call_count >= 1
            # Should contain "Shutting down"
            printed_text = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
            assert "Shutting down" in printed_text


class TestSmartNestTUISignalHandlers:
    """Tests for signal handler registration."""

    def test_sigint_handler_registered(self) -> None:
        """SIGINT handler is registered during initialization."""
        with patch("signal.signal") as mock_signal:
            tui = SmartNestTUI()
            # Should register SIGINT handler
            sigint_calls = [
                call for call in mock_signal.call_args_list if call.args[0] == signal.SIGINT
            ]
            assert len(sigint_calls) == 1
            assert sigint_calls[0].args[1] == tui._handle_sigint

    def test_sigterm_handler_registered(self) -> None:
        """SIGTERM handler is registered during initialization."""
        with patch("signal.signal") as mock_signal:
            tui = SmartNestTUI()
            # Should register SIGTERM handler
            sigterm_calls = [
                call for call in mock_signal.call_args_list if call.args[0] == signal.SIGTERM
            ]
            assert len(sigterm_calls) == 1
            assert sigterm_calls[0].args[1] == tui._handle_sigterm

    def test_sigint_handler_logs_signal(self) -> None:
        """SIGINT handler logs shutdown request with signal name."""
        tui = SmartNestTUI()
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch.object(tui, "shutdown"),
        ):
            mock_log.reset_mock()
            tui._handle_sigint(2, None)  # SIGINT = 2
            # Should log with signal name
            assert any(
                call.args[2] == MessageCode.TUI_SHUTDOWN_REQUESTED
                and "signal" in call.kwargs
                and call.kwargs["signal"] == "SIGINT"
                for call in mock_log.call_args_list
            )

    def test_sigterm_handler_logs_signal(self) -> None:
        """SIGTERM handler logs shutdown request with signal name."""
        tui = SmartNestTUI()
        with (
            patch("backend.tui.app.log_with_code") as mock_log,
            patch.object(tui, "shutdown"),
        ):
            mock_log.reset_mock()
            tui._handle_sigterm(15, None)  # SIGTERM = 15
            # Should log with signal name
            assert any(
                call.args[2] == MessageCode.TUI_SHUTDOWN_REQUESTED
                and "signal" in call.kwargs
                and call.kwargs["signal"] == "SIGTERM"
                for call in mock_log.call_args_list
            )

    def test_sigint_handler_calls_shutdown(self) -> None:
        """SIGINT handler calls shutdown()."""
        tui = SmartNestTUI()
        with patch.object(tui, "shutdown") as mock_shutdown:
            tui._handle_sigint(2, None)
            mock_shutdown.assert_called_once()

    def test_sigterm_handler_calls_shutdown(self) -> None:
        """SIGTERM handler calls shutdown()."""
        tui = SmartNestTUI()
        with patch.object(tui, "shutdown") as mock_shutdown:
            tui._handle_sigterm(15, None)
            mock_shutdown.assert_called_once()


class TestSmartNestTUIRun:
    """Tests for TUI run() method."""

    def test_run_calls_startup(self) -> None:
        """run() calls startup() before main loop."""
        tui = SmartNestTUI()
        with (
            patch.object(tui, "startup") as mock_startup,
            patch("time.sleep", side_effect=KeyboardInterrupt),  # Exit loop immediately
            patch.object(tui, "shutdown"),
        ):
            tui.is_running = True  # Simulate startup setting this
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            mock_startup.assert_called_once()

    def test_run_calls_shutdown_on_keyboard_interrupt(self) -> None:
        """run() calls shutdown() when KeyboardInterrupt raised."""
        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch("time.sleep", side_effect=KeyboardInterrupt),
            patch.object(tui, "shutdown") as mock_shutdown,
        ):
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            # shutdown() called in finally block
            mock_shutdown.assert_called_once()

    def test_run_handles_graceful_shutdown(self) -> None:
        """run() handles graceful shutdown in finally block."""
        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch("time.sleep", side_effect=KeyboardInterrupt),
            patch("sys.exit") as mock_exit,
            patch.object(tui.console, "print"),
        ):
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            # shutdown() should have been called, which calls sys.exit(0)
            assert tui.is_running is False
            mock_exit.assert_called_once_with(0)

    def test_run_uses_signal_pause_on_unix(self) -> None:
        """run() uses signal.pause() on Unix systems."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        # Mock signal to have pause method
        mock_signal = MagicMock()
        mock_signal.pause = MagicMock(side_effect=KeyboardInterrupt)
        mock_signal.SIGINT = signal.SIGINT
        mock_signal.SIGTERM = signal.SIGTERM
        mock_signal.signal = signal.signal

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", mock_signal),
            patch.object(tui, "shutdown"),
        ):
            try:
                tui.run()
            except (KeyboardInterrupt, SystemExit):
                pass
            # signal.pause() should have been called
            mock_signal.pause.assert_called_once()

    def test_run_uses_time_sleep_on_windows(self) -> None:
        """run() uses time.sleep() loop when signal.pause() not available."""
        import backend.tui.app as app_module  # noqa: PLC0415

        tui = SmartNestTUI()

        def fake_startup() -> None:
            tui.is_running = True

        # Mock signal to not have pause method (like Windows)
        mock_signal = MagicMock(spec=[])  # Empty spec = no attributes
        mock_signal.SIGINT = signal.SIGINT
        mock_signal.SIGTERM = signal.SIGTERM
        mock_signal.signal = signal.signal

        sleep_count = 0

        def fake_sleep(_duration: float) -> None:
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 3:  # Run a few iterations then stop
                tui.is_running = False  # Exit cleanly

        with (
            patch.object(tui, "startup", side_effect=fake_startup),
            patch.object(app_module, "signal", mock_signal),
            patch.object(app_module, "time", MagicMock(sleep=MagicMock(side_effect=fake_sleep))),
            patch.object(tui, "shutdown") as mock_shutdown,
        ):
            tui.run()
            # time.sleep() should have been called multiple times
            assert sleep_count >= 3
            # shutdown() should be called when loop exits
            mock_shutdown.assert_called_once()


class TestMain:
    """Tests for main() entry point."""

    def test_main_creates_tui_and_runs(self) -> None:
        """main() creates SmartNestTUI instance and calls run()."""
        from backend.tui.app import main  # noqa: PLC0415

        with (
            patch("backend.tui.app.SmartNestTUI") as mock_tui_class,
        ):
            mock_tui_instance = MagicMock()
            mock_tui_class.return_value = mock_tui_instance

            main()

            # Should create TUI instance
            mock_tui_class.assert_called_once()
            # Should call run() on instance
            mock_tui_instance.run.assert_called_once()
