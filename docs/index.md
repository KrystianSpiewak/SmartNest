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

### Scripts
- [scripts/mqtt_validation_test.py](../scripts/mqtt_validation_test.py) - Broker connectivity test

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

## Project Structure (Planned)

```
SmartNest/
├── backend/           # FastAPI REST API service
├── tui/              # Terminal user interface
├── devices/          # Mock IoT devices
├── tests/            # Test suite
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

---

**Last Updated:** February 7, 2026  
**Project:** SmartNest Home Automation Management System
