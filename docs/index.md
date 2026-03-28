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

### Project Planning
- [timeline_optimizations.md](timeline_optimizations.md) - Timeline optimization analysis, 3-week buffer from continuous quality practices

## Quality Metrics (Current)

- **Test Coverage:** 100% maintained
- **Test Count:** 1033 tests - all passing
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

### Launching the TUI

```bash
# Start backend API (required)
npm run dev           # Terminal 1: FastAPI server on http://localhost:8000

# Start MQTT broker (required)
npm run docker:up     # HiveMQ CE on localhost:1883

# Launch TUI (Terminal 2)
npm run tui           # Start SmartNest Terminal UI
```

### Keyboard Shortcuts

**Global Navigation:**
- `F1` - Dashboard (system overview)
- `F2` - Settings (user management)
- `F3` - Device List (all devices)
- `F4` - Sensor View (sensor data & stats)
- `Q` - Quit application
- `Ctrl+C` - Emergency exit

**Device List (F3):**
- `L` - Filter by Lights
- `S` - Filter by Sensors
- `W` - Filter by Switches
- `A` - Show All devices
- `/` - Search by name/location
- `Enter` - Open device detail

**Device Detail (Select from list):**
- `P` - Toggle power (lights)
- `+` / `-` - Adjust brightness ±10% (lights)
- `↑` / `↓` - Adjust color temp ±500K (lights)
- `R` - Refresh device state
- `Esc` - Back to device list

**Sensor View (F4):**
- `R` - Refresh sensor data
- `E` - Export to CSV (future)

**Settings (F2):**
- View user list with roles
- Future: Add/remove users

### Screen Descriptions

**Dashboard (F1):**
- System overview with live MQTT status
- Device count and active sensors
- Quick health indicators
- Auto-refreshes at 4 FPS (250ms)

**Device List (F3):**
- Tabular listing of all devices
- Filter by type (lights, sensors, switches)
- Search by name or location
- Color-coded status (online/offline)

**Device Detail (Select device):**
- Comprehensive device information
- Real-time state display
- Interactive controls for smart lights
- Command feedback

**Sensor View (F4):**
- Latest readings from all sensors
- 24-hour statistics (min, max, average)
- Timestamp tracking
- Auto-refresh

**Settings (F2):**
- User management interface
- Role display (admin, user, readonly)
- Active status indicators
- Future: User creation and deletion

### Troubleshooting TUI Issues

**"API Error: Unable to fetch devices"**
- Check backend is running: `npm run dev`
- Verify API reachable: `curl http://localhost:8000/api/devices`

**"MQTT: OFFLINE" status in dashboard**
- Check broker is running: `npm run docker:health`
- Restart broker: `npm run docker:down && npm run docker:up`

**TUI not updating in real-time**
- Verify MQTT connection (check logs in terminal where `npm run tui` ran)
- Ensure devices are publishing state updates
- Restart TUI: `Ctrl+C` then `npm run tui`

**Display corruption or formatting issues / stale or duplicated output**
- Use **Windows Terminal** or **PowerShell** for best behavior; Git Bash/mintty often shows appended or duplicated Live output.
- Clear terminal between runs: `clear` (bash) or `cls` (PowerShell) to avoid accumulated “Shutting down…” and log lines.
- Resize terminal to minimum 120x30 characters.
- See [TUI Developer Guide – Terminal behavior](tui_developer_guide.md#7-terminal-behavior-and-why-automated-runs-look-different) for why automated runs don’t show the same issues.

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
All tasks are defined in the **root** `.vscode/tasks.json` (not in SmartNest/.vscode/).

Available via `Ctrl+Shift+P` → "Tasks: Run Task" or via the `run_task` tool:

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

### Ruff Configuration
Configured in [pyproject.toml](../pyproject.toml):
- **Security:** Bandit checks (S prefix)
- **Complexity:** McCabe complexity limit (C90)
- **Best practices:** Pylint, performance, async patterns
- **Line length:** 100 characters
- **Type checking:** mypy strict mode

### Git Hooks
Pre-commit hook automatically runs:
1. `ruff check . --fix` - Auto-fix issues
2. `ruff format .` - Format code
3. Blocks commit if checks fail

Bypass (not recommended): `git commit --no-verify`

### Line Endings
- All text files use **LF** (Unix-style)
- Enforced by `.gitattributes`
- Configured in `.editorconfig`
- Cross-platform compatible

## Project Structure

```
SmartNest/
├── backend/                # Backend service
│   ├── config.py          # Application settings (pydantic-settings)
│   ├── app.py             # FastAPI application
│   ├── main.py            # uvicorn entry point
│   ├── api/               # REST API layer
│   │   ├── routes/        # API endpoints (devices, users, sensors)
│   │   ├── models/        # Pydantic request/response models
│   │   └── mqtt_bridge.py # MQTT-to-Database bridge
│   ├── database/          # Data access layer
│   │   ├── connection.py  # Async connection manager
│   │   ├── schema.py      # SQLite schema
│   │   └── repositories/  # Repository pattern (devices, users)
│   ├── mqtt/              # MQTT client module
│   │   ├── topics.py      # Topic builder
│   │   ├── config.py      # Connection configuration (Pydantic)
│   │   ├── client.py      # SmartNestMQTTClient
│   │   └── discovery.py   # Device discovery protocol
│   ├── logging/           # Structured logging (structlog)
│   │   ├── config.py      # configure_logging, get_logger
│   │   ├── catalog.py     # Message catalog (MessageCode enum)
│   │   └── utils.py       # Correlation tracking, log_with_code
│   ├── tui/               # Terminal User Interface
│   │   ├── app.py         # Main TUI application (SmartNestTUI)
│   │   ├── __main__.py    # TUI entry point
│   │   └── screens/       # Screen implementations
│   │       ├── dashboard.py      # System overview with MQTT live updates
│   │       ├── device_list.py    # Device listing with filtering
│   │       ├── device_detail.py  # Device controls
│   │       ├── sensor_view.py    # Sensor data & 24h stats
│   │       └── settings.py       # User management
│   ├── devices/           # Mock IoT devices
│   │   ├── base.py        # BaseDevice abstract class
│   │   ├── mock_light.py  # Smart light mock
│   │   ├── mock_temperature_sensor.py
│   │   └── mock_motion_sensor.py
│   └── auth/              # Authentication module
│       └── password.py    # Bcrypt password hashing
├── tests/                 # Test suite (743 tests: 721 unit + 22 integration, 100% coverage)
│   ├── unit/              # Unit tests (mocked dependencies)
│   │   ├── tui/           # TUI screen tests
│   │   ├── api/           # API routes and models tests
│   │   ├── database/      # Database repository tests
│   │   ├── mqtt/          # MQTT module tests
│   │   ├── devices/       # Device module tests
│   │   └── logging/       # Logging tests
│   └── integration/       # Integration tests (real dependencies)
│       ├── api/routes/    # API endpoint integration tests
│       └── mqtt/          # MQTT bridge integration tests
├── config/                # Configuration files
│   └── mqtt/              # MQTT broker config (HiveMQ)
├── docs/                  # Documentation (this directory)
├── scripts/               # Utility scripts
└── data/                  # Runtime data (SQLite database, logs)
```

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

**Last Updated:** February 26, 2026 (Post-TUI Implementation - Week 7)  
**Project:** SmartNest Home Automation Management System
