"""
NATS Event Publisher for PMOVES-Health-wger

This module provides asynchronous event publishing to NATS for health metrics,
workout completions, and weekly summaries. It integrates with PMOVES.AI's
event-driven architecture for cross-domain workflows.

Usage:
    from wger.observability.nats_publisher import HealthEventPublisher

    publisher = HealthEventPublisher()
    await publisher.connect()
    await publisher.publish_metric_update(user_id, "weight", 75.5)

NATS Subjects:
    - health.metrics.updated.v1: Body metrics updated (weight, body fat, measurements)
    - health.workout.completed.v1: Workout session completed
    - health.weekly.summary.v1: Weekly fitness summary
    - health.anomaly.detected.v1: Anomaly detection alerts

Environment Variables:
    NATS_URL: NATS connection URL (default: nats://nats:pmoves@nats:4222)
    WGER_ENABLE_NATS: Enable/disable NATS publishing (default: true)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import nats
from django.conf import settings

logger = logging.getLogger(__name__)


# CHIT sensitivity classification (Phase 4, TAC_HEALTH.md).
# delta_sensitive gates magnitude/threshold ("how much changed") anomalies;
# hz_sensitive gates frequency/cadence ("how often") anomalies. Anomaly types not
# listed here are unclassified and always pass the gate (fail-open) so a new type
# is never silently dropped before it is classified.
DELTA_ANOMALY_TYPES = frozenset({
    "weight_spike",
    "weight_drop",
    "body_fat_delta",
    "measurement_jump",
    "metric_threshold",
})
HZ_ANOMALY_TYPES = frozenset({
    "missing_data",
    "logging_gap",
    "workout_cadence",
    "frequency_drop",
    "frequency_spike",
})


class HealthEventPublisher:
    """
    Asynchronous NATS event publisher for health data.

    This publisher connects to NATS and emits events for health metrics
    and workout completions. It's used by Django signal handlers to
    publish events in real-time.
    """

    def __init__(self):
        """Initialize the publisher with NATS URL from settings."""
        self.nc: Optional[nats.aio.client.Client] = None
        self.js: Optional[nats.aio.jetstream.JetStreamContext] = None

        # Get NATS URL from environment or use default with authentication
        self.nats_url = getattr(settings, 'NATS_URL', 'nats://nats:pmoves@nats:4222')

        # Check if NATS is enabled
        self.enabled = getattr(settings, 'WGER_ENABLE_NATS', True)

        # CHIT sensitivity toggles (Phase 4, TAC_HEALTH.md).
        # delta_sensitive gates magnitude/threshold anomalies (e.g. weight_spike);
        # hz_sensitive gates frequency/cadence anomalies (e.g. missing_data).
        # When a toggle is False, anomalies of that class are suppressed at the
        # publish boundary rather than emitted to health.anomaly.detected.v1.
        self.delta_sensitive = getattr(settings, 'WGER_CHIT_DELTA_SENSITIVE', True)
        self.hz_sensitive = getattr(settings, 'WGER_CHIT_HZ_SENSITIVE', True)

        # Subject versioning
        self.subject_version = "v1"

    async def connect(self) -> None:
        """
        Connect to NATS server.

        Raises:
            nats.errors.Error: If connection fails
        """
        if not self.enabled:
            logger.info("NATS publishing is disabled (WGER_ENABLE_NATS=false)")
            return

        try:
            self.nc = await nats.connect(self.nats_url)
            logger.info(f"Connected to NATS at {self.nats_url}")

            # Initialize JetStream for durable subscriptions
            self.js = self.nc.jetstream()

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            # Don't raise - allow application to run without NATS
            self.nc = None

    async def close(self) -> None:
        """Close NATS connection."""
        if self.nc:
            try:
                await self.nc.close()
                logger.info("NATS connection closed")
            except Exception as e:
                logger.error(f"Error closing NATS connection: {e}")

    async def publish(self, subject: str, payload: Dict[str, Any]) -> bool:
        """
        Publish event to NATS subject.

        Args:
            subject: NATS subject (e.g., "health.metrics.updated.v1")
            payload: Event data dictionary

        Returns:
            True if published successfully, False otherwise
        """
        if not self.enabled or not self.nc:
            logger.debug(f"NATS disabled or not connected, skipping {subject}")
            return False

        try:
            # Add timestamp if not present
            if 'timestamp' not in payload:
                payload['timestamp'] = datetime.utcnow().isoformat()

            # Serialize to JSON
            message = json.dumps(payload).encode()

            # Publish to NATS
            await self.nc.publish(subject, message)

            logger.debug(f"Published to {subject}: {payload.get('user_id', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            return False

    async def publish_metric_update(
        self,
        user_id: str,
        metric_type: str,
        value: Any,
        unit: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish health metric update event.

        Args:
            user_id: User UUID
            metric_type: Type of metric (weight, body_fat, measurement, etc.)
            value: Metric value
            unit: Unit of measurement (kg, %, cm, etc.)
            metadata: Additional metadata (date, notes, etc.)

        Returns:
            True if published successfully
        """
        subject = f"health.metrics.updated.{self.subject_version}"

        payload = {
            "user_id": str(user_id),
            "metric_type": metric_type,
            "value": value,
            "unit": unit,
            "metadata": metadata or {}
        }

        return await self.publish(subject, payload)

    async def publish_workout_completed(
        self,
        user_id: str,
        workout_id: str,
        duration_seconds: int,
        exercises_completed: int,
        date: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish workout completion event.

        Args:
            user_id: User UUID
            workout_id: Workout session UUID
            duration_seconds: Workout duration in seconds
            exercises_completed: Number of exercises completed
            date: Workout date (ISO8601)
            metadata: Additional metadata (notes, intensity, etc.)

        Returns:
            True if published successfully
        """
        subject = f"health.workout.completed.{self.subject_version}"

        payload = {
            "user_id": str(user_id),
            "workout_id": str(workout_id),
            "duration_seconds": duration_seconds,
            "exercises_completed": exercises_completed,
            "date": date,
            "metadata": metadata or {}
        }

        return await self.publish(subject, payload)

    async def publish_weekly_summary(
        self,
        user_id: str,
        week_start: str,
        workouts_completed: int,
        total_duration_minutes: int,
        metrics_summary: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish weekly fitness summary event.

        Args:
            user_id: User UUID
            week_start: Week start date (ISO8601)
            workouts_completed: Number of workouts completed
            total_duration_minutes: Total workout duration in minutes
            metrics_summary: Summary of health metrics (weight, body fat, etc.)
            metadata: Additional metadata (goals, adherence, etc.)

        Returns:
            True if published successfully
        """
        subject = f"health.weekly.summary.{self.subject_version}"

        payload = {
            "user_id": str(user_id),
            "week_start": week_start,
            "workouts_completed": workouts_completed,
            "total_duration_minutes": total_duration_minutes,
            "metrics_summary": metrics_summary,
            "metadata": metadata or {}
        }

        return await self.publish(subject, payload)

    def chit_gate_allows(self, anomaly_type: str) -> bool:
        """
        CHIT sensitivity gate for anomaly publishing (Phase 4).

        Returns False when the relevant sensitivity toggle is disabled, which
        suppresses the anomaly before it reaches the event bus:
          - magnitude/threshold anomalies (DELTA_ANOMALY_TYPES) are gated by
            ``delta_sensitive``
          - frequency/cadence anomalies (HZ_ANOMALY_TYPES) are gated by
            ``hz_sensitive``
          - unclassified anomaly types always pass (fail-open) so a new type is
            never silently dropped before it is classified.

        Args:
            anomaly_type: Type of anomaly (e.g. "weight_spike", "missing_data")

        Returns:
            True if the anomaly may be published, False if CHIT-suppressed.
        """
        if anomaly_type in DELTA_ANOMALY_TYPES:
            return self.delta_sensitive
        if anomaly_type in HZ_ANOMALY_TYPES:
            return self.hz_sensitive
        return True

    async def publish_anomaly_detected(
        self,
        user_id: str,
        anomaly_type: str,
        severity: str,
        description: str,
        affected_metrics: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish health anomaly detection event.

        Honours the CHIT sensitivity gate (Phase 4): if the relevant toggle
        (``delta_sensitive`` / ``hz_sensitive``) is disabled for this
        ``anomaly_type``, the event is suppressed and not published.

        Args:
            user_id: User UUID
            anomaly_type: Type of anomaly (weight_spike, missing_data, etc.)
            severity: Severity level (low, medium, high, critical)
            description: Human-readable description
            affected_metrics: Metrics affected by anomaly
            metadata: Additional metadata (suggested actions, etc.)

        Returns:
            True if published successfully, False if not (disabled, disconnected,
            or CHIT-suppressed by the sensitivity gate).
        """
        if not self.chit_gate_allows(anomaly_type):
            logger.info(
                "CHIT gate suppressed '%s' anomaly "
                "(delta_sensitive=%s, hz_sensitive=%s)",
                anomaly_type, self.delta_sensitive, self.hz_sensitive,
            )
            return False

        subject = f"health.anomaly.detected.{self.subject_version}"

        payload = {
            "user_id": str(user_id),
            "anomaly_type": anomaly_type,
            "severity": severity,
            "description": description,
            "affected_metrics": affected_metrics,
            "metadata": metadata or {}
        }

        return await self.publish(subject, payload)


# Singleton instance for use in signal handlers
_publisher_instance: Optional[HealthEventPublisher] = None


async def get_publisher() -> HealthEventPublisher:
    """
    Get or create singleton publisher instance.

    Returns:
        HealthEventPublisher instance
    """
    global _publisher_instance

    if _publisher_instance is None:
        _publisher_instance = HealthEventPublisher()
        await _publisher_instance.connect()

    return _publisher_instance


def sync_publish_metric_update(
    user_id: str,
    metric_type: str,
    value: Any,
    unit: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Synchronous wrapper for publish_metric_update (for use in Django signals).

    This properly handles async publishing from Django signal handlers.
    Uses fire-and-forget pattern with error logging.

    Args:
        user_id: User UUID
        metric_type: Type of metric
        value: Metric value
        unit: Unit of measurement
        metadata: Additional metadata

    Returns:
        True if task was scheduled (not necessarily delivered)
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Fire-and-forget: create task without waiting
            # Get publisher coroutine and schedule it
            async def _publish():
                pub = await get_publisher()
                return await pub.publish_metric_update(
                    user_id, metric_type, value, unit, metadata
                )

            task = loop.create_task(_publish())

            # Add error callback to log failures
            def _log_error(task):
                try:
                    error = task.exception()
                    if error:
                        logger.error(f"NATS publish task failed: {error}")
                except asyncio.CancelledError:
                    pass

            task.add_done_callback(_log_error)
            return True
        else:
            # No loop running, run synchronously
            async def _publish():
                pub = await get_publisher()
                return await pub.publish_metric_update(
                    user_id, metric_type, value, unit, metadata
                )

            loop.run_until_complete(_publish())
            return True
    except Exception as e:
        logger.error(f"Failed to sync publish metric update: {e}")
        return False


def sync_publish_workout_completed(
    user_id: str,
    workout_id: str,
    duration_seconds: int,
    exercises_completed: int,
    date: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Synchronous wrapper for publish_workout_completed (for use in Django signals).

    Args:
        user_id: User UUID
        workout_id: Workout session UUID
        duration_seconds: Workout duration in seconds
        exercises_completed: Number of exercises completed
        date: Workout date (ISO8601)
        metadata: Additional metadata

    Returns:
        True if published successfully
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Fire-and-forget: create task without waiting
            # Get publisher coroutine and schedule it
            async def _publish():
                pub = await get_publisher()
                return await pub.publish_workout_completed(
                    user_id, workout_id, duration_seconds,
                    exercises_completed, date, metadata
                )

            task = loop.create_task(_publish())

            # Add error callback to log failures
            def _log_error(task):
                try:
                    error = task.exception()
                    if error:
                        logger.error(f"NATS publish workout task failed: {error}")
                except asyncio.CancelledError:
                    pass

            task.add_done_callback(_log_error)
            return True
        else:
            # No loop running, run synchronously
            async def _publish():
                pub = await get_publisher()
                return await pub.publish_workout_completed(
                    user_id, workout_id, duration_seconds,
                    exercises_completed, date, metadata
                )

            loop.run_until_complete(_publish())
            return True
    except Exception as e:
        logger.error(f"Failed to sync publish workout completed: {e}")
        return False
