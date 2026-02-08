"""Unit tests for SmartNest MQTT topic builder."""

from __future__ import annotations

import pytest

from backend.mqtt.topics import TopicBuilder, validate_device_id


class TestValidateDeviceId:
    """Tests for the validate_device_id helper."""

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_device_id("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="whitespace-only"):
            validate_device_id("   ")

    def test_contains_plus_wildcard(self) -> None:
        with pytest.raises(ValueError, match="invalid MQTT characters"):
            validate_device_id("light+01")

    def test_contains_hash_wildcard(self) -> None:
        with pytest.raises(ValueError, match="invalid MQTT characters"):
            validate_device_id("light#01")

    def test_contains_slash(self) -> None:
        with pytest.raises(ValueError, match="invalid MQTT characters"):
            validate_device_id("light/01")

    def test_valid_device_id(self) -> None:
        validate_device_id("light_01")  # should not raise

    def test_valid_device_id_with_hyphens(self) -> None:
        validate_device_id("temp-sensor-01")  # should not raise


class TestTopicBuilderDeviceTopic:
    """Tests for TopicBuilder.device_topic()."""

    def test_command_topic(self) -> None:
        result = TopicBuilder.device_topic("light_01", "command")
        assert result == "smartnest/device/light_01/command"

    def test_state_topic(self) -> None:
        result = TopicBuilder.device_topic("light_01", "state")
        assert result == "smartnest/device/light_01/state"

    def test_status_topic(self) -> None:
        result = TopicBuilder.device_topic("light_01", "status")
        assert result == "smartnest/device/light_01/status"

    def test_invalid_device_id_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            TopicBuilder.device_topic("", "command")


class TestTopicBuilderSensorTopic:
    """Tests for TopicBuilder.sensor_topic()."""

    def test_sensor_data_topic(self) -> None:
        result = TopicBuilder.sensor_topic("temp_01")
        assert result == "smartnest/sensor/temp_01/data"

    def test_invalid_device_id_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            TopicBuilder.sensor_topic("")


class TestTopicBuilderStaticTopics:
    """Tests for discovery and system topics."""

    def test_discovery_topic(self) -> None:
        assert TopicBuilder.discovery_topic() == "smartnest/discovery/announce"

    def test_system_event_topic(self) -> None:
        assert TopicBuilder.system_topic() == "smartnest/system/event"

    def test_system_topic_explicit_event(self) -> None:
        assert TopicBuilder.system_topic("event") == "smartnest/system/event"


class TestTopicBuilderWildcards:
    """Tests for wildcard subscription helpers."""

    def test_device_command_wildcard(self) -> None:
        assert TopicBuilder.device_wildcard("command") == "smartnest/device/+/command"

    def test_device_state_wildcard(self) -> None:
        assert TopicBuilder.device_wildcard("state") == "smartnest/device/+/state"

    def test_device_status_wildcard(self) -> None:
        assert TopicBuilder.device_wildcard("status") == "smartnest/device/+/status"

    def test_sensor_wildcard(self) -> None:
        assert TopicBuilder.sensor_wildcard() == "smartnest/sensor/+/data"

    def test_all_devices_wildcard(self) -> None:
        assert TopicBuilder.all_devices_wildcard() == "smartnest/device/#"


class TestTopicBuilderPrefix:
    """Verify the prefix constant is used consistently."""

    def test_prefix_value(self) -> None:
        assert TopicBuilder.PREFIX == "smartnest"

    def test_all_topics_start_with_prefix(self) -> None:
        topics = [
            TopicBuilder.device_topic("d1", "command"),
            TopicBuilder.device_topic("d1", "state"),
            TopicBuilder.device_topic("d1", "status"),
            TopicBuilder.sensor_topic("s1"),
            TopicBuilder.discovery_topic(),
            TopicBuilder.system_topic(),
            TopicBuilder.device_wildcard("state"),
            TopicBuilder.sensor_wildcard(),
            TopicBuilder.all_devices_wildcard(),
        ]
        for topic in topics:
            assert topic.startswith("smartnest/"), f"{topic} missing prefix"
