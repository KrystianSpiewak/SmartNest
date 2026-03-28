# SmartNest Reusable Validation Checklist

Canonical checklist and command set for incremental validation and final QA.

## Quality Gates

All of the following must pass before merging feature work:

1. Lint passes.
2. Formatting check passes.
3. Type checking passes.
4. Tests pass with coverage requirements maintained.
5. No new errors in application logs.

## Reusable Command Set

Run from SmartNest project root.

```bash
npm run lint
npm run format
npm run typecheck
npm run test
npm run test:cov
npm run validate
```

## Security Verification Set

```bash
.venv/Scripts/python -m pytest tests/integration/auth/test_auth_flow.py -q
```

## API Route Verification Set

```bash
.venv/Scripts/python -m pytest tests/integration/api/routes -q
```

## TUI Verification Set

```bash
.venv/Scripts/python -m pytest tests/unit/tui/test_app.py -q
```

## MQTT Integration Verification Set

```bash
.venv/Scripts/python -m pytest tests/integration/test_mqtt_broker.py -q -rs
```

Note: The broker integration file has environment-dependent skips when localhost:1883 is unavailable.

## Manual Smoke Checklist

- Start broker and backend services.
- Verify login succeeds with valid credentials.
- Verify protected read endpoint returns 401 when unauthenticated.
- Verify readonly role is denied on write endpoint (403).
- Verify TUI starts and dashboard renders.

## Maintenance Rule

When a weekly plan or report needs validation commands, link to this file instead of duplicating command blocks.
