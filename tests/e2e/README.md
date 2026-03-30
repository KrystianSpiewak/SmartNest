# SmartNest E2E Tests

This folder contains end-to-end baseline test scenarios.

## Layout

- auth/: authentication and token lifecycle flows
- workflows/: cross-domain user workflows (auth + API + persistence)
- conftest.py: shared fixtures and environment setup

## Baseline Scenarios

1. Login and authenticated read
2. Authorized write success
3. Unauthorized write denied
4. Anonymous access denied

## Run

```bash
cd SmartNest
.venv/Scripts/python -m pytest tests/e2e -q
```
