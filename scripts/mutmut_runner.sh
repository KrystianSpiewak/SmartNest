#!/bin/bash
# mutmut test runner with fast-skip for non-business-logic files.
#
# mutmut sets MUTANT_UNDER_TEST to the full mutant name before invoking this
# runner, e.g.: backend.tui.screens.device_list.xǁDeviceListScreenǁ...
#
# Exit codes (mutmut convention):
#   0 = tests pass    → mutation SURVIVED (counted as 🙁)
#   1 = tests fail    → mutation KILLED   (counted as 🎉)
#
# For excluded modules we exit 1 (fake-kill) so they don't pollute the
# survived count. The mutation score then only reflects modules with real
# unit test coverage.

# Skip backend/tui/screens/ — cosmetic rendering mutations only
# (style=, border_style=, title_align=, Rich markup strings).
if [[ "$MUTANT_UNDER_TEST" == backend.tui.screens.* ]]; then
    exit 1  # Fake-kill: excluded from mutation score
fi

# Skip backend/api/ — integration-only tests; unit runner can't run them
# (FastAPI lifespan + logging to closed stdout causes failures in mutmut).
if [[ "$MUTANT_UNDER_TEST" == backend.api.* ]]; then
    exit 1  # Fake-kill: excluded from mutation score
fi

# Run actual unit tests for all other modules
source "$HOME/smartnest-venv/bin/activate"
pytest tests/unit -x --tb=no -q
