# SmartNest Development Workspace

This directory contains the SmartNest Home Automation Management System project.

## Quick Links

### SmartNest Project
- [Documentation Index](docs/index.md) - SmartNest files, commands, and configuration reference

## Project Status

**Current Phase:** Phase 5 - Security & Final Integration (Week 11)  
**Completed:** TUI functional completion
**Timeline:** 12 weeks (Weeks 4-15, Jan 26 - Apr 13, 2026)  
**Progress:** 124.25/110 hours tracked

## Project Structure (Planned)

```
SmartNest/
├── backend/                # FastAPI backend service
│   ├── api/               # REST API endpoints
│   ├── models/            # Data models (Pydantic)
│   ├── database/          # SQLite database layer
│   └── mqtt_bridge/       # MQTT-to-API bridge
├── tui/                   # Terminal user interface
│   ├── screens/           # TUI screen implementations
│   └── components/        # Reusable UI components
├── devices/               # Mock IoT device implementations
│   ├── lights/            # Smart light devices
│   ├── sensors/           # Temperature, motion sensors
│   └── switches/          # Smart switches
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests (planned Week 12)
├── config/                # Configuration files
│   ├── mqtt/             # MQTT broker config
│   └── database/         # Database schemas
├── docs/                  # Additional documentation
└── docker/                # Docker configurations
```

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
npm run test:mqtt      # Verify connectivity

# Development
npm run validate       # Run all checks (lint + format + typecheck + test)
npm run docker:down    # Stop broker
```

**For detailed commands, configuration, and workflow →** See [docs/index.md](docs/index.md)

## Key Features

1. **Device Management**
   - Register and control MQTT-compatible IoT devices
   - Support for lights, sensors, switches, and more
   - Real-time status monitoring

2. **Terminal User Interface**
   - Rich text-based interface with live updates
   - Dashboard with system overview
   - Device list with filtering and search
   - Device detail screens with full control
   - Sensor data visualization

3. **Automation (Future)**
   - Time-based rules
   - Sensor-triggered actions
   - Complex automation workflows

4. **Security**
   - Multi-user authentication
   - Role-based access control (admin, user, readonly)
   - MQTT authentication and TLS
   - Audit logging

5. **Reports**
   - Daily device health reports
   - Sensor data summaries
   - System performance metrics
   - Security audit logs

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐      ┌─────────────────┐
│   TUI Client    │────▶│  FastAPI Backend │────▶│  SQLite Database│
│  (Python Rich)  │     │   (REST API)     │      │   (State Store) │
└─────────────────┘     └──────────────────┘      └─────────────────┘
         │                       │
         └───────────────────────┴────────▶┌──────────────────┐
                                            │  MQTT Broker     │
                                            │  (HiveMQ CE)     │
                                            └──────────────────┘
                                                     │
                                    ┌────────────────┴────────────────┐
                              ┌─────▼───────┐                  ┌──────▼─────┐
                              │ Mock Devices│                  │Real Devices│
                              │  (Python)   │                  │ (ESP32/RPi)│
                              └─────────────┘                  └────────────┘
```

**For detailed architecture documentation →** See [docs/architecture.md](docs/architecture.md) for comprehensive system diagrams, data flow, component relationships, and MQTT topic structure.

## MQTT Topic Structure

- Commands: `smartnest/device/{device_id}/command`
- State Updates: `smartnest/device/{device_id}/state`
- Sensor Data: `smartnest/sensor/{device_id}/data`
- Device Discovery: `smartnest/discovery/announce`
- System Events: `smartnest/system/event`

## Contributing

This is a capstone project for SDEV435. For questions or issues, contact Krystian Spiewak.

## License

Educational project for Champlain College SDEV435 course.

## Resources

### Internal Documentation
- [SmartNest Documentation Index](docs/index.md) - Complete file reference and command guide
- [Device Implementation Guide](docs/device_implementation_guide.md) - How to create new device types
- [Discovery Protocol Specification](docs/discovery_protocol.md) - MQTT device discovery protocol

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
