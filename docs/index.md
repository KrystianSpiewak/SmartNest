# SmartNest Documentation

Quick reference for SmartNest project documentation and configuration.

## SmartNest Project Files

### Core Configuration
- [README.md](../README.md) - Project overview, setup, and getting started
- [package.json](../package.json) - npm task runner scripts
- [pyproject.toml](../pyproject.toml) - ruff, pytest, mypy configuration
- [docker-compose.yml](../docker-compose.yml) - MQTT broker and optional backend full-stack profile
- [Dockerfile](../Dockerfile) - Backend API container image definition

### Requirements
- [requirements/base.txt](../requirements/base.txt) - Production dependencies
- [requirements/dev.txt](../requirements/dev.txt) - Development dependencies

### Configuration
- [config/mqtt/config.xml](../config/mqtt/config.xml) - MQTT broker configuration
- [config/mqtt/logback-dev.xml](../config/mqtt/logback-dev.xml) - Verbose logging (development, current)
- [config/mqtt/logback-prod.xml](../config/mqtt/logback-prod.xml) - Minimal logging (production)

### Scripts
- [scripts/mqtt_validation_test.py](../scripts/mqtt_validation_test.py) - Broker connectivity test
- [scripts/wait_for_api_health.py](../scripts/wait_for_api_health.py) - API health polling helper used by smoke scripts

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

### Backend Devices Module
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
- [access_control_matrix.md](access_control_matrix.md) - Canonical route-role access matrix and verification checklist
- [validation_checklist.md](validation_checklist.md) - Reusable validation quality gates and command set

Reusable Functionality Canonical Reference:
- [architecture.md](architecture.md#shared-components) - Single source of truth for shared runtime components

Documentation Standards References:
- [access_control_matrix.md](access_control_matrix.md) - Canonical endpoint authorization policy reference
- [validation_checklist.md](validation_checklist.md) - Canonical validation command/checklist reference

### Project Planning
- [timeline_optimizations.md](timeline_optimizations.md) - Timeline optimization analysis, 3-week buffer from continuous quality practices

## Quality Metrics (Current)

- **Test Coverage:** 100% maintained
- **Test Count:** 1079 tests collected (latest run: 1075 passed, 4 skipped)
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

## Getting Started

Use the README as the single source of truth for first-run and smoke-test workflows:

- [README.md](../README.md) - Quick Start (setup, smoke run, TUI verification, teardown)
- [validation_checklist.md](validation_checklist.md) - Reusable quality-gate command set

For TUI implementation details and keyboard behavior, use:

- [tui_developer_guide.md](tui_developer_guide.md)

For mutation testing setup and analysis, use:

- [mutation_testing.md](mutation_testing.md)

## Command Reference

Run commands from the SmartNest root directory.

| Goal | Command |
|---|---|
| First-time setup | `npm run setup` |
| Rebuild demo .env values | `npm run setup:env -- --force` |
| Full API+TUI smoke run | `npm run smoke:tui` |
| Smoke prep without launching TUI | `npm run smoke:tui:prep` |
| Start full stack manually | `npm run docker:up:stack` |
| Clean full-stack teardown | `npm run docker:down:stack` |
| Full quality gate | `npm run validate` |

If npm is unavailable, see the direct Python and Docker workflow in [README.md](../README.md#running-without-npm).

## VS Code Tasks

Run from `Tasks: Run Task` in VS Code:

| Task Label | npm Script | Purpose |
|---|---|---|
| SmartNest: Start Broker | `docker:up` + `docker:logs` | Start HiveMQ MQTT broker |
| SmartNest: Stop Broker | `docker:down` | Stop broker profile |
| SmartNest: MQTT Validation | `test:mqtt` | Validate broker connectivity |
| SmartNest: Broker Health | `docker:health` | Check broker status |
| SmartNest: Lint | `lint` | Run ruff checks |
| SmartNest: Test | `test` | Run unit + integration tests |
| SmartNest: Test Coverage | `test:cov` | Run tests with coverage report |
| SmartNest: Validate | `validate` | Run lint + format + typecheck + test:cov |


## Code Quality Standards

Primary quality configuration is maintained in:

- [pyproject.toml](../pyproject.toml)
- [.gitattributes](../.gitattributes)
- [.editorconfig](../.editorconfig)

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

**Last Updated:** April 18, 2026  
**Project:** SmartNest Home Automation Management System
