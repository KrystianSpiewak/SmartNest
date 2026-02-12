"""Integration tests for MQTT Bridge service.

Tests the complete flow from MQTT device discovery/state messages
through to database persistence.
"""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from backend.api.mqtt_bridge import MQTTBridge
from backend.config import AppSettings
from backend.database.connection import init_database
from backend.database.repositories.device import DeviceRepository
from backend.mqtt.client import SmartNestMQTTClient
from backend.mqtt.config import MQTTConfig


@pytest.fixture
def test_db_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[AppSettings, Path]:
    """Provide test settings with temporary database for MQTT bridge tests."""
    settings = AppSettings(
        admin_username="testadmin",
        admin_email="test@example.com",
        admin_password="testpass123",
        bcrypt_rounds=4,  # Faster for testing
        host="127.0.0.1",
        port=8000,
        _env_file=None,  # type: ignore[call-arg]
    )
    # Mock settings
    monkeypatch.setattr("backend.config.get_settings", lambda: settings)

    # Mock database path to use temp directory
    test_db_path = tmp_path / f"test_mqtt_bridge_{id(settings)}.db"
    monkeypatch.setattr("backend.database.connection.DATABASE_PATH", test_db_path)

    # Reset database initialization state
    monkeypatch.setattr("backend.database.connection._initialized", False)

    return settings, test_db_path


@pytest.fixture
def mqtt_config() -> MQTTConfig:
    """Create MQTT configuration for testing."""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="test_bridge_client",
    )


@pytest.fixture
def mock_mqtt_client(mqtt_config: MQTTConfig) -> Generator[SmartNestMQTTClient]:
    """Create a mock MQTT client for testing."""
    with patch("backend.mqtt.client.mqtt.Client"):
        client = SmartNestMQTTClient(mqtt_config)
        # Mock the internal Paho client
        mock_paho = Mock()
        mock_paho.subscribe = Mock(return_value=(0, 1))
        mock_paho.message_callback_add = Mock()
        mock_paho.message_callback_remove = Mock()
        client._paho = mock_paho
        client.set_connected_for_test(True)
        yield client


@pytest.fixture
async def mqtt_bridge(mock_mqtt_client: SmartNestMQTTClient) -> MQTTBridge:
    """Create MQTT bridge instance for testing."""
    return MQTTBridge(mock_mqtt_client)


class TestMQTTBridgeLifecycle:
    """Test MQTT bridge startup and shutdown."""

    async def test_bridge_initialization(self, mock_mqtt_client: SmartNestMQTTClient) -> None:
        """Test bridge initializes correctly."""
        bridge = MQTTBridge(mock_mqtt_client)
        assert bridge._mqtt_client is mock_mqtt_client
        assert bridge._discovery_consumer is not None
        assert not bridge._started

    async def test_bridge_start(self, mqtt_bridge: MQTTBridge) -> None:
        """Test bridge starts successfully."""
        await mqtt_bridge.start()
        assert mqtt_bridge._started

    async def test_bridge_start_twice_raises_error(self, mqtt_bridge: MQTTBridge) -> None:
        """Test starting bridge twice raises RuntimeError."""
        await mqtt_bridge.start()
        with pytest.raises(RuntimeError, match="already started"):
            await mqtt_bridge.start()

    async def test_bridge_stop(self, mqtt_bridge: MQTTBridge) -> None:
        """Test bridge stops successfully."""
        await mqtt_bridge.start()
        await mqtt_bridge.stop()
        assert not mqtt_bridge._started

    async def test_bridge_stop_when_not_started(self, mqtt_bridge: MQTTBridge) -> None:
        """Test stopping bridge when not started is safe."""
        await mqtt_bridge.stop()  # Should not raise
        assert not mqtt_bridge._started


class TestDeviceDiscoverySync:
    """Test device discovery synchronization to database."""

    @pytest.fixture(autouse=True)
    async def _setup_database(self, test_db_settings: tuple[AppSettings, Path]) -> None:
        """Initialize test database for each test."""
        await init_database()

    @pytest.fixture
    def discovery_payload(self) -> dict[str, object]:
        """Sample device discovery payload."""
        return {
            "device_id": "test_light_01",
            "name": "Test Light",
            "device_type": "smart_light",
            "capabilities": ["power", "brightness"],
            "topics": {
                "command": "smartnest/device/test_light_01/command",
                "state": "smartnest/device/test_light_01/state",
            },
        }

    async def test_sync_discovered_devices_empty(self, mqtt_bridge: MQTTBridge) -> None:
        """Test syncing when no devices discovered."""
        await mqtt_bridge.start()
        synced = await mqtt_bridge.sync_discovered_devices()
        assert synced == 0

    async def test_sync_discovered_devices_single(
        self,
        mqtt_bridge: MQTTBridge,
        discovery_payload: dict[str, object],
    ) -> None:
        """Test syncing a single discovered device to database."""
        await mqtt_bridge.start()

        # Simulate device discovery
        mqtt_bridge._discovery_consumer._register_device(discovery_payload)

        # Sync to database
        synced = await mqtt_bridge.sync_discovered_devices()
        assert synced == 1

        # Verify device persisted
        device = await DeviceRepository.get_by_id("test_light_01")
        assert device is not None
        assert device.friendly_name == "Test Light"
        assert device.device_type == "smart_light"
        assert device.capabilities == ["power", "brightness"]

    async def test_sync_discovered_devices_multiple(
        self,
        mqtt_bridge: MQTTBridge,
        discovery_payload: dict[str, object],
    ) -> None:
        """Test syncing multiple discovered devices."""
        await mqtt_bridge.start()

        # Simulate multiple device discoveries
        devices = [
            {
                **discovery_payload,
                "device_id": f"test_light_{i:02d}",
                "name": f"Light {i}",
                "topics": {
                    "command": f"smartnest/device/test_light_{i:02d}/command",
                    "state": f"smartnest/device/test_light_{i:02d}/state",
                },
            }
            for i in range(1, 4)
        ]
        for device in devices:
            mqtt_bridge._discovery_consumer._register_device(device)

        # Sync to database
        synced = await mqtt_bridge.sync_discovered_devices()
        assert synced == 3

        # Verify all devices persisted
        for i in range(1, 4):
            device_resp = await DeviceRepository.get_by_id(f"test_light_{i:02d}")
            assert device_resp is not None
            assert device_resp.friendly_name == f"Light {i}"

    async def test_sync_duplicate_device_continues(
        self,
        mqtt_bridge: MQTTBridge,
        discovery_payload: dict[str, object],
    ) -> None:
        """Test sync continues on duplicate device (logs warning, doesn't fail)."""
        await mqtt_bridge.start()

        # First sync
        mqtt_bridge._discovery_consumer._register_device(discovery_payload)
        synced1 = await mqtt_bridge.sync_discovered_devices()
        assert synced1 == 1

        # Attempt to sync same device again (should gracefully handle duplicate)
        synced2 = await mqtt_bridge.sync_discovered_devices()
        assert synced2 == 0  # Already exists, can't create again


class TestDeviceStateUpdates:
    """Test device state update handling."""

    async def test_state_update_callback_valid_topic(self, mqtt_bridge: MQTTBridge) -> None:
        """Test state update callback with valid topic structure."""
        await mqtt_bridge.start()

        # Create mock MQTT message
        mock_message = Mock()
        mock_message.topic = "smartnest/device/test_light_01/state"
        mock_message.payload = b'{"power": true, "brightness": 75}'

        # Invoke callback (should not raise)
        mqtt_bridge._on_device_state_update(Mock(), None, mock_message)
        # Currently just logs - future enhancement will update database

    async def test_state_update_callback_invalid_topic(self, mqtt_bridge: MQTTBridge) -> None:
        """Test state update callback with malformed topic."""
        await mqtt_bridge.start()

        # Create mock MQTT message with invalid topic
        mock_message = Mock()
        mock_message.topic = "invalid/topic"
        mock_message.payload = b'{"power": true}'

        # Invoke callback (should log warning, not raise)
        mqtt_bridge._on_device_state_update(Mock(), None, mock_message)

    async def test_state_update_callback_logging_exception(self, mqtt_bridge: MQTTBridge) -> None:
        """Test state update callback handles logging exceptions gracefully."""
        await mqtt_bridge.start()

        # Create mock MQTT message
        mock_message = Mock()
        mock_message.topic = "smartnest/device/test_light_01/state"
        mock_message.payload = b'{"power": true}'

        # Patch logger.debug to raise exception to trigger exception handler
        with patch("backend.api.mqtt_bridge.logger.debug", side_effect=ValueError("Test error")):
            # Should not raise - exception is caught and logged
            mqtt_bridge._on_device_state_update(Mock(), None, mock_message)
        mock_message.payload = b'{"power": true}'

        # Invoke callback (should log warning, not raise)
        mqtt_bridge._on_device_state_update(Mock(), None, mock_message)
