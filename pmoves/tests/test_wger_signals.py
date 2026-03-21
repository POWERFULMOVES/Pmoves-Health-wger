"""
Unit tests for Wger Django signal handlers.

Tests the automatic NATS event publishing triggered by Django
model saves for workouts, measurements, and user profiles.
"""

import pytest
from datetime import datetime, date, time
from unittest.mock import MagicMock, patch


@pytest.mark.django_db
class TestWorkoutSignals:
    """Test Django signal handlers for workout events."""

    def test_workout_log_save_triggers_nats_publish(self):
        """Test saving WorkoutLog triggers NATS workout completion publish."""
        with patch(
            'wger.observability.signals.sync_publish_workout_completed'
        ) as mock_publish:
            mock_publish.return_value = True

            # Create mock WorkoutLog instance to trigger post_save signal
            from wger.observability.signals import workout_completed_handler

            instance = MagicMock()
            instance.id = 1
            instance.user.id = 42
            instance.routine_id = 10
            instance.exercise_id = 5
            instance.session_id = 3
            instance.rest = 60
            instance.date = date.today()

            workout_completed_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args[1]
            assert call_kwargs['user_id'] == 42
            assert call_kwargs['workout_id'] == '10'

    def test_workout_log_update_skips_publish(self):
        """Test updating (not creating) WorkoutLog skips NATS publish."""
        with patch(
            'wger.observability.signals.sync_publish_workout_completed'
        ) as mock_publish:
            from wger.observability.signals import workout_completed_handler

            instance = MagicMock()
            workout_completed_handler(
                sender=MagicMock(), instance=instance, created=False
            )

            mock_publish.assert_not_called()

    def test_workout_session_save_triggers_nats_publish(self):
        """Test saving WorkoutSession triggers NATS publish with duration."""
        with patch(
            'wger.observability.signals.sync_publish_workout_completed'
        ) as mock_publish:
            mock_publish.return_value = True

            from wger.observability.signals import workout_session_handler

            instance = MagicMock()
            instance.id = 1
            instance.user.id = 42
            instance.routine_id = 10
            instance.date = date.today()
            instance.time_start = time(9, 0)
            instance.time_end = time(9, 45)
            instance.impression = 'good'
            instance.notes = 'Great session'

            workout_session_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args[1]
            assert call_kwargs['user_id'] == 42
            assert call_kwargs['duration_seconds'] == 2700  # 45 minutes


@pytest.mark.django_db
class TestWeightSignals:
    """Test Django signal handlers for weight tracking."""

    def test_weight_entry_save_triggers_nats_publish(self):
        """Test saving WeightEntry triggers NATS metric update."""
        with patch(
            'wger.observability.signals.sync_publish_metric_update'
        ) as mock_publish:
            mock_publish.return_value = True

            from wger.observability.signals import weight_entry_handler

            instance = MagicMock()
            instance.id = 1
            instance.user.id = 42
            instance.weight = 75.5
            instance.date = date.today()

            weight_entry_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args[1]
            assert call_kwargs['user_id'] == 42
            assert call_kwargs['metric_type'] == 'weight'
            assert call_kwargs['value'] == 75.5
            assert call_kwargs['unit'] == 'kg'


@pytest.mark.django_db
class TestMeasurementSignals:
    """Test Django signal handlers for body measurements."""

    def test_measurement_save_triggers_nats_publish(self):
        """Test saving Measurement triggers NATS metric update."""
        with patch(
            'wger.observability.signals.sync_publish_metric_update'
        ) as mock_publish:
            mock_publish.return_value = True

            from wger.observability.signals import measurement_handler

            # Measurement user is via category FK: Measurement → Category → User
            instance = MagicMock()
            instance.id = 1
            instance.category.user_id = 42
            instance.category.name = 'Chest'
            instance.category.unit = 'cm'
            instance.value = 100.5
            instance.date = date.today()
            instance.notes = ''

            measurement_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args[1]
            assert call_kwargs['user_id'] == 42
            assert call_kwargs['metric_type'] == 'measurement'

    def test_measurement_without_category_skips_publish(self):
        """Test Measurement without category skips NATS publish."""
        with patch(
            'wger.observability.signals.sync_publish_metric_update'
        ) as mock_publish:
            from wger.observability.signals import measurement_handler

            instance = MagicMock()
            instance.id = 1
            instance.category = None
            instance.date = date.today()

            measurement_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            mock_publish.assert_not_called()


@pytest.mark.django_db
class TestUserProfileSignals:
    """Test Django signal handlers for user profile updates."""

    def test_user_profile_update_triggers_nats_publish(self):
        """Test updating user profile triggers NATS publish."""
        with patch(
            'wger.observability.signals.sync_publish_metric_update'
        ) as mock_publish:
            mock_publish.return_value = True

            from wger.observability.signals import user_profile_handler

            instance = MagicMock()
            instance.id = 1
            instance.user.id = 42
            instance.height = 180

            # created=False means update, which SHOULD trigger publish
            user_profile_handler(
                sender=MagicMock(), instance=instance, created=False
            )

            mock_publish.assert_called_once()

    def test_user_profile_create_skips_publish(self):
        """Test creating user profile skips NATS publish."""
        with patch(
            'wger.observability.signals.sync_publish_metric_update'
        ) as mock_publish:
            from wger.observability.signals import user_profile_handler

            instance = MagicMock()
            user_profile_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            mock_publish.assert_not_called()


@pytest.mark.django_db
class TestSignalErrorHandling:
    """Test error handling in signal handlers."""

    def test_nats_publish_failure_doesnt_crash_handler(self):
        """Test NATS publish failure is caught and logged."""
        with patch(
            'wger.observability.signals.sync_publish_workout_completed',
            side_effect=Exception("NATS connection lost"),
        ):
            from wger.observability.signals import workout_completed_handler

            instance = MagicMock()
            instance.id = 1
            instance.user.id = 42
            instance.routine_id = 10
            instance.exercise_id = 5
            instance.session_id = 3
            instance.rest = 0
            instance.date = date.today()

            # Should not raise exception
            workout_completed_handler(
                sender=MagicMock(), instance=instance, created=True
            )


@pytest.mark.django_db
class TestSignalIntegrationWithCHIT:
    """Test signal-to-CHIT constellation integration structure."""

    def test_workout_signal_publishes_correct_metadata(self):
        """Test workout signal includes exercise and session metadata."""
        with patch(
            'wger.observability.signals.sync_publish_workout_completed'
        ) as mock_publish:
            mock_publish.return_value = True

            from wger.observability.signals import workout_completed_handler

            instance = MagicMock()
            instance.id = 99
            instance.user.id = 42
            instance.routine_id = 10
            instance.exercise_id = 5
            instance.session_id = 3
            instance.rest = 90
            instance.date = date.today()

            workout_completed_handler(
                sender=MagicMock(), instance=instance, created=True
            )

            call_kwargs = mock_publish.call_args[1]
            metadata = call_kwargs['metadata']
            assert metadata['workout_log_id'] == '99'
            assert metadata['exercise_id'] == '5'
            assert metadata['session_id'] == '3'
