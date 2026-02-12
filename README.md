# SmartNest Development Workspace

This directory contains the SmartNest Home Automation Management System project.

## Quick Links

### SmartNest Project
- [Documentation Index](docs/index.md) - SmartNest files, commands, and configuration reference

## Project Status

**Current Phase:** Phase 4 - Terminal User Interface (Week 7+)  
**Completed:** Backend API Complete (Week 6, Feb 11-12)  
**Timeline:** 12 weeks (Weeks 4-15, Jan 26 - Apr 13, 2026)  
**Progress:** 69.5/110 hours (63%), 10 days ahead of schedule  

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
│   └── e2e/              # End-to-end tests
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

- **Test Coverage:** 100% (1178 statements, 146 branches)
- **Test Suite:** 546 tests (534 unit + 12 integration)
- **Mutation Score:** 97.5% (1245/1277 mutants killed)
- **Linting:** ruff (100% passing, 72 files)
- **Type Checking:** mypy strict mode (0 errors)
- **Test Performance:** ~44 seconds full suite

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

## Development Workflow to sync, test, and view results

### Phase 1: Foundation (Week 4) ✅
- [x] HiveMQ broker running (Docker)
- [x] MQTT protocol learning complete
- [x] Dev toolchain configured (npm, ruff, mypy, pytest)
- [x] Python MQTT client implemented (SmartNestMQTTClient, TopicBuilder, MQTTConfig)
- [x] Structured logging infrastructure (structlog with message catalog)
- [x] Comprehensive test suite (83 tests, 100% coverage)

### Phase 2: Device Ecosystem (Week 5) ✅
- [x] Comprehensive mock devices (MockSmartLight, MockTemperatureSensor, MockMotionSensor)
- [x] Device discovery protocol (DiscoveryConsumer)
- [x] State synchronization
- [x] Error handling and reconnection
- [x] Expanded test suite (369 tests, 100% coverage, 97.4% mutation score)

### Phase 3: Backend API (Week 6) ✅
- [x] SQLite database schema (4 tables: devices, sensor_readings, device_state, users)
- [x] Async connection manager (aiosqlite)
- [x] FastAPI application with modern lifespan
- [x] Pydantic models (DeviceCreate, DeviceUpdate, DeviceResponse, UserCreate, UserResponse)
- [x] Repository pattern (DeviceRepository, UserRepository)
- [x] Device CRUD API (7 REST endpoints)
- [x] MQTT-to-Database bridge (MQTTBridge service)
- [x] Authentication foundation (bcrypt password hashing)
- [x] 546 tests, 100% coverage, 97.5% mutation score

### Phase 4: User Interface
- [ ] TUI framework setup
- [ ] Dashboard screen
- [ ] Device list and detail screens
- [ ] Real-time updates

### Phase 5: Security (Week 11, 0.5 weeks) - Optimized
- [ ] Password hashing (bcrypt, auth stubs from Phase 3)
- [ ] JWT authentication with refresh tokens
- [ ] Role-based access control (admin, user, readonly)
- [ ] MQTT authentication and TLS
- [ ] Security testing (parallel with implementation)

### Phase 6: Testing (Weeks 11.5-12, 0.5 weeks) - Optimized
- [x] Unit test coverage 100% (maintained continuously)
- [x] Integration tests (4 tests, maintained continuously)
- [x] Mutation testing 97.4% (maintained continuously)
- [ ] End-to-end tests
- [ ] Load testing

### Phase 7: Deployment (Weeks 12.5-14, 1.5 weeks) - Optimized
- [ ] Docker containerization (Dockerfile in Phase 3)
- [ ] Cloud hosting setup (DigitalOcean/AWS)
- [ ] TLS configuration (Let's Encrypt)
- [ ] Monitoring and logging infrastructure

### Phase 8: Documentation (Weeks 14.5-15, 0.5 weeks) - Optimized
- [x] Documentation maintained continuously
- [ ] API auto-documentation (FastAPI OpenAPI/Swagger)
- [ ] User guide finalization
- [ ] Deployment runbook
- [ ] Troubleshooting guide

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
