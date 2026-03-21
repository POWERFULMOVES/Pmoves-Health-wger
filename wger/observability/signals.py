"""
Django Signal Handlers for PMOVES-Health-wger

This module connects Django model signals to NATS event publishing,
enabling real-time event-driven integration with PMOVES.AI.

When health metrics or workouts are saved/updated, these signal handlers
automatically publish events to NATS subjects for downstream processing.

Usage:
    Signal handlers are automatically registered when the observability app
    is loaded. No manual registration required.

Connected Models:
    - WorkoutLog: Workout session completion events
    - UserProfile: User profile updates
    - WeightEntry: Body weight measurements
    - Measurement: Body measurements (chest, waist, etc.)
    - BodyFat: Body fat percentage measurements

Environment Variables:
    WGER_ENABLE_NATS: Enable/disable NATS publishing (default: true)
"""

import logging
from datetime import datetime

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from wger.core.models import UserProfile
from wger.weight.models import WeightEntry
from wger.manager.models import WorkoutLog, WorkoutSession
from wger.measurements.models import Measurement

from .nats_publisher import sync_publish_metric_update, sync_publish_workout_completed

logger = logging.getLogger(__name__)

User = get_user_model()


# Export signal handlers for testing and external access
__all__ = [
    'workout_completed_handler',
    'user_profile_handler',
    'weight_entry_handler',
    'measurement_handler',
    'workout_session_handler',
]


@receiver(post_save, sender=WorkoutLog)
def workout_completed_handler(sender, instance, created, **kwargs):
    """
    Publish workout completion event to NATS.

    Triggered when a new workout log is created, indicating a workout
    session was completed.

    Args:
        sender: WorkoutLog model class
        instance: WorkoutLog instance that was saved
        created: True if new instance, False if update
    """
    if not created:
        logger.debug(f"WorkoutLog updated (not created), skipping NATS publish: {instance.id}")
        return

    try:
        # WorkoutLog has no duration field; use rest time as proxy or default to 0
        duration_seconds = getattr(instance, 'rest', 0) or 0

        # Count exercises via routine (WorkoutLog has routine FK, not workout)
        exercises_completed = 0
        if instance.routine:
            exercises_completed = 1  # Each WorkoutLog is one exercise entry

        # Get workout date
        workout_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        # Publish to NATS
        success = sync_publish_workout_completed(
            user_id=instance.user.id,
            workout_id=str(instance.routine_id) if instance.routine_id else str(instance.id),
            duration_seconds=int(duration_seconds),
            exercises_completed=exercises_completed,
            date=workout_date,
            metadata={
                "workout_log_id": str(instance.id),
                "exercise_id": str(instance.exercise_id) if instance.exercise_id else None,
                "session_id": str(instance.session_id) if instance.session_id else None,
            }
        )

        if success:
            logger.info(f"Published workout completion event for user {instance.user.id}, workout {instance.id}")

    except Exception as e:
        logger.error(f"Failed to publish workout completion event: {e}")


@receiver(post_save, sender=WorkoutSession)
def workout_session_handler(sender, instance, created, **kwargs):
    """
    Publish workout session updates to NATS.

    Triggered when a workout session is created or updated.

    Args:
        sender: WorkoutSession model class
        instance: WorkoutSession instance that was saved
        created: True if new instance, False if update
    """
    try:
        # Calculate duration from time_start and time_end
        duration_seconds = 0
        if instance.time_start and instance.time_end:
            start_dt = datetime.combine(instance.date or datetime.now().date(), instance.time_start)
            end_dt = datetime.combine(instance.date or datetime.now().date(), instance.time_end)
            duration_seconds = max(0, int((end_dt - start_dt).total_seconds()))

        # Get session date
        session_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        # Publish session completion
        success = sync_publish_workout_completed(
            user_id=instance.user.id,
            workout_id=str(instance.routine_id) if instance.routine_id else str(instance.id),
            duration_seconds=duration_seconds,
            exercises_completed=0,  # Session doesn't track exercise count directly
            date=session_date,
            metadata={
                "workout_session_id": str(instance.id),
                "session_type": "session",
                "impression": instance.impression if instance.impression else None,
                "notes": instance.notes if instance.notes else None,
            }
        )

        if success:
            logger.info(f"Published workout session event for user {instance.user.id}, session {instance.id}")

    except Exception as e:
        logger.error(f"Failed to publish workout session event: {e}")


@receiver(post_save, sender=WeightEntry)
def weight_entry_handler(sender, instance, created, **kwargs):
    """
    Publish weight measurement update to NATS.

    Triggered when a weight entry is created or updated.

    Args:
        sender: WeightEntry model class
        instance: WeightEntry instance that was saved
        created: True if new instance, False if update
    """
    try:
        weight_kg = instance.weight
        entry_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        success = sync_publish_metric_update(
            user_id=instance.user.id,
            metric_type="weight",
            value=weight_kg,
            unit="kg",
            metadata={
                "weight_entry_id": str(instance.id),
                "date": entry_date,
            }
        )

        if success:
            logger.info(f"Published weight update for user {instance.user.id}: {weight_kg} kg")

    except Exception as e:
        logger.error(f"Failed to publish weight update event: {e}")


@receiver(post_save, sender=Measurement)
def measurement_handler(sender, instance, created, **kwargs):
    """
    Publish body measurement update to NATS.

    Triggered when a body measurement (chest, waist, etc.) is created or updated.

    Args:
        sender: Measurement model class
        instance: Measurement instance that was saved
        created: True if new instance, False if update
    """
    try:
        measurement_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        # Measurement user is accessed via category FK (Measurement → Category → User)
        user_id = instance.category.user_id if instance.category else None
        if not user_id:
            logger.warning(f"Measurement {instance.id} has no category/user, skipping NATS publish")
            return

        category_name = instance.category.name if instance.category else "unknown"

        success = sync_publish_metric_update(
            user_id=user_id,
            metric_type="measurement",
            value={
                "category": category_name,
                "value": float(instance.value) if instance.value else 0,
            },
            unit=getattr(instance.category, 'unit', 'cm') if instance.category else "cm",
            metadata={
                "measurement_id": str(instance.id),
                "date": measurement_date,
                "notes": instance.notes if instance.notes else None,
            }
        )

        if success:
            logger.info(f"Published measurement update for user {user_id}: {category_name}")

    except Exception as e:
        logger.error(f"Failed to publish measurement update event: {e}")



@receiver(post_save, sender=UserProfile)
def user_profile_handler(sender, instance, created, **kwargs):
    """
    Publish user profile updates to NATS.

    Triggered when user profile metadata is updated.

    Args:
        sender: UserProfile model class
        instance: UserProfile instance that was saved
        created: True if new instance, False if update
    """
    # Only publish on updates, not creation
    if created:
        logger.debug(f"UserProfile created (not updated), skipping NATS publish: {instance.user.id}")
        return

    try:
        # Publish profile update as generic metric
        success = sync_publish_metric_update(
            user_id=instance.user.id,
            metric_type="profile_update",
            value={
                "height": float(instance.height) if instance.height else None,
                "weight_unit": instance.weight_unit if hasattr(instance, 'weight_unit') else 'kg',
            },
            unit=None,
            metadata={
                "user_profile_id": str(instance.id),
                "update_type": "profile",
            }
        )

        if success:
            logger.info(f"Published user profile update for user {instance.user.id}")

    except Exception as e:
        logger.error(f"Failed to publish user profile update event: {e}")


# Signal handler connection confirmation
logger.info("PMOVES-Health-wger signal handlers registered for NATS event publishing")
