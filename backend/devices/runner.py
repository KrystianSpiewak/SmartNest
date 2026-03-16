"""Mock device state simulation runner for SmartNest.

By default this runner picks one device for each supported mock category from
the database and simulates their MQTT activity in one command.

Supported device types:
- light / smart_light
- temperature_sensor
- motion_sensor

Usage::

    python -m backend.devices.runner
"""

from __future__ import annotations

import argparse
import os
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

import httpx
from dotenv import load_dotenv

from backend.devices.mock_light import MockSmartLight
from backend.devices.mock_motion_sensor import MockMotionSensor
from backend.devices.mock_temperature_sensor import MockTemperatureSensor
from backend.logging import configure_logging, get_logger
from backend.mqtt.config import get_mqtt_config
from backend.mqtt.topics import TopicBuilder

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

_DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_WARMUP_SECONDS = 10.0
_DEFAULT_STATE_CHANGES = 10
_DEFAULT_MIN_DELAY_SECONDS = 3.0
_DEFAULT_MAX_DELAY_SECONDS = 5.0

_LIGHT_TYPES = {"light", "smart_light"}
_TEMP_TYPES = {"temperature_sensor"}
_MOTION_TYPES = {"motion_sensor"}
_SUPPORTED_TYPES = _LIGHT_TYPES | _TEMP_TYPES | _MOTION_TYPES

DeviceKind = Literal["light", "temperature_sensor", "motion_sensor"]


class DeviceRuntime(Protocol):
    """Structural contract for runtime mock device implementations."""

    @property
    def client(self) -> Any: ...

    def start(self, timeout: float = 10.0) -> bool: ...

    def stop(self, reason: str = "shutdown") -> None: ...


@dataclass
class SimulatedDevice:
    """Runtime wrapper for a simulated device instance."""

    kind: DeviceKind
    device_id: str
    name: str
    runtime: DeviceRuntime


@dataclass(frozen=True)
class RunnerConfig:
    """Configuration for mock device simulation runs."""

    api_base_url: str
    username: str
    password: str
    state_changes_per_device: int
    warmup_seconds: float
    min_delay_seconds: float
    max_delay_seconds: float
    simulate_all_supported: bool = False
    seed_supported: bool = False
    seed_only: bool = False


class DeviceSimulationRunner:
    """Run a timed simulation of mock light devices."""

    def __init__(
        self,
        config: RunnerConfig,
        *,
        rng: random.Random | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._config = config
        self._rng = rng or random.Random()
        self._sleep = sleeper or time.sleep
        self._http = httpx.Client(base_url=config.api_base_url, timeout=10.0)
        self._devices: list[SimulatedDevice] = []

    def run(self) -> int:
        """Execute the full simulation lifecycle."""
        if not self._authenticate():
            return 1

        api_devices = self._fetch_devices_from_api()
        if self._config.seed_supported:
            self._seed_missing_supported_devices(api_devices)
            api_devices = self._fetch_devices_from_api()

        if self._config.seed_only:
            self._http.close()
            return 0

        supported_devices = self._build_supported_devices(api_devices)
        self._devices = self._select_devices_for_simulation(supported_devices)

        if not self._devices:
            logger.warning("simulation_no_supported_devices")
            self._http.close()
            return 0

        self._set_all_status("offline")

        logger.info(
            "simulation_warmup_started",
            seconds=self._config.warmup_seconds,
            device_count=len(self._devices),
        )
        self._sleep(self._config.warmup_seconds)

        try:
            self._start_devices()
            self._set_all_status("online")
            self._run_state_changes()
        finally:
            self._set_all_status("offline")
            self._stop_devices()
            self._http.close()

        logger.info("simulation_completed", device_count=len(self._devices))
        return 0

    def _authenticate(self) -> bool:
        """Authenticate with backend API and set bearer token header."""
        try:
            response = self._http.post(
                "/api/auth/login",
                json={
                    "username": self._config.username,
                    "password": self._config.password,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("simulation_auth_failed", username=self._config.username)
            return False

        token = str(response.json().get("access_token", "")).strip()
        if not token:
            logger.error("simulation_auth_missing_token")
            return False

        self._http.headers["Authorization"] = f"Bearer {token}"
        logger.info("simulation_auth_success", username=self._config.username)
        return True

    def _fetch_devices_from_api(self) -> list[dict[str, Any]]:
        """Fetch all devices from API with pagination."""
        devices: list[dict[str, Any]] = []
        page = 1
        page_size = 100

        while True:
            response = self._http.get(
                "/api/devices",
                params={"page": page, "page_size": page_size},
            )
            response.raise_for_status()
            payload = response.json()
            page_devices = payload.get("devices", [])
            total = int(payload.get("total", 0))
            devices.extend(page_devices)
            if len(devices) >= total or not page_devices:
                break
            page += 1

        return devices

    def _build_supported_devices(self, api_devices: list[dict[str, Any]]) -> list[SimulatedDevice]:
        """Instantiate runtime mock devices from API device records."""
        mqtt_config = get_mqtt_config()
        simulated: list[SimulatedDevice] = []

        for index, api_device in enumerate(api_devices):
            device_id = str(api_device.get("id", "")).strip()
            if not device_id:
                continue

            name = str(api_device.get("friendly_name") or device_id)
            raw_type = str(api_device.get("device_type", "")).strip().lower()
            if raw_type not in _SUPPORTED_TYPES:
                continue

            client_id = f"sim-device-runner-{index + 1:03d}"
            config = mqtt_config.model_copy(update={"client_id": client_id})

            if raw_type in _LIGHT_TYPES:
                simulated.append(
                    SimulatedDevice(
                        kind="light",
                        device_id=device_id,
                        name=name,
                        runtime=MockSmartLight(device_id=device_id, name=name, config=config),
                    )
                )
            elif raw_type in _TEMP_TYPES:
                simulated.append(
                    SimulatedDevice(
                        kind="temperature_sensor",
                        device_id=device_id,
                        name=name,
                        runtime=MockTemperatureSensor(
                            device_id=device_id,
                            name=name,
                            config=config,
                            interval=5.0,
                        ),
                    )
                )
            elif raw_type in _MOTION_TYPES:
                simulated.append(
                    SimulatedDevice(
                        kind="motion_sensor",
                        device_id=device_id,
                        name=name,
                        runtime=MockMotionSensor(device_id=device_id, name=name, config=config),
                    )
                )

        logger.info(
            "simulation_devices_loaded",
            total_devices=len(api_devices),
            supported_devices=len(simulated),
        )
        return simulated

    def _seed_missing_supported_devices(self, api_devices: list[dict[str, Any]]) -> None:
        """Create one device per supported mock kind if missing.

        This operation is idempotent: if a kind is already present in DB,
        nothing is created for that kind.
        """
        existing_type_to_count: dict[str, int] = {}
        existing_ids: set[str] = set()
        for device in api_devices:
            raw_type = str(device.get("device_type", "")).strip().lower()
            if raw_type:
                existing_type_to_count[raw_type] = existing_type_to_count.get(raw_type, 0) + 1
            raw_id = str(device.get("id", "")).strip()
            if raw_id:
                existing_ids.add(raw_id)

        seed_specs = [
            {
                "aliases": _LIGHT_TYPES,
                "device_type": "smart_light",
                "name": "Seed Smart Light",
                "id_prefix": "seed-smart-light",
            },
            {
                "aliases": _TEMP_TYPES,
                "device_type": "temperature_sensor",
                "name": "Seed Temperature Sensor",
                "id_prefix": "seed-temperature-sensor",
            },
            {
                "aliases": _MOTION_TYPES,
                "device_type": "motion_sensor",
                "name": "Seed Motion Sensor",
                "id_prefix": "seed-motion-sensor",
            },
        ]

        for spec in seed_specs:
            if any(existing_type_to_count.get(alias, 0) > 0 for alias in spec["aliases"]):
                continue

            device_id = self._next_available_seed_id(
                id_prefix=str(spec["id_prefix"]),
                existing_ids=existing_ids,
            )
            payload = {
                "id": device_id,
                "friendly_name": str(spec["name"]),
                "device_type": str(spec["device_type"]),
                "mqtt_topic": TopicBuilder.device_topic(device_id, "state"),
                "manufacturer": "SmartNest",
                "model": "Seed",
                "firmware_version": "1.0.0",
                "capabilities": [],
            }

            response = self._http.post("/api/devices", json=payload)
            response.raise_for_status()
            existing_ids.add(device_id)

            logger.info(
                "simulation_seed_device_created",
                device_id=device_id,
                device_type=spec["device_type"],
            )

    def _next_available_seed_id(self, id_prefix: str, existing_ids: set[str]) -> str:
        """Generate a unique deterministic seed id based on a prefix."""
        candidate = id_prefix
        suffix = 1
        while candidate in existing_ids:
            suffix += 1
            candidate = f"{id_prefix}-{suffix:03d}"
        return candidate

    def _select_devices_for_simulation(
        self, supported_devices: list[SimulatedDevice]
    ) -> list[SimulatedDevice]:
        """Select devices to simulate based on runner mode.

        Default mode keeps one device per supported kind to provide a compact,
        representative system run. --all-supported keeps previous behavior.
        """
        if self._config.simulate_all_supported:
            return supported_devices

        first_by_kind: dict[DeviceKind, SimulatedDevice] = {}
        for device in supported_devices:
            first_by_kind.setdefault(device.kind, device)

        return list(first_by_kind.values())

    def _start_devices(self) -> None:
        """Start all mock devices."""
        for device in self._devices:
            started = device.runtime.start(timeout=10.0)
            if not started:
                msg = f"Failed to start mock device: {device.device_id}"
                raise RuntimeError(msg)
            logger.info("simulation_device_started", device_id=device.device_id)

    def _stop_devices(self) -> None:
        """Stop all mock devices with best-effort teardown."""
        for device in self._devices:
            try:
                device.runtime.stop(reason="simulation_complete")
                logger.info("simulation_device_stopped", device_id=device.device_id)
            except Exception:
                logger.exception("simulation_device_stop_failed", device_id=device.device_id)

    def _set_all_status(self, status: str) -> None:
        """Set all simulation devices to the given status via API."""
        for device in self._devices:
            try:
                response = self._http.patch(
                    f"/api/devices/{device.device_id}/status",
                    json={"status": status},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                logger.exception(
                    "simulation_status_update_failed",
                    device_id=device.device_id,
                    status=status,
                )
            else:
                logger.info(
                    "simulation_status_updated",
                    device_id=device.device_id,
                    status=status,
                )

    def _run_state_changes(self) -> None:
        """Publish a sequence of state changes across all devices."""
        total_changes = self._config.state_changes_per_device * len(self._devices)
        for index in range(total_changes):
            device = self._rng.choice(self._devices)
            payload = self._build_next_command(device)
            topic = TopicBuilder.device_topic(device.device_id, "command")
            published = device.runtime.client.publish(topic, payload, qos=1, retain=False)
            self._touch_device_online(device.device_id)

            logger.info(
                "simulation_state_change",
                change_number=index + 1,
                total_changes=total_changes,
                device_id=device.device_id,
                payload=payload,
                published=published,
            )

            if index < total_changes - 1:
                delay = self._rng.uniform(
                    self._config.min_delay_seconds,
                    self._config.max_delay_seconds,
                )
                self._sleep(delay)

    def _touch_device_online(self, device_id: str) -> None:
        """Update device status to online to refresh last_seen in UI."""
        try:
            response = self._http.patch(
                f"/api/devices/{device_id}/status",
                json={"status": "online"},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("simulation_touch_online_failed", device_id=device_id)

    def _build_next_command(self, device: SimulatedDevice) -> dict[str, int | bool | float]:
        """Build next command payload that changes current light state."""
        if device.kind == "temperature_sensor":
            interval = self._rng.choice([5.0, 6.0, 8.0, 10.0])
            return {"interval": interval}

        if device.kind == "motion_sensor":
            return {"trigger": True}

        light = device.runtime
        current_power = bool(getattr(light, "power", False))
        current_brightness = int(getattr(light, "brightness", 50))
        current_color_temp = int(getattr(light, "color_temp", 4000))
        action = self._rng.choice(["power", "brightness", "color_temp"])
        if action == "power":
            return {"power": not current_power}

        if action == "brightness":
            options = [10, 30, 50, 70, 90]
            choices = [value for value in options if value != current_brightness]
            return {"brightness": self._rng.choice(choices)}

        options = [2700, 3000, 4000, 5000, 6500]
        choices = [value for value in options if value != current_color_temp]
        return {"color_temp": self._rng.choice(choices)}


def _parse_args(argv: list[str] | None = None) -> RunnerConfig:
    """Parse CLI arguments into a validated runner config."""
    parser = argparse.ArgumentParser(description="SmartNest mock device simulation runner")
    parser.add_argument("--api-base-url", default=_DEFAULT_API_BASE_URL)
    parser.add_argument(
        "--username",
        default=(os.getenv("SMARTNEST_ADMIN_USERNAME", "").strip()),
    )
    parser.add_argument(
        "--password",
        default=(os.getenv("SMARTNEST_ADMIN_PASSWORD") or ""),
    )
    parser.add_argument("--state-changes", type=int, default=_DEFAULT_STATE_CHANGES)
    parser.add_argument("--warmup-seconds", type=float, default=_DEFAULT_WARMUP_SECONDS)
    parser.add_argument("--min-delay-seconds", type=float, default=_DEFAULT_MIN_DELAY_SECONDS)
    parser.add_argument("--max-delay-seconds", type=float, default=_DEFAULT_MAX_DELAY_SECONDS)
    parser.add_argument(
        "--all-supported",
        action="store_true",
        help="Simulate all supported devices from DB instead of one per supported type",
    )
    parser.add_argument(
        "--seed-supported",
        action="store_true",
        help="Create missing supported device kinds before simulation (idempotent)",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Only perform idempotent seeding and exit",
    )

    args = parser.parse_args(argv)

    if not str(args.username).strip():
        parser.error("Missing username. Use --username or set SMARTNEST_ADMIN_USERNAME in .env")

    if not str(args.password).strip():
        parser.error("Missing password. Use --password or set SMARTNEST_ADMIN_PASSWORD in .env")

    if args.state_changes < 1:
        parser.error("--state-changes must be >= 1")

    if args.min_delay_seconds <= 0 or args.max_delay_seconds <= 0:
        parser.error("Delay values must be > 0")

    if args.min_delay_seconds > args.max_delay_seconds:
        parser.error("--min-delay-seconds must be <= --max-delay-seconds")

    if args.warmup_seconds < 0:
        parser.error("--warmup-seconds must be >= 0")

    seed_only = bool(args.seed_only)
    seed_supported = bool(args.seed_supported) or seed_only

    return RunnerConfig(
        api_base_url=str(args.api_base_url),
        username=str(args.username).strip(),
        password=str(args.password),
        state_changes_per_device=int(args.state_changes),
        warmup_seconds=float(args.warmup_seconds),
        min_delay_seconds=float(args.min_delay_seconds),
        max_delay_seconds=float(args.max_delay_seconds),
        simulate_all_supported=bool(args.all_supported),
        seed_supported=seed_supported,
        seed_only=seed_only,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for mock device simulation runner."""
    # Load .env into process environment for CLI usage (non-destructive).
    load_dotenv(override=False)
    configure_logging(level="INFO", renderer="console")
    config = _parse_args(argv)
    runner = DeviceSimulationRunner(config)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
