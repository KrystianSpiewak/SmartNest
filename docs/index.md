# SmartNest Documentation

Quick reference for SmartNest project documentation and configuration.

## SmartNest Project Files

### Core Configuration
- [README.md](../README.md) - Project overview, setup, and getting started
- [package.json](../package.json) - npm task runner scripts
- [pyproject.toml](../pyproject.toml) - ruff, pytest, mypy configuration
- [docker-compose.yml](../docker-compose.yml) - HiveMQ MQTT broker container

### Requirements
- [requirements/base.txt](../requirements/base.txt) - Production dependencies
- [requirements/dev.txt](../requirements/dev.txt) - Development dependencies

### Configuration
- [config/mqtt/config.xml](../config/mqtt/config.xml) - MQTT broker configuration
- [config/mqtt/logback-dev.xml](../config/mqtt/logback-dev.xml) - Verbose logging (development, current)
- [config/mqtt/logback-prod.xml](../config/mqtt/logback-prod.xml) - Minimal logging (production)

### Scripts
- [scripts/mqtt_validation_test.py](../scripts/mqtt_validation_test.py) - Broker connectivity test

### Backend MQTT Module
- [backend/mqtt/topics.py](../backend/mqtt/topics.py) - MQTT topic builder (TopicBuilder)
- [backend/mqtt/config.py](../backend/mqtt/config.py) - MQTT connection configuration (MQTTConfig, Pydantic BaseModel)
- [backend/mqtt/client.py](../backend/mqtt/client.py) - Core MQTT client (SmartNestMQTTClient)

### Backend Configuration
- [backend/config.py](../backend/config.py) - Application settings (AppSettings, pydantic-settings)
- [backend/auth/client.py](../backend/auth/client.py) - Shared runtime auth helpers (`login_and_get_access_token`, `set_bearer_token`)
- [.env.example](../.env.example) - Environment variable template (copy to .env)

### Backend Logging Module
- [backend/logging/config.py](../backend/logging/config.py) - Structured logging configuration (structlog, console/JSON renderers)
- [backend/logging/catalog.py](../backend/logging/catalog.py) - Message catalog with stable codes (AIP-193-inspired)
- [backend/logging/utils.py](../backend/logging/utils.py) - Correlation tracking and catalog-aware log helpers
- [backend/logging/__init__.py](../backend/logging/__init__.py) - Public API (configure_logging, get_logger, MessageCode, log_with_code)

### Backend Devices Module (Week 5)
- [backend/devices/base.py](../backend/devices/base.py) - BaseDevice abstract class for all mock devices
- [backend/devices/mock_light.py](../backend/devices/mock_light.py) - MockSmartLight (event-driven controllable device)
- [backend/devices/mock_temperature_sensor.py](../backend/devices/mock_temperature_sensor.py) - MockTemperatureSensor (time-driven periodic sensor)
- [backend/devices/mock_motion_sensor.py](../backend/devices/mock_motion_sensor.py) - MockMotionSensor (event-driven binary sensor)
- [backend/mqtt/discovery.py](../backend/mqtt/discovery.py) - Device discovery protocol (DeviceDiscoveryMessage, DiscoveryConsumer)

### Developer Guides
- [architecture.md](architecture.md) - System architecture, component relationships, data flow diagrams, MQTT topics
- [tui_developer_guide.md](tui_developer_guide.md) - TUI screen implementation patterns, Rich patterns, MQTT integration, testing strategies
- [device_implementation_guide.md](device_implementation_guide.md) - How to create new device types using BaseDevice
- [discovery_protocol.md](discovery_protocol.md) - SmartNest device discovery protocol specification

Reusable Functionality Canonical Reference:
- [architecture.md](architecture.md#shared-components) - Single source of truth for shared runtime components

### Project Planning
- [timeline_optimizations.md](timeline_optimizations.md) - Timeline optimization analysis, 3-week buffer from continuous quality practices

## Quality Metrics (Current)

- **Test Coverage:** 100% maintained
- **Test Count:** 1048 tests
- **Linting:** ruff checks passing
- **Type Safety:** mypy strict mode passing
- **Validation Gate:** `npm run validate` passing

### Tests
- [tests/unit/devices/](../tests/unit/devices/) - Device module unit tests
- [tests/unit/mqtt/](../tests/unit/mqtt/) - MQTT module unit tests  
- [tests/unit/logging/](../tests/unit/logging/) - Logging module unit tests
- [tests/unit/database/](../tests/unit/database/) - Database module unit tests
- [tests/unit/api/](../tests/unit/api/) - API models/routes unit tests
- [tests/unit/tui/](../tests/unit/tui/) - TUI screens unit tests (Week 7)
- [tests/integration/mqtt/](../tests/integration/mqtt/) - MQTT bridge integration tests
- [tests/integration/api/routes/](../tests/integration/api/routes/) - API endpoint integration tests

### Git Configuration
- [.gitattributes](../.gitattributes) - Line ending configuration (LF)
- [.editorconfig](../.editorconfig) - Editor consistency settings
- [.gitignore](../.gitignore) - Git ignore patterns
- `.git/hooks/pre-commit` - Automatic ruff checks on commit

## Development Workflow

```bash
# Setup (first time)
npm run setup          # Create .venv + install dependencies
npm run docker:up      # Start HiveMQ broker

# Activate venv (optional - scripts work without it)
npm run activate       # Shows activation command
source .venv/Scripts/activate  # Then run this

# Daily workflow
npm run lint           # ruff check
npm run lint:fix       # ruff check --fix
npm run format         # ruff format
npm run typecheck      # mypy strict mode
npm run test           # pytest
npm run validate       # Full pipeline (lint + format + typecheck + test)
```

## TUI Usage

TUI launch instructions, keyboard shortcuts, screen descriptions, and troubleshooting are maintained in:

- [tui_developer_guide.md](tui_developer_guide.md)

## Mutation Testing

** Windows users:** mutmut requires WSL2 due to Unix process management (fork, setproctitle).

### Prerequisites
- Windows 10 version 2004+ or Windows 11
- WSL2 installed: `wsl --install` (PowerShell as Administrator)
- Python 3.12+ in WSL (Ubuntu comes with Python 3.12.3)

### Initial Setup (One-Time)

```bash
# In WSL terminal
# Update package lists
sudo apt update

# Create venv in WSL native filesystem (avoids /mnt/d/ permission issues)
cd ~
python3 -m venv smartnest-venv

# Activate venv
source ~/smartnest-venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Daily Usage

**Recommended: Using bash script (works from WSL)**

```bash
# Make script executable (first time only)
chmod +x mutmut.sh

# Full workflow:
./mutmut.sh all          # Run full pipeline (sync + test + report + sync back)
./mutmut.sh analyze      # Categorize mutants by priority
./mutmut.sh list         # List all surviving mutants
./mutmut.sh show <id>    # Show diff for specific mutant
./mutmut.sh apply <id>   # Apply mutant to see actual code

# Individual commands:
./mutmut.sh sync         # Sync project to WSL
./mutmut.sh run          # Run mutation testing only
./mutmut.sh results      # Show summary
./mutmut.sh report       # Generate text report
./mutmut.sh sync-report  # Copy report to Windows
```

**Investigating Mutants:**
1. Run `./mutmut.sh all` - Full pipeline, creates `reports/mutation_report.txt` in Windows
2. Open `reports/mutation_report.txt` to see all results
3. Run `./mutmut.sh analyze` to see categorized high-priority mutants
4. Run `./mutmut.sh show <full-id>` to see diff for specific mutant
5. If needed, `./mutmut.sh apply <full-id>` to see actual code (run `./mutmut.sh sync` to revert)
6. Write test to kill the mutant, then re-run mutation testing

### Troubleshooting

**Error: "node: not found" when running npm scripts**
- npm scripts must be run from **Windows** (PowerShell/Command Prompt), not from inside WSL
- Exit WSL with `exit` command, then run npm scripts from Windows
- Alternative: Use `./mutmut.sh` commands directly in WSL

**Error: "Operation not permitted" when creating venv**
- Don't create venv on Windows filesystem (`/mnt/d/...`)
- Create in WSL home: `cd ~ && python3 -m venv smartnest-venv`

**Error: "Operation not permitted" when running mutmut**
- mutmut needs to create `mutants/` directory which requires filesystem permissions
- Solution: Copy project to WSL native filesystem before running
- Use `rsync` command from Daily Usage section above

**Error: "pip not found"**
- Run: `sudo apt update && sudo apt install python3-pip -y`

**Error: "python3.13 not found" or version mismatch**
- Python 3.12.3 (WSL default) works fine for mutation testing
- Code doesn't use 3.13-specific features

**WSL filesystem is slow**
- Accessing `/mnt/d/` is slower than native WSL filesystem
- This is expected; mutmut performance is still acceptable

```bash
# MQTT
npm run test:mqtt      # Validate MQTT connectivity
npm run docker:health  # Check broker status
npm run docker:logs    # View broker logs
npm run docker:down    # Stop broker
```

### VS Code Tasks
Available via `Ctrl+Shift+P` -> "Tasks: Run Task" or via the `run_task` tool:

| Task Label | npm Script | Purpose |
|---|---|---|
| SmartNest: Start Broker | `docker:up` + `docker:logs` | Start HiveMQ MQTT broker |
| SmartNest: Stop Broker | `docker:down` | Stop the broker |
| SmartNest: MQTT Validation | `test:mqtt` | Validate broker connectivity |
| SmartNest: Broker Health | `docker:health` | Check broker status |
| SmartNest: Lint | `lint` | ruff check |
| SmartNest: Test | `test` | pytest (unit + integration) |
| SmartNest: Test Coverage | `test:cov` | pytest with coverage report |
| SmartNest: Validate | `validate` | Full pipeline (lint + format + typecheck + test:cov) |


## Developer Guides

- [architecture.md](architecture.md) - Comprehensive system architecture with diagrams
- [tui_developer_guide.md](tui_developer_guide.md) - TUI development patterns and testing
- [device_implementation_guide.md](device_implementation_guide.md) - Creating new device types
- [discovery_protocol.md](discovery_protocol.md) - Device discovery specification
- [mutation_testing.md](mutation_testing.md) - Mutation testing with mutmut, understanding results, known limitations, and mutation score calculation

## Code Quality Standards

Primary quality configuration is maintained in:

- [pyproject.toml](../pyproject.toml)
- [.gitattributes](../.gitattributes)
- [.editorconfig](../.editorconfig)

## Quick Reference

| Topic | File |
|-------|------|
| Getting started | [README.md](../README.md) |
| System architecture | [architecture.md](architecture.md) |
| TUI development | [tui_developer_guide.md](tui_developer_guide.md) |
| Task commands | [package.json](../package.json) |
| Linting/formatting | [pyproject.toml](../pyproject.toml) |
| Line endings | [.gitattributes](../.gitattributes) |
| Editor config | [.editorconfig](../.editorconfig) |
| Mutation testing | [mutation_testing.md](mutation_testing.md) |

## MQTT Broker Logging

**Development (verbose - current):**
- Shows connections, disconnections, subscriptions
- Enabled by default in [docker-compose.yml](../docker-compose.yml)

**Production (minimal):**
- Only errors and warnings
- To switch: Edit [docker-compose.yml](../docker-compose.yml), change:
  ```yaml
  - ./config/mqtt/logback-dev.xml:/opt/hivemq/conf/logback.xml:ro
  ```
  to:
  ```yaml
  - ./config/mqtt/logback-prod.xml:/opt/hivemq/conf/logback.xml:ro
  ```
- Then restart: `npm run docker:down && npm run docker:up`

---

**Last Updated:** March 28, 2026 (Week 11 DRY implementation update)  
**Project:** SmartNest Home Automation Management System
