# SmartNest Development Workspace

This directory contains the SmartNest Home Automation Management System project.

## Quick Links

### SmartNest Project
- [Documentation Index](docs/index.md) - SmartNest files, commands, and configuration reference

## Project Status

**Current Phase:** Final submission and delivery readiness  
**Completed:** Deployment integration, security hardening, and e2e baseline expansion  
**Progress:** Validation and submission packaging

## Technology Stack

- **Backend:** Python 3.13+, FastAPI, SQLite, Paho MQTT, Pydantic
- **TUI:** Python Rich, Prompt Toolkit
- **Infrastructure:** HiveMQ CE (Docker), npm (task runner), ruff, mypy, pytest

## Quality Metrics

- **Test Coverage:** 100% maintained
- **Test Suite:** 1079 tests collected (latest run: 1075 passed, 4 skipped)
- **Linting:** ruff checks passing
- **Type Checking:** mypy strict mode passing

## Prerequisites

- Git
- Python 3.13+
- Node.js and npm (recommended task runner)
- Docker Desktop (Linux containers mode)

## Quick Start

Use this flow to verify the full local app, including API and TUI, with minimal commands.

### 1) Setup environment

```bash
# Create virtual environment, install dependencies, and bootstrap .env for demo use
npm run setup
```

The setup command now creates `.env` from `.env.example` and fills required demo values automatically:
- `SMARTNEST_ADMIN_USERNAME`
- `SMARTNEST_ADMIN_EMAIL`
- `SMARTNEST_ADMIN_PASSWORD`
- `SMARTNEST_JWT_SECRET`

It prints demo login credentials after setup finishes.

To regenerate demo credentials in an existing `.env`:

```bash
npm run setup:env -- --force
```

Note: admin values are used only when the users table is empty.

### 2) Recommended smoke run

```bash
npm run smoke:tui
```

This command starts the stack, waits for API health, seeds mock devices, opens TUI, and tears down the stack when TUI exits.

Expected result:
- TUI login prompt appears.
- Dashboard renders after login.
- Keys `1` to `5` switch screens.
- Key `q` exits cleanly.

If smoke run is interrupted, clean up with:

```bash
npm run docker:down:stack
```

### 3) Manual run (optional)

If you want full control over each step:

```bash
npm run smoke:tui:prep
npm run tui
```

Manual API health check:

```bash
curl -sS http://127.0.0.1:8000/health
```

PowerShell alternative:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 4) Quality gate (optional)

```bash
npm run validate
```

## Running Without npm

npm in this project is a task runner for Python and Docker commands. If Node.js is unavailable, you can run the underlying commands directly.

```bash
python -m venv --clear .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements/dev.txt
.venv/Scripts/python.exe scripts/setup_demo_env.py
docker compose --profile fullstack up -d
.venv/Scripts/python.exe scripts/wait_for_api_health.py
.venv/Scripts/python.exe -m backend.devices.runner --seed-only
.venv/Scripts/python.exe -B -m backend.tui
docker compose --profile fullstack down
```

## Documentation

- Full operational reference: [docs/index.md](docs/index.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- TUI development: [docs/tui_developer_guide.md](docs/tui_developer_guide.md)
- Mutation testing: [docs/mutation_testing.md](docs/mutation_testing.md)

## Contributing

For questions or issues, contact Krystian Spiewak.

## License

Private project.

## Resources

### Internal Documentation
- [SmartNest Documentation Index](docs/index.md)
- [Device Implementation Guide](docs/device_implementation_guide.md)
- [Discovery Protocol Specification](docs/discovery_protocol.md)

### MQTT & IoT
- [MQTT Protocol](https://mqtt.org/)
- [Paho MQTT Python](https://github.com/eclipse/paho.mqtt.python)
- [HiveMQ Documentation](https://www.hivemq.com/docs/)

### Python & FastAPI
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Rich Terminal Library](https://rich.readthedocs.io/)
- [Pydantic](https://docs.pydantic.dev/)

### Testing & Quality
- [pytest Documentation](https://docs.pytest.org/)
- [Ruff Linter & Formatter](https://docs.astral.sh/ruff/)
- [mypy Type Checker](https://mypy.readthedocs.io/)
- [mutmut Mutation Testing](https://mutmut.readthedocs.io/) (requires WSL on Windows)

---

**Developer:** Krystian Spiewak  
**Course:** SDEV435 - Capstone Project  
**Term:** Spring 2026  
**Institution:** Champlain College
