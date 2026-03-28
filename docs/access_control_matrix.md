# SmartNest Access Control Matrix

Canonical authorization reference for API routes and role-based access behavior.

## Roles

- admin: full access
- user: operational read/write access
- readonly: authenticated read-only access
- anonymous: unauthenticated caller

## Route Matrix

| Route | Method | Dependency Guard | admin | user | readonly | anonymous |
|---|---|---|---|---|---|---|
| /api/auth/login | POST | none | allow | allow | allow | allow |
| /api/auth/me | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/devices | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/devices/count | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/devices/{device_id} | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/devices | POST | require_role(admin,user) | allow | allow | deny 403 | deny 401 |
| /api/devices/{device_id} | PUT | require_role(admin,user) | allow | allow | deny 403 | deny 401 |
| /api/devices/{device_id} | DELETE | require_role(admin,user) | allow | allow | deny 403 | deny 401 |
| /api/devices/{device_id}/status | PATCH | require_role(admin,user) | allow | allow | deny 403 | deny 401 |
| /api/sensors/latest | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/sensors/stats/24h | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/reports/dashboard-summary | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/users | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/users/{user_id} | GET | get_current_user | allow | allow | allow | deny 401 |
| /api/users | POST | require_role(admin) | allow | deny 403 | deny 403 | deny 401 |
| /api/users/{user_id} | DELETE | require_role(admin) | allow | deny 403 | deny 403 | deny 401 |

## Verification Checklist

- Assert allow and deny behavior for every guarded endpoint category.
- Assert 401 for anonymous requests and 403 for authenticated-role mismatch.
- Include expired and invalid token scenarios for auth-protected routes.
- Keep this matrix synchronized when adding or changing route guards.

## Source of Truth

- [backend/api/deps.py](../backend/api/deps.py)
- [backend/api/routes/auth.py](../backend/api/routes/auth.py)
- [backend/api/routes/devices.py](../backend/api/routes/devices.py)
- [backend/api/routes/sensors.py](../backend/api/routes/sensors.py)
- [backend/api/routes/reports.py](../backend/api/routes/reports.py)
- [backend/api/routes/users.py](../backend/api/routes/users.py)
