"""
Unit tests for Wger NATS publisher functionality.

Tests the asynchronous NATS event publishing for health metrics
and workout completions in PMOVES.AI's event-driven architecture.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_django_settings(monkeypatch):
    """Mock Django settings for NATS configuration."""
    mock_settings = MagicMock()
    mock_settings.NATS_URL = "nats://nats:pmoves@nats:4222"
    mock_settings.WGER_ENABLE_NATS = True
    monkeypatch.setattr('wger.observability.nats_publisher.settings', mock_settings)
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

        publisher.nc.publish.assert_called_once()

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

        await publisher.publish_workout_completed(
            user_id="user-123",
            workout_id="workout-456",
            duration_seconds=2700,
            exercises_completed=8,
            date="2026-03-21",
        )

        publisher.nc.publish.assert_called_once()

        call_args = publisher.nc.publish.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert subject == "health.workout.completed.v1"
        assert payload["user_id"] == "user-123"
        assert payload["workout_id"] == "workout-456"
        assert payload["duration_seconds"] == 2700
        assert payload["exercises_completed"] == 8

    async def test_publish_weekly_summary_sends_to_nats(self, mock_django_settings):
        """Test publish_weekly_summary() sends event to NATS."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        await publisher.publish_weekly_summary(
            user_id="user-123",
            week_start="2026-03-17",
            workouts_completed=5,
            total_duration_minutes=225,
            metrics_summary={"weight_start": 80.0, "weight_end": 79.2},
        )

        publisher.nc.publish.assert_called_once()

        call_args = publisher.nc.publish.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert subject == "health.weekly.summary.v1"
        assert payload["user_id"] == "user-123"
        assert payload["workouts_completed"] == 5

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
            description="Unusual weight change detected",
            affected_metrics={"weight_change": 5.2, "threshold": 3.0},
        )

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


@pytest.mark.asyncio
class TestNATSErrorHandling:
    """Test NATS publisher error handling and edge cases."""

    async def test_publish_without_connection_returns_false(self, mock_django_settings):
        """Test publishing without connection returns False."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()

        result = await publisher.publish_metric_update("user-123", "weight", 75.5)
        assert result is False

    async def test_connection_failure_graceful_degradation(self, mock_django_settings):
        """Test connection failure doesn't crash application."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()

        with patch('wger.observability.nats_publisher.nats.connect',
                   side_effect=Exception("Connection refused")):
            await publisher.connect()

        assert publisher.nc is None

    async def test_disabled_publisher_skips_publish(self, mock_django_settings):
        """Test disabled publisher skips connection and publish."""
        mock_django_settings.WGER_ENABLE_NATS = False

        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.enabled = False

        await publisher.connect()
        assert publisher.nc is None

        result = await publisher.publish_metric_update("user-123", "weight", 75.5)
        assert result is False


@pytest.mark.asyncio
class TestNATSIntegrationPatterns:
    """Test PMOVES.AI integration patterns for NATS."""

    async def test_subject_naming_convention(self, mock_django_settings):
        """Test NATS subjects follow PMOVES.AI naming convention."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        test_cases = [
            ("health.metrics.updated.v1", publisher.publish_metric_update,
             {"user_id": "u1", "metric_type": "weight", "value": 75.5}),
            ("health.workout.completed.v1", publisher.publish_workout_completed,
             {"user_id": "u1", "workout_id": "w1", "duration_seconds": 0,
              "exercises_completed": 0, "date": "2026-01-01"}),
            ("health.weekly.summary.v1", publisher.publish_weekly_summary,
             {"user_id": "u1", "week_start": "2026-01-01", "workouts_completed": 0,
              "total_duration_minutes": 0, "metrics_summary": {}}),
            ("health.anomaly.detected.v1", publisher.publish_anomaly_detected,
             {"user_id": "u1", "anomaly_type": "spike", "severity": "low",
              "description": "test", "affected_metrics": {}}),
        ]

        for expected_subject, method, kwargs in test_cases:
            publisher.nc.publish.reset_mock()
            await method(**kwargs)
            call_args = publisher.nc.publish.call_args
            actual_subject = call_args[0][0]
            assert actual_subject == expected_subject, (
                f"Expected {expected_subject}, got {actual_subject}"
            )

    async def test_payload_includes_required_fields(self, mock_django_settings):
        """Test NATS payloads include required PMOVES.AI fields."""
        from wger.observability.nats_publisher import HealthEventPublisher

        publisher = HealthEventPublisher()
        publisher.nc = AsyncMock()
        publisher.nc.publish = AsyncMock()

        await publisher.publish_metric_update("user-123", "weight", 75.5)

        call_args = publisher.nc.publish.call_args
        payload = json.loads(call_args[0][1])

        for field in ["user_id", "timestamp"]:
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

        import re
        iso8601_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
        assert re.match(iso8601_pattern, payload["timestamp"]), (
            f"Invalid ISO 8601 timestamp: {payload['timestamp']}"
        )
