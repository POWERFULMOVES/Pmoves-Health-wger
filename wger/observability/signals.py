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
from wger.measurements.models import Measurement, BodyFat

from .nats_publisher import sync_publish_metric_update, sync_publish_workout_completed

logger = logging.getLogger(__name__)

User = get_user_model()


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
        # Calculate duration if not set
        duration_seconds = 0
        if instance.duration:
            duration_seconds = instance.duration

        # Count exercises in workout
        exercises_completed = 0
        if hasattr(instance, 'workout') and instance.workout:
            exercises_completed = instance.workout.exercise_set.count()

        # Get workout date
        workout_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        # Publish to NATS
        success = sync_publish_workout_completed(
            user_id=instance.user.id,
            workout_id=instance.workout.id if hasattr(instance, 'workout') and instance.workout else str(instance.id),
            duration_seconds=int(duration_seconds),
            exercises_completed=exercises_completed,
            date=workout_date,
            metadata={
                "workout_log_id": str(instance.id),
                "impression": instance.impression if hasattr(instance, 'impression') else None,
                "notes": instance.notes if hasattr(instance, 'notes') else None,
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
        # Calculate duration
        duration_seconds = 0
        if instance.duration:
            duration_seconds = instance.duration

        # Get session date
        session_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        # Publish session completion
        success = sync_publish_workout_completed(
            user_id=instance.user.id,
            workout_id=instance.workout.id if hasattr(instance, 'workout') and instance.workout else str(instance.id),
            duration_seconds=int(duration_seconds),
            exercises_completed=0,  # Session doesn't track exercise count directly
            date=session_date,
            metadata={
                "workout_session_id": str(instance.id),
                "session_type": "session",
                "notes": instance.notes if hasattr(instance, 'notes') else None,
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
                "notes": instance.notes if hasattr(instance, 'notes') else None,
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

        success = sync_publish_metric_update(
            user_id=instance.user.id,
            metric_type="measurement",
            value={
                "category": instance.category.name if hasattr(instance, 'category') and instance.category else "unknown",
                "value": float(instance.value) if instance.value else 0,
            },
            unit=instance.unit if hasattr(instance, 'unit') and instance.unit else "cm",
            metadata={
                "measurement_id": str(instance.id),
                "date": measurement_date,
                "notes": instance.notes if hasattr(instance, 'notes') else None,
            }
        )

        if success:
            logger.info(f"Published measurement update for user {instance.user.id}: {instance.category.name if hasattr(instance, 'category') and instance.category else 'unknown'}")

    except Exception as e:
        logger.error(f"Failed to publish measurement update event: {e}")


@receiver(post_save, sender=BodyFat)
def body_fat_handler(sender, instance, created, **kwargs):
    """
    Publish body fat percentage update to NATS.

    Triggered when a body fat measurement is created or updated.

    Args:
        sender: BodyFat model class
        instance: BodyFat instance that was saved
        created: True if new instance, False if update
    """
    try:
        entry_date = instance.date.isoformat() if instance.date else datetime.now().isoformat()

        success = sync_publish_metric_update(
            user_id=instance.user.id,
            metric_type="body_fat",
            value=float(instance.fat) if instance.fat else 0,
            unit="%",
            metadata={
                "body_fat_id": str(instance.id),
                "date": entry_date,
                "notes": instance.notes if hasattr(instance, 'notes') else None,
            }
        )

        if success:
            logger.info(f"Published body fat update for user {instance.user.id}: {instance.fat}%")

    except Exception as e:
        logger.error(f"Failed to publish body fat update event: {e}")


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
