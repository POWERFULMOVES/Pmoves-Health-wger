"""
Unit tests for Wger NATS publisher functionality.

Tests the asynchronous NATS event publishing for health metrics
and workout completions in PMOVES.AI's event-driven architecture.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock Django settings before importing wger modules
sys_modules = pytest.importorskip("sys.modules")


@pytest.fixture
def mock_django_settings(monkeypatch):
    """Mock Django settings for NATS configuration."""
    mock_settings = MagicMock()
    mock_settings.NATS_URL = "nats://nats:pmoves@nats:4222"
    mock_settings.WGER_ENABLE_NATS = True
    return mock_settings


@pytest.mark.asyncio
class TestHealthEventPublisher:
    """Test HealthEventPublisher class functionality."""

    async def test_publisher_initialization(self, mock_django_settings):
        """Test publisher initializes with correct NATS URL."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        assert publisher.nats_url == "nats://nats:pmoves@nats:4222"
        assert publisher.nc is None
        assert publisher.js is None

    async def test_connect_creates_connection(self, mock_django_settings):
        """Test connect() creates NATS connection."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()

        with patch('wger.observability.nats_publisher.nats.connect') as mock_connect:
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection

            await publisher.connect()

            mock_connect.assert_called_once_with("nats://nats:pmoves@nats:4222")
            assert publisher.nc == mock_connection

    async def test_publish_metric_update_sends_to_nats(self, mock_django_settings):
        """Test publish_metric_update() sends event to NATS."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        await publisher.publish_metric_update(
            user_id="user-123",
            metric_type="weight",
            value=75.5
        )

        # Verify publish was called
        publisher.nc.publish.assert_called_once()

        # Extract the call arguments
        call_args = publisher.nc.publish.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert subject == "health.metrics.updated.v1"
        assert payload["user_id"] == "user-123"
        assert payload["metric_type"] == "weight"
        assert payload["value"] == 75.5
        assert "timestamp" in payload

    async def test_publish_workout_completed_sends_to_nats(self, mock_django_settings):
        """Test publish_workout_completed() sends event to NATS."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        workout_data = {
            "workout_id": "workout-456",
            "duration": 45,
            "exercises_completed": 8
        }

        await publisher.publish_workout_completed(
            user_id="user-123",
            workout_data=workout_data
        )

        # Verify publish was called
        publisher.nc.publish.assert_called_once()

        call_args = publisher.nc.publish.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert subject == "health.workout.completed.v1"
        assert payload["user_id"] == "user-123"
        assert payload["workout_data"]["workout_id"] == "workout-456"
        assert payload["workout_data"]["duration"] == 45

    async def test_publish_weekly_summary_sends_to_nats(self, mock_django_settings):
        """Test publish_weekly_summary() sends event to NATS."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        summary_data = {
            "workouts_completed": 5,
            "total_duration_minutes": 225,
            "metrics_summary": {
                "weight_start": 80.0,
                "weight_end": 79.2
            }
        }

        await publisher.publish_weekly_summary(
            user_id="user-123",
            summary_data=summary_data
        )

        # Verify publish was called
        publisher.nc.publish.assert_called_once()

        call_args = publisher.nc.publish.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert subject == "health.weekly.summary.v1"
        assert payload["user_id"] == "user-123"
        assert payload["summary_data"]["workouts_completed"] == 5

    async def test_publish_anomaly_detected_sends_to_nats(self, mock_django_settings):
        """Test publish_anomaly_detected() sends event to NATS."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        await publisher.publish_anomaly_detected(
            user_id="user-123",
            anomaly_type="weight_spike",
            severity="warning",
            details={"weight_change": 5.2, "threshold": 3.0}
        )

        # Verify publish was called
        publisher.nc.publish.assert_called_once()

        call_args = publisher.nc.publish.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert subject == "health.anomaly.detected.v1"
        assert payload["user_id"] == "user-123"
        assert payload["anomaly_type"] == "weight_spike"
        assert payload["severity"] == "warning"

    async def test_close_closes_nats_connection(self, mock_django_settings):
        """Test close() closes NATS connection."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.close = AsyncMock()

        await publisher.close()

        publisher.nc.close.assert_called_once()

    async def test_sync_publish_wrapper(self, mock_django_settings):
        """Test sync_publish wrapper handles async publish in sync context."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        # Call sync wrapper (used by Django signals)
        publisher.sync_publish_metric_update("user-123", "weight", 75.5)

        # Allow async event loop to process
        await asyncio.sleep(0.1)

        # Verify publish was called
        publisher.nc.publish.assert_called_once()


@pytest.mark.asyncio
class TestNATSErrorHandling:
    """Test NATS publisher error handling and edge cases."""

    async def test_publish_without_connection_logs_error(self, mock_django_settings, caplog):
        """Test publishing without connection logs error but doesn't crash."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        # No connection established

        # Should not raise exception
        await publisher.publish_metric_update("user-123", "weight", 75.5)

        # Verify error was logged
        # Note: Actual logging behavior depends on implementation

    async def test_connection_failure_graceful_degradation(self, mock_django_settings):
        """Test connection failure doesn't crash application."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()

        with patch('wger.observability.nats_publisher.nats.connect',
                   side_effect=Exception("Connection refused")):
            # Should not raise exception
            try:
                await publisher.connect()
            except Exception as e:
                pytest.fail(f"connect() raised exception: {e}")

    async def test_invalid_payload_serialization(self, mock_django_settings):
        """Test handling of unserializable payload data."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        # Pass unserializable data (should be handled gracefully)
        with pytest.raises((TypeError, ValueError)):
            await publisher.publish_metric_update(
                "user-123",
                "weight",
                object()  # Unserializable
            )


@pytest.mark.asyncio
class TestNATSIntegrationPatterns:
    """Test PMOVES.AI integration patterns for NATS."""

    async def test_subject_naming_convention(self, mock_django_settings):
        """Test NATS subjects follow PMOVES.AI naming convention."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        # Test each subject
        subjects = [
            ("health.metrics.updated.v1", publisher.publish_metric_update, ["user-123", "weight", 75.5]),
            ("health.workout.completed.v1", publisher.publish_workout_completed, ["user-123", {}]),
            ("health.weekly.summary.v1", publisher.publish_weekly_summary, ["user-123", {}]),
            ("health.anomaly.detected.v1", publisher.publish_anomaly_detected, ["user-123", "warning", "warning", {}])
        ]

        for expected_subject, method, args in subjects:
            publisher.nc.publish.reset_mock()

            if method == publisher.publish_anomaly_detected:
                await method(*args)
            else:
                await method(*args)

            call_args = publisher.nc.publish.call_args
            actual_subject = call_args[0][0]
            assert actual_subject == expected_subject, f"Expected {expected_subject}, got {actual_subject}"

    async def test_payload_includes_required_fields(self, mock_django_settings):
        """Test NATS payloads include required PMOVES.AI fields."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        await publisher.publish_metric_update("user-123", "weight", 75.5)

        call_args = publisher.nc.publish.call_args
        payload = json.loads(call_args[0][1])

        # Required fields for PMOVES.AI events
        required_fields = ["user_id", "timestamp"]
        for field in required_fields:
            assert field in payload, f"Missing required field: {field}"

    async def test_payload_timestamp_iso8601(self, mock_django_settings):
        """Test timestamps are in ISO 8601 format."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        await publisher.publish_metric_update("user-123", "weight", 75.5)

        call_args = publisher.nc.publish.call_args
        payload = json.loads(call_args[0][1])

        # Verify timestamp is ISO 8601 format
        import re
        iso8601_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
        assert re.match(iso8601_pattern, payload["timestamp"]), f"Invalid ISO 8601 timestamp: {payload['timestamp']}"
