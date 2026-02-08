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

### Tests
- [tests/unit/mqtt/](../tests/unit/mqtt/) - Unit tests for MQTT module (82 tests)
- [tests/unit/logging/](../tests/unit/logging/) - Unit tests for logging module (20 tests)
- [tests/unit/test_config.py](../tests/unit/test_config.py) - Unit tests for AppSettings (19 tests)
- [tests/integration/](../tests/integration/) - Integration tests against live broker (4 tests)

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

# Mutation Testing (Week 6+)
npm run test:mutation          # mutmut mutation testing
npm run test:mutation:results  # View mutmut results
npm run test:mutation:html     # Generate HTML report

# MQTT
npm run test:mqtt      # Validate MQTT connectivity
npm run docker:health  # Check broker status
npm run docker:logs    # View broker logs
npm run docker:down    # Stop broker
```

### VSCode Tasks
Available via `Ctrl+Shift+P` → "Tasks: Run Task":
- SmartNest: Start Broker
- SmartNest: Stop Broker
- SmartNest: MQTT Validation
- SmartNest: Lint
- SmartNest: Test

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
├── backend/           # Backend service
│   ├── config.py     # Application settings (pydantic-settings)
│   ├── mqtt/         # MQTT client module
│   │   ├── topics.py # Topic builder
│   │   ├── config.py # Connection configuration (Pydantic)
│   │   └── client.py # SmartNestMQTTClient
│   ├── logging/      # Structured logging (structlog)
│   │   ├── config.py # configure_logging, get_logger
│   │   ├── catalog.py# Message catalog (MessageCode enum)
│   │   └── utils.py  # Correlation tracking, log_with_code
│   └── __init__.py
├── tests/            # Test suite (125 tests, 100% coverage)
│   ├── unit/mqtt/    # MQTT unit tests
│   ├── unit/logging/ # Logging unit tests
│   ├── unit/test_config.py # AppSettings tests
│   └── integration/  # Integration tests
├── config/           # Configuration files
├── docs/             # Documentation (this directory)
└── scripts/          # Utility scripts
```

## Quick Reference

| Topic | File |
|-------|------|
| Getting started | [README.md](../README.md) |
| Task commands | [package.json](../package.json) |
| Linting/formatting | [pyproject.toml](../pyproject.toml) |
| Line endings | [.gitattributes](../.gitattributes) |
| Editor config | [.editorconfig](../.editorconfig) |

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

**Last Updated:** February 9, 2026  
**Project:** SmartNest Home Automation Management System
