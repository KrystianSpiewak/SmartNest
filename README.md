# SmartNest Development Workspace

This directory contains the SmartNest Home Automation Management System project.

## Quick Links

### SmartNest Project
- [Documentation Index](docs/index.md) - SmartNest files, commands, and configuration reference

## Project Status

**Current Phase:** Security and final integration  
**Completed:** TUI functional completion  
**Progress:** Active development

## Technology Stack

- **Backend:** Python 3.13+, FastAPI, SQLite, Paho MQTT, Pydantic
- **TUI:** Python Rich, Prompt Toolkit
- **Infrastructure:** HiveMQ CE (Docker), npm (task runner), ruff, mypy, pytest

## Quality Metrics

- **Test Coverage:** 100% maintained
- **Test Suite:** 1040 tests
- **Linting:** ruff checks passing
- **Type Checking:** mypy strict mode passing

## Quick Start

```bash
# First-time setup
npm run setup          # Create venv + install dependencies
npm run docker:up      # Start MQTT broker
npm run validate       # Run all checks (lint + format + typecheck + test)
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
