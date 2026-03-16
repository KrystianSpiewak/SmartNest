"""Unit tests for mock device simulation runner."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.devices.runner import (
    DeviceSimulationRunner,
    RunnerConfig,
    SimulatedDevice,
    _parse_args,
    main,
)


class _FakeRuntime:
    def __init__(self) -> None:
        self.client = MagicMock()
        self.client.publish.return_value = True
        self.start_called = False
        self.stop_called = False

    def start(self, timeout: float = 10.0) -> bool:
        assert timeout == 10.0
        self.start_called = True
        return True

    def stop(self, reason: str = "shutdown") -> None:
        assert reason == "simulation_complete"
        self.stop_called = True


class _FakeLightRuntime(_FakeRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.power = False
        self.brightness = 50
        self.color_temp = 4000


class _FailingStartRuntime(_FakeRuntime):
    def start(self, timeout: float = 10.0) -> bool:
        assert timeout == 10.0
        return False


class _FailingStopRuntime(_FakeRuntime):
    def stop(self, reason: str = "shutdown") -> None:
        raise RuntimeError("boom")


@pytest.fixture
def runner_config() -> RunnerConfig:
    return RunnerConfig(
        api_base_url="http://127.0.0.1:8000",
        username="notarealadmin",
        password="notarealpassword123",
        state_changes_per_device=2,
        warmup_seconds=0.0,
        min_delay_seconds=0.01,
        max_delay_seconds=0.02,
    )


@pytest.fixture
def mock_http_client() -> MagicMock:
    client = MagicMock(spec=httpx.Client)
    client.headers = {}
    return client


@pytest.fixture
def runner(runner_config: RunnerConfig, mock_http_client: MagicMock) -> DeviceSimulationRunner:
    with patch("backend.devices.runner.httpx.Client", return_value=mock_http_client):
        return DeviceSimulationRunner(runner_config, sleeper=lambda _s: None)


class TestParseArgs:
    _VALID_CREDS: ClassVar[list[str]] = [
        "--username",
        "notarealadmin",
        "--password",
        "notarealpassword123",
    ]

    def test_parse_args_uses_env_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMARTNEST_ADMIN_USERNAME", "notarealadmin")
        monkeypatch.setenv("SMARTNEST_ADMIN_PASSWORD", "notarealpassword123")

        config = _parse_args([])

        assert config.username == "notarealadmin"
        assert config.password == "notarealpassword123"
        assert config.state_changes_per_device == 10

    def test_parse_args_uses_cli_credentials(self) -> None:
        config = _parse_args(["--username", "notarealadmin", "--password", "notarealpassword123"])

        assert config.username == "notarealadmin"
        assert config.password == "notarealpassword123"

    def test_parse_args_requires_username(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMARTNEST_ADMIN_USERNAME", raising=False)
        monkeypatch.setenv("SMARTNEST_ADMIN_PASSWORD", "notarealpassword123")

        with pytest.raises(SystemExit):
            _parse_args([])

    def test_parse_args_requires_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMARTNEST_ADMIN_USERNAME", "notarealadmin")
        monkeypatch.delenv("SMARTNEST_ADMIN_PASSWORD", raising=False)

        with pytest.raises(SystemExit):
            _parse_args([])

    def test_parse_args_rejects_invalid_state_changes(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args([*self._VALID_CREDS, "--state-changes", "0"])

    def test_parse_args_rejects_non_positive_delay(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args([*self._VALID_CREDS, "--min-delay-seconds", "0"])

    def test_parse_args_rejects_delay_range(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args(
                [*self._VALID_CREDS, "--min-delay-seconds", "5", "--max-delay-seconds", "3"]
            )

    def test_parse_args_rejects_negative_warmup(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args([*self._VALID_CREDS, "--warmup-seconds", "-1"])

    def test_parse_args_all_supported_flag_enabled(self) -> None:
        config = _parse_args(
            [
                "--username",
                "notarealadmin",
                "--password",
                "notarealpassword123",
                "--all-supported",
            ]
        )

        assert config.simulate_all_supported is True

    def test_parse_args_seed_supported_flag_enabled(self) -> None:
        config = _parse_args(
            [
                "--username",
                "notarealadmin",
                "--password",
                "notarealpassword123",
                "--seed-supported",
            ]
        )

        assert config.seed_supported is True
        assert config.seed_only is False

    def test_parse_args_seed_only_implies_seed_supported(self) -> None:
        config = _parse_args(
            [
                "--username",
                "notarealadmin",
                "--password",
                "notarealpassword123",
                "--seed-only",
            ]
        )

        assert config.seed_only is True
        assert config.seed_supported is True


class TestAuthentication:
    def test_authenticate_success(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"access_token": "token-123"}
        mock_http_client.post.return_value = response

        success = runner._authenticate()

        assert success is True
        assert mock_http_client.headers["Authorization"] == "Bearer token-123"

    def test_authenticate_http_error(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        mock_http_client.post.side_effect = httpx.HTTPError("fail")

        success = runner._authenticate()

        assert success is False

    def test_authenticate_missing_token(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"access_token": ""}
        mock_http_client.post.return_value = response

        success = runner._authenticate()

        assert success is False


class TestFetchDevices:
    def test_fetch_devices_single_page(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"devices": [{"id": "d1"}], "total": 1}
        mock_http_client.get.return_value = response

        result = runner._fetch_devices_from_api()

        assert len(result) == 1
        assert result[0]["id"] == "d1"

    def test_fetch_devices_multi_page(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        response1 = MagicMock()
        response1.raise_for_status.return_value = None
        response1.json.return_value = {"devices": [{"id": "d1"}], "total": 2}

        response2 = MagicMock()
        response2.raise_for_status.return_value = None
        response2.json.return_value = {"devices": [{"id": "d2"}], "total": 2}

        mock_http_client.get.side_effect = [response1, response2]

        result = runner._fetch_devices_from_api()

        assert [device["id"] for device in result] == ["d1", "d2"]


class TestBuildSupportedDevices:
    def test_build_supported_devices_filters_and_maps_types(
        self, runner: DeviceSimulationRunner
    ) -> None:
        mock_mqtt_config = MagicMock()
        mock_mqtt_config.model_copy.side_effect = [MagicMock(), MagicMock(), MagicMock()]

        with (
            patch("backend.devices.runner.get_mqtt_config", return_value=mock_mqtt_config),
            patch("backend.devices.runner.MockSmartLight", return_value=_FakeLightRuntime()),
            patch("backend.devices.runner.MockTemperatureSensor", return_value=_FakeRuntime()),
            patch("backend.devices.runner.MockMotionSensor", return_value=_FakeRuntime()),
        ):
            devices = runner._build_supported_devices(
                [
                    {"id": "light-001", "friendly_name": "Light", "device_type": "light"},
                    {
                        "id": "temp-001",
                        "friendly_name": "Temp",
                        "device_type": "temperature_sensor",
                    },
                    {"id": "motion-001", "friendly_name": "Motion", "device_type": "motion_sensor"},
                    {"id": "x", "friendly_name": "Unsupported", "device_type": "door_sensor"},
                    {"id": "", "friendly_name": "MissingId", "device_type": "light"},
                ]
            )

        assert len(devices) == 3
        assert {device.kind for device in devices} == {
            "light",
            "temperature_sensor",
            "motion_sensor",
        }

    def test_build_supported_devices_handles_extra_supported_type_without_mapping(
        self, runner: DeviceSimulationRunner
    ) -> None:
        mock_mqtt_config = MagicMock()
        mock_mqtt_config.model_copy.return_value = MagicMock()

        with (
            patch("backend.devices.runner.get_mqtt_config", return_value=mock_mqtt_config),
            patch("backend.devices.runner._SUPPORTED_TYPES", {"unknown_supported"}),
        ):
            devices = runner._build_supported_devices(
                [{"id": "x-001", "friendly_name": "X", "device_type": "unknown_supported"}]
            )

        assert devices == []

    def test_select_devices_for_simulation_defaults_to_one_per_kind(
        self, runner: DeviceSimulationRunner
    ) -> None:
        devices = [
            SimulatedDevice(
                kind="light", device_id="light-001", name="L1", runtime=_FakeLightRuntime()
            ),
            SimulatedDevice(
                kind="light", device_id="light-002", name="L2", runtime=_FakeLightRuntime()
            ),
            SimulatedDevice(
                kind="temperature_sensor", device_id="temp-001", name="T1", runtime=_FakeRuntime()
            ),
            SimulatedDevice(
                kind="temperature_sensor", device_id="temp-002", name="T2", runtime=_FakeRuntime()
            ),
            SimulatedDevice(
                kind="motion_sensor", device_id="motion-001", name="M1", runtime=_FakeRuntime()
            ),
        ]

        selected = runner._select_devices_for_simulation(devices)

        assert len(selected) == 3
        assert {device.kind for device in selected} == {
            "light",
            "temperature_sensor",
            "motion_sensor",
        }
        assert {device.device_id for device in selected} == {"light-001", "temp-001", "motion-001"}

    def test_select_devices_for_simulation_all_supported_mode_keeps_all(
        self, runner_config: RunnerConfig, mock_http_client: MagicMock
    ) -> None:
        all_mode_config = RunnerConfig(
            api_base_url=runner_config.api_base_url,
            username=runner_config.username,
            password=runner_config.password,
            state_changes_per_device=runner_config.state_changes_per_device,
            warmup_seconds=runner_config.warmup_seconds,
            min_delay_seconds=runner_config.min_delay_seconds,
            max_delay_seconds=runner_config.max_delay_seconds,
            simulate_all_supported=True,
        )
        with patch("backend.devices.runner.httpx.Client", return_value=mock_http_client):
            all_mode_runner = DeviceSimulationRunner(all_mode_config, sleeper=lambda _s: None)

        devices = [
            SimulatedDevice(
                kind="light", device_id="light-001", name="L1", runtime=_FakeLightRuntime()
            ),
            SimulatedDevice(
                kind="light", device_id="light-002", name="L2", runtime=_FakeLightRuntime()
            ),
            SimulatedDevice(
                kind="temperature_sensor", device_id="temp-001", name="T1", runtime=_FakeRuntime()
            ),
        ]

        selected = all_mode_runner._select_devices_for_simulation(devices)

        assert selected == devices

    def test_seed_missing_supported_devices_adds_only_missing_kinds(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        existing_devices = [
            {"id": "light-001", "device_type": "light"},
            {"id": "smart-light-existing", "device_type": "smart_light"},
        ]
        ok_response = MagicMock()
        ok_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = ok_response

        runner._seed_missing_supported_devices(existing_devices)

        assert mock_http_client.post.call_count == 2
        post_payloads = [call.kwargs["json"] for call in mock_http_client.post.call_args_list]
        posted_types = {payload["device_type"] for payload in post_payloads}
        assert posted_types == {"temperature_sensor", "motion_sensor"}

    def test_seed_missing_supported_devices_noop_when_all_present(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        existing_devices = [
            {"id": "light-001", "device_type": "light"},
            {"id": "temp-001", "device_type": "temperature_sensor"},
            {"id": "motion-001", "device_type": "motion_sensor"},
        ]

        runner._seed_missing_supported_devices(existing_devices)

        mock_http_client.post.assert_not_called()

    def test_seed_missing_supported_devices_ignores_empty_type_and_id(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        """Cover branches where device_type/id are empty strings after normalization."""
        existing_devices = [
            {"id": "   ", "device_type": "   "},
        ]
        ok_response = MagicMock()
        ok_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = ok_response

        runner._seed_missing_supported_devices(existing_devices)

        # With no usable type/id found, all 3 supported kinds should be seeded.
        assert mock_http_client.post.call_count == 3

    def test_next_available_seed_id_adds_suffix_when_base_taken(
        self, runner: DeviceSimulationRunner
    ) -> None:
        result = runner._next_available_seed_id(
            id_prefix="seed-smart-light",
            existing_ids={"seed-smart-light", "seed-smart-light-002"},
        )

        assert result == "seed-smart-light-003"


class TestDeviceActions:
    def test_start_devices_success(self, runner: DeviceSimulationRunner) -> None:
        good_runtime = _FakeRuntime()
        runner._devices = [
            SimulatedDevice(kind="light", device_id="light-001", name="Light", runtime=good_runtime)
        ]

        runner._start_devices()

        assert good_runtime.start_called is True

    def test_start_devices_raises_when_start_fails(self, runner: DeviceSimulationRunner) -> None:
        bad_runtime = _FailingStartRuntime()
        runner._devices = [
            SimulatedDevice(kind="light", device_id="light-001", name="Light", runtime=bad_runtime)
        ]

        with pytest.raises(RuntimeError):
            runner._start_devices()

    def test_start_devices_with_no_devices(self, runner: DeviceSimulationRunner) -> None:
        runner._devices = []

        runner._start_devices()

    def test_stop_devices_handles_exception(self, runner: DeviceSimulationRunner) -> None:
        good_runtime = _FakeRuntime()
        bad_runtime = _FailingStopRuntime()
        runner._devices = [
            SimulatedDevice(
                kind="light", device_id="light-001", name="Light", runtime=good_runtime
            ),
            SimulatedDevice(
                kind="motion_sensor", device_id="motion-001", name="Motion", runtime=bad_runtime
            ),
        ]

        runner._stop_devices()

        assert good_runtime.stop_called is True

    def test_set_all_status_handles_http_error(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        runner._devices = [
            SimulatedDevice(
                kind="light", device_id="light-001", name="Light", runtime=_FakeLightRuntime()
            )
        ]

        bad_response = MagicMock()
        bad_response.raise_for_status.side_effect = httpx.HTTPError("fail")
        mock_http_client.patch.return_value = bad_response

        runner._set_all_status("online")

        mock_http_client.patch.assert_called_once()

    def test_set_all_status_success(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        runner._devices = [
            SimulatedDevice(
                kind="light", device_id="light-001", name="Light", runtime=_FakeLightRuntime()
            )
        ]
        ok_response = MagicMock()
        ok_response.raise_for_status.return_value = None
        mock_http_client.patch.return_value = ok_response

        runner._set_all_status("offline")

        mock_http_client.patch.assert_called_once_with(
            "/api/devices/light-001/status",
            json={"status": "offline"},
        )

    def test_set_all_status_with_no_devices(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        runner._devices = []

        runner._set_all_status("online")

        mock_http_client.patch.assert_not_called()

    def test_touch_device_online_handles_http_error(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        bad_response = MagicMock()
        bad_response.raise_for_status.side_effect = httpx.HTTPError("fail")
        mock_http_client.patch.return_value = bad_response

        runner._touch_device_online("light-001")

        mock_http_client.patch.assert_called_once()

    def test_touch_device_online_success(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        ok_response = MagicMock()
        ok_response.raise_for_status.return_value = None
        mock_http_client.patch.return_value = ok_response

        runner._touch_device_online("light-001")

        mock_http_client.patch.assert_called_once_with(
            "/api/devices/light-001/status",
            json={"status": "online"},
        )


class TestCommandBuilders:
    def test_build_next_command_temperature_sensor(self, runner: DeviceSimulationRunner) -> None:
        device = SimulatedDevice(
            kind="temperature_sensor",
            device_id="temp-001",
            name="Temp",
            runtime=_FakeRuntime(),
        )
        runner._rng = MagicMock()
        runner._rng.choice.return_value = 6.0

        payload = runner._build_next_command(device)

        assert payload == {"interval": 6.0}

    def test_build_next_command_motion_sensor(self, runner: DeviceSimulationRunner) -> None:
        device = SimulatedDevice(
            kind="motion_sensor",
            device_id="motion-001",
            name="Motion",
            runtime=_FakeRuntime(),
        )

        payload = runner._build_next_command(device)

        assert payload == {"trigger": True}

    def test_build_next_command_light_power(self, runner: DeviceSimulationRunner) -> None:
        light_runtime = _FakeLightRuntime()
        device = SimulatedDevice(
            kind="light",
            device_id="light-001",
            name="Light",
            runtime=light_runtime,
        )
        runner._rng = MagicMock()
        runner._rng.choice.side_effect = ["power"]

        payload = runner._build_next_command(device)

        assert payload == {"power": True}

    def test_build_next_command_light_brightness(self, runner: DeviceSimulationRunner) -> None:
        light_runtime = _FakeLightRuntime()
        device = SimulatedDevice(
            kind="light",
            device_id="light-001",
            name="Light",
            runtime=light_runtime,
        )
        runner._rng = MagicMock()
        runner._rng.choice.side_effect = ["brightness", 70]

        payload = runner._build_next_command(device)

        assert payload == {"brightness": 70}

    def test_build_next_command_light_color_temp(self, runner: DeviceSimulationRunner) -> None:
        light_runtime = _FakeLightRuntime()
        device = SimulatedDevice(
            kind="light",
            device_id="light-001",
            name="Light",
            runtime=light_runtime,
        )
        runner._rng = MagicMock()
        runner._rng.choice.side_effect = ["color_temp", 5000]

        payload = runner._build_next_command(device)

        assert payload == {"color_temp": 5000}


class TestRunStateChanges:
    def test_run_state_changes_publishes_and_touches_online(
        self, runner: DeviceSimulationRunner
    ) -> None:
        light_runtime = _FakeLightRuntime()
        device = SimulatedDevice(
            kind="light",
            device_id="light-001",
            name="Light",
            runtime=light_runtime,
        )
        runner._devices = [device]
        runner._rng = MagicMock()
        runner._rng.choice.side_effect = [device, "power", device, "power"]
        runner._rng.uniform.return_value = 0.01
        with patch.object(runner, "_touch_device_online") as mock_touch:
            runner._run_state_changes()

        assert light_runtime.client.publish.call_count == 2
        assert mock_touch.call_count == 2


class TestRun:
    def test_run_returns_1_when_auth_fails(
        self, runner: DeviceSimulationRunner, mock_http_client: MagicMock
    ) -> None:
        mock_http_client.post.side_effect = httpx.HTTPError("auth")

        assert runner.run() == 1

    def test_run_returns_0_when_no_supported_devices(self, runner: DeviceSimulationRunner) -> None:
        with (
            patch.object(runner, "_authenticate", return_value=True),
            patch.object(runner, "_fetch_devices_from_api", return_value=[]),
            patch.object(runner, "_build_supported_devices", return_value=[]),
        ):
            result = runner.run()

        assert result == 0

    def test_run_happy_path(self, runner: DeviceSimulationRunner) -> None:
        device = SimulatedDevice(
            kind="light",
            device_id="light-001",
            name="Light",
            runtime=_FakeLightRuntime(),
        )
        with (
            patch.object(runner, "_authenticate", return_value=True),
            patch.object(runner, "_fetch_devices_from_api", return_value=[{"id": "light-001"}]),
            patch.object(runner, "_build_supported_devices", return_value=[device]),
            patch.object(runner, "_set_all_status") as mock_set_status,
            patch.object(runner, "_start_devices"),
            patch.object(runner, "_run_state_changes"),
            patch.object(runner, "_stop_devices"),
        ):
            result = runner.run()

        assert result == 0
        assert mock_set_status.call_count == 3

    def test_run_seed_only_seeds_and_exits_before_simulation(
        self, runner: DeviceSimulationRunner
    ) -> None:
        seeded_runner = DeviceSimulationRunner(
            RunnerConfig(
                api_base_url="http://127.0.0.1:8000",
                username="notarealadmin",
                password="notarealpassword123",
                state_changes_per_device=2,
                warmup_seconds=0.0,
                min_delay_seconds=0.01,
                max_delay_seconds=0.02,
                seed_supported=True,
                seed_only=True,
            ),
            sleeper=lambda _s: None,
        )

        seeded_runner._http = MagicMock(spec=httpx.Client)
        with (
            patch.object(seeded_runner, "_authenticate", return_value=True),
            patch.object(seeded_runner, "_fetch_devices_from_api", return_value=[]),
            patch.object(seeded_runner, "_seed_missing_supported_devices") as mock_seed,
            patch.object(seeded_runner, "_start_devices") as mock_start,
        ):
            result = seeded_runner.run()

        assert result == 0
        mock_seed.assert_called_once()
        mock_start.assert_not_called()


class TestMain:
    def test_main_returns_runner_exit_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMARTNEST_ADMIN_USERNAME", "notarealadmin")
        monkeypatch.setenv("SMARTNEST_ADMIN_PASSWORD", "notarealpassword123")

        with (
            patch("backend.devices.runner.configure_logging"),
            patch("backend.devices.runner.DeviceSimulationRunner") as mock_runner_cls,
        ):
            mock_runner = MagicMock()
            mock_runner.run.return_value = 0
            mock_runner_cls.return_value = mock_runner

            result = main([])

            assert result == 0
            mock_runner.run.assert_called_once()
