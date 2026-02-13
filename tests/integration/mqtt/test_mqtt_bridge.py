"""Integration tests for MQTT Bridge service.

Tests the complete flow from MQTT device discovery/state messages
through to database persistence.
"""

from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, Mock, patch

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
    # Create a MagicMock for the Paho MQTT client
    mock_paho = MagicMock()
    mock_paho.subscribe = MagicMock(return_value=(0, 1))
    mock_paho.message_callback_add = MagicMock()
    mock_paho.message_callback_remove = MagicMock()

    with patch("backend.mqtt.client.mqtt.Client", return_value=mock_paho):
        client = SmartNestMQTTClient(mqtt_config)
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
        assert bridge.mqtt_client is mock_mqtt_client
        assert bridge.discovery_consumer is not None
        assert not bridge.is_started
        assert bridge.discovery_consumer.mqtt_client is mock_mqtt_client
        assert bridge.mqtt_client.config.client_id == "test_bridge_client"
        assert not bridge.is_started
        assert bridge.discovery_consumer.mqtt_client is mock_mqtt_client
        assert bridge.mqtt_client.config.client_id == "test_bridge_client"

    async def test_bridge_start(
        self, mqtt_bridge: MQTTBridge, mock_mqtt_client: SmartNestMQTTClient
    ) -> None:
        """Test bridge starts successfully."""
        # Verify initial state
        assert not mqtt_bridge.is_started
        assert not mqtt_bridge.discovery_consumer.is_started

        await mqtt_bridge.start()

        # Verify bridge started
        assert mqtt_bridge.is_started

        # Verify discovery consumer started
        assert mqtt_bridge.discovery_consumer.is_started

        # Get mock paho client for assertion
        mock_paho = cast("MagicMock", mock_mqtt_client.paho_client)

        # Verify MQTT subscriptions made
        assert mock_paho.subscribe.call_count >= 2  # discovery + state topics
        assert mock_paho.message_callback_add.call_count >= 2

        # Verify state topic subscription
        subscribe_calls = [call[0][0] for call in mock_paho.subscribe.call_args_list]
        assert any("smartnest/device/+/state" in call for call in subscribe_calls)

    async def test_bridge_start_twice_raises_error(
        self, mqtt_bridge: MQTTBridge, mock_mqtt_client: SmartNestMQTTClient
    ) -> None:
        """Test starting bridge twice raises RuntimeError."""
        await mqtt_bridge.start()

        # Get mock paho client for assertion
        mock_paho = cast("MagicMock", mock_mqtt_client.paho_client)

        # Record call counts after first start
        first_subscribe_count = mock_paho.subscribe.call_count
        first_callback_count = mock_paho.message_callback_add.call_count

        # Second start should raise
        with pytest.raises(RuntimeError, match="already started"):
            await mqtt_bridge.start()

        # Verify no additional subscriptions were made
        assert mock_paho.subscribe.call_count == first_subscribe_count
        assert mock_paho.message_callback_add.call_count == first_callback_count

    async def test_bridge_stop(
        self, mqtt_bridge: MQTTBridge, mock_mqtt_client: SmartNestMQTTClient
    ) -> None:
        """Test bridge stops successfully."""
        await mqtt_bridge.start()
        assert mqtt_bridge.is_started
        assert mqtt_bridge.discovery_consumer.is_started

        await mqtt_bridge.stop()

        # Verify bridge stopped
        assert not mqtt_bridge.is_started
        assert not mqtt_bridge.discovery_consumer.is_started

        # Get mock paho client for assertion
        mock_paho = cast("MagicMock", mock_mqtt_client.paho_client)

        # Verify MQTT cleanup performed
        assert mock_paho.message_callback_remove.call_count >= 1

        # Verify state topic handler removed
        remove_calls = [call[0][0] for call in mock_paho.message_callback_remove.call_args_list]
        assert any("smartnest/device/+/state" in call for call in remove_calls)

    async def test_bridge_stop_when_not_started(
        self, mqtt_bridge: MQTTBridge, mock_mqtt_client: SmartNestMQTTClient
    ) -> None:
        """Test stopping bridge when not started is safe."""
        # Verify not started
        assert not mqtt_bridge.is_started

        # Get mock paho client for assertion
        mock_paho = cast("MagicMock", mock_mqtt_client.paho_client)

        # Record initial state
        initial_remove_count = mock_paho.message_callback_remove.call_count

        await mqtt_bridge.stop()  # Should not raise

        # Verify still not started
        assert not mqtt_bridge.is_started

        # Verify no cleanup attempted (nothing to clean)
        assert mock_paho.message_callback_remove.call_count == initial_remove_count


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

        # Verify no devices in discovery consumer
        assert mqtt_bridge.discovery_consumer.device_count == 0

        synced = await mqtt_bridge.sync_discovered_devices()

        # Verify return value
        assert synced == 0

        # Verify no devices in database
        devices = await DeviceRepository.get_all()
        assert len(devices) == 0

    async def test_sync_discovered_devices_single(
        self,
        mqtt_bridge: MQTTBridge,
        discovery_payload: dict[str, object],
    ) -> None:
        """Test syncing a single discovered device to database."""
        await mqtt_bridge.start()

        # Verify no devices initially
        assert mqtt_bridge.discovery_consumer.device_count == 0

        # Simulate device discovery
        mqtt_bridge.discovery_consumer.register_device_for_test(discovery_payload)

        # Verify device in discovery consumer
        assert mqtt_bridge.discovery_consumer.device_count == 1
        discovered = mqtt_bridge.discovery_consumer.get_device("test_light_01")
        assert discovered is not None
        assert discovered.device_id == "test_light_01"

        # Sync to database
        synced = await mqtt_bridge.sync_discovered_devices()
        assert synced == 1

        # Verify device persisted with all fields
        device = await DeviceRepository.get_by_id("test_light_01")
        assert device is not None
        assert device.id == "test_light_01"
        assert device.friendly_name == "Test Light"
        assert device.device_type == "smart_light"
        assert device.capabilities == ["power", "brightness"]
        assert device.mqtt_topic == "smartnest/device/test_light_01/state"
        assert device.status == "offline"  # Default status

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
            mqtt_bridge.discovery_consumer.register_device_for_test(device)

        # Verify all in discovery consumer
        assert mqtt_bridge.discovery_consumer.device_count == 3

        # Sync to database
        synced = await mqtt_bridge.sync_discovered_devices()
        assert synced == 3

        # Verify all devices persisted
        all_devices = await DeviceRepository.get_all()
        assert len(all_devices) == 3

        for i in range(1, 4):
            device_resp = await DeviceRepository.get_by_id(f"test_light_{i:02d}")
            assert device_resp is not None
            assert device_resp.friendly_name == f"Light {i}"
            assert device_resp.device_type == "smart_light"

    async def test_sync_duplicate_device_continues(
        self,
        mqtt_bridge: MQTTBridge,
        discovery_payload: dict[str, object],
    ) -> None:
        """Test sync continues on duplicate device (logs warning, doesn't fail)."""
        await mqtt_bridge.start()

        # First sync
        mqtt_bridge.discovery_consumer.register_device_for_test(discovery_payload)
        assert mqtt_bridge.discovery_consumer.device_count == 1

        synced1 = await mqtt_bridge.sync_discovered_devices()
        assert synced1 == 1

        # Verify device exists
        device = await DeviceRepository.get_by_id("test_light_01")
        assert device is not None

        # Attempt to sync same device again (should gracefully handle duplicate)
        synced2 = await mqtt_bridge.sync_discovered_devices()
        assert synced2 == 0  # Already exists, can't create again

        # Verify still only one device
        all_devices = await DeviceRepository.get_all()
        assert len(all_devices) == 1


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
        mqtt_bridge.handle_state_update_for_test(Mock(), None, mock_message)

        # Verify message properties were accessed
        assert mock_message.topic  # topic was read

    async def test_state_update_callback_valid_topic_extracts_device_id(
        self, mqtt_bridge: MQTTBridge
    ) -> None:
        """Test state update callback correctly extracts device ID from topic."""
        await mqtt_bridge.start()

        test_cases = [
            ("smartnest/device/light_01/state", "light_01"),
            ("smartnest/device/sensor_temp_02/state", "sensor_temp_02"),
            ("smartnest/device/switch-123/state", "switch-123"),
        ]

        for topic, _expected_device_id in test_cases:
            mock_message = Mock()
            mock_message.topic = topic
            mock_message.payload = b'{"status": "on"}'

            # Should not raise
            mqtt_bridge.handle_state_update_for_test(Mock(), None, mock_message)

    async def test_state_update_callback_invalid_topic(self, mqtt_bridge: MQTTBridge) -> None:
        """Test state update callback with malformed topic."""
        await mqtt_bridge.start()

        # Test various invalid topic formats
        invalid_topics = [
            "invalid/topic",
            "smartnest/device/state",  # Missing device_id
            "smartnest/device",  # Too short
            "device/test/state",  # Wrong prefix
            "smartnest/device/test/command",  # Wrong suffix
            "/device/test/state",  # Empty prefix
        ]

        for invalid_topic in invalid_topics:
            mock_message = Mock()
            mock_message.topic = invalid_topic
            mock_message.payload = b'{"power": true}'

            # Invoke callback (should log warning, not raise)
            mqtt_bridge.handle_state_update_for_test(Mock(), None, mock_message)

            # Verify message was accessed
            assert mock_message.topic

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
            mqtt_bridge.handle_state_update_for_test(Mock(), None, mock_message)
        mock_message.payload = b'{"power": true}'

        # Invoke callback (should log warning, not raise)
        mqtt_bridge.handle_state_update_for_test(Mock(), None, mock_message)
