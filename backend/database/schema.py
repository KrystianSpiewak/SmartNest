"""Database schema DDL for SmartNest.

This module defines the SQLite database schema for the SmartNest application.
Tables: devices, sensor_readings, device_state, users.

Schema Reference:
- devices: Core device registry
- sensor_readings: Time-series sensor data (temperature, motion events)
- device_state: Current device state (brightness, color_temp, power)
- users: Authentication and authorization
"""

SCHEMA_DDL = """
-- devices table: Core device registry
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    friendly_name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    mqtt_topic TEXT NOT NULL UNIQUE,
    manufacturer TEXT,
    model TEXT,
    capabilities TEXT NOT NULL,  -- JSON array of capabilities
    status TEXT NOT NULL DEFAULT 'online',  -- online, offline, error
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen_at);

-- sensor_readings table: Time-series sensor data
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL,  -- temperature, motion, humidity, etc.
    value REAL NOT NULL,
    unit TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_device ON sensor_readings(device_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_type ON sensor_readings(sensor_type);

-- device_state table: Current device state
CREATE TABLE IF NOT EXISTS device_state (
    device_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,  -- JSON object with device-specific state
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_state_updated ON device_state(updated_at);

-- users table: Authentication and authorization
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',  -- admin, user, readonly
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
"""
