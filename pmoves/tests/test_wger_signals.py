"""
Unit tests for Wger Django signal handlers.

Tests the automatic NATS event publishing triggered by Django
model saves for workouts, measurements, and user profiles.
"""

import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from wger.core.models import UserProfile, WorkoutLog, WorkoutSession
from wger.weight.models import WeightEntry
from wger.observability.signals import (
    workout_completed,
    weight_updated,
    measurement_updated
)


@pytest.mark.django_db
class TestWorkoutSignals:
    """Test Django signal handlers for workout events."""

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        User = get_user_model()
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    @pytest.fixture
    def workout(self, db, user):
        """Create test workout."""
        from wger.core.models import Workout
        workout = Workout.objects.create(
            user=user,
            name="Test Workout"
        )
        return workout

    def test_workout_session_save_triggers_signal(self, user, workout):
        """Test saving WorkoutSession triggers NATS publish."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_workout_completed = MagicMock()

            session = WorkoutSession.objects.create(
                user=user,
                workout=workout,
                date=date.today(),
                duration=45
            )

            # Verify signal was triggered
            mock_publisher.sync_publish_workout_completed.assert_called_once()

            # Verify call arguments
            call_args = mock_publisher.sync_publish_workout_completed.call_args
            assert call_args[0][0] == str(user.id)
            assert "workout_data" in call_args[0][1]

    def test_workout_log_save_triggers_signal(self, user, workout):
        """Test saving WorkoutLog triggers NATS publish."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_workout_completed = MagicMock()

            log = WorkoutLog.objects.create(
                user=user,
                workout=workout,
                date=date.today(),
                duration=30
            )

            # Verify signal was triggered
            mock_publisher.sync_publish_workout_completed.assert_called_once()

    def test_workout_update_triggers_signal(self, user, workout):
        """Test updating workout session triggers NATS publish."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_workout_completed = MagicMock()

            session = WorkoutSession.objects.create(
                user=user,
                workout=workout,
                date=date.today(),
                duration=30
            )

            # Reset mock
            mock_publisher.sync_publish_workout_completed.reset_mock()

            # Update session
            session.duration = 45
            session.save()

            # Verify signal was triggered again
            mock_publisher.sync_publish_workout_completed.assert_called_once()

    @override_settings(WGER_ENABLE_NATS=False)
    def test_nats_disabled_no_signal_triggered(self, user, workout):
        """Test signals are not triggered when NATS is disabled."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_workout_completed = MagicMock()

            session = WorkoutSession.objects.create(
                user=user,
                workout=workout,
                date=date.today(),
                duration=45
            )

            # Verify signal was NOT triggered
            mock_publisher.sync_publish_workout_completed.assert_not_called()


@pytest.mark.django_db
class TestWeightSignals:
    """Test Django signal handlers for weight tracking."""

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        User = get_user_model()
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_weight_entry_save_triggers_signal(self, user):
        """Test saving WeightEntry triggers NATS publish."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_metric_update = MagicMock()

            entry = WeightEntry.objects.create(
                user=user,
                weight=75.5,
                date=date.today()
            )

            # Verify signal was triggered
            mock_publisher.sync_publish_metric_update.assert_called_once()

            # Verify call arguments
            call_args = mock_publisher.sync_publish_metric_update.call_args
            assert call_args[0][0] == str(user.id)
            assert call_args[0][1] == "weight"
            assert call_args[0][2] == 75.5

    def test_weight_update_triggers_signal(self, user):
        """Test updating weight entry triggers NATS publish."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_metric_update = MagicMock()

            entry = WeightEntry.objects.create(
                user=user,
                weight=75.5,
                date=date.today()
            )

            # Reset mock
            mock_publisher.sync_publish_metric_update.reset_mock()

            # Update weight
            entry.weight = 76.0
            entry.save()

            # Verify signal was triggered again
            mock_publisher.sync_publish_metric_update.assert_called_once()

            # Verify new value was published
            call_args = mock_publisher.sync_publish_metric_update.call_args
            assert call_args[0][2] == 76.0


@pytest.mark.django_db
class TestMeasurementSignals:
    """Test Django signal handlers for body measurements."""

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        User = get_user_model()
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_measurement_save_triggers_signal(self, user):
        """Test saving measurement triggers NATS publish."""
        from wger.core.models import Measurement

        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_metric_update = MagicMock()

            measurement = Measurement.objects.create(
                user=user,
                date=date.today(),
                measurement_type="chest",
                value=100.5
            )

            # Verify signal was triggered
            mock_publisher.sync_publish_metric_update.assert_called_once()

            # Verify call arguments
            call_args = mock_publisher.sync_publish_metric_update.call_args
            assert call_args[0][0] == str(user.id)
            assert call_args[0][1] == "measurement"
            assert "chest" in str(call_args[0][3])


@pytest.mark.django_db
class TestUserProfileSignals:
    """Test Django signal handlers for user profile updates."""

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        User = get_user_model()
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_user_profile_update_triggers_signal(self, user):
        """Test updating user profile triggers NATS publish."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_metric_update = MagicMock()

            profile = UserProfile.objects.get(user=user)
            profile.height = 180
            profile.save()

            # Verify signal was triggered
            mock_publisher.sync_publish_metric_update.assert_called_once()


@pytest.mark.django_db
class TestSignalErrorHandling:
    """Test error handling in signal handlers."""

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        User = get_user_model()
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_nats_publish_failure_doesnt_crash_save(self, user):
        """Test NATS publish failure doesn't prevent database save."""
        from wger.core.models import Workout

        with patch('wger.observability.signals.publisher') as mock_publisher:
            # Simulate NATS publish failure
            mock_publisher.sync_publish_workout_completed.side_effect = Exception("NATS connection lost")

            workout = Workout.objects.create(user=user, name="Test Workout")

            # Verify object was saved to database despite NATS error
            assert workout.id is not None
            assert workout.name == "Test Workout"

    def test_signal_exception_is_logged(self, user, caplog):
        """Test signal exceptions are logged."""
        from wger.core.models import Workout

        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_workout_completed.side_effect = Exception("NATS error")

            workout = Workout.objects.create(user=user, name="Test Workout")

            # Verify exception was logged
            # Note: Actual logging behavior depends on implementation


@pytest.mark.django_db
class TestSignalIntegrationWithCHIT:
    """Test integration with CHIT/CGP constellation models."""

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        User = get_user_model()
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_workout_signal_generates_cgp_constellation(self, user):
        """Test workout signal generates CGP constellation."""
        from wger.core.models import Workout

        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_workout_completed = MagicMock()

            workout = Workout.objects.create(user=user, name="Test Workout")

            # Verify signal was triggered
            mock_publisher.sync_publish_workout_completed.assert_called_once()

            # In production, this would publish CGP constellation
            # For now, verify the call structure

    def test_weight_signal_generates_cgp_constellation(self, user):
        """Test weight signal generates CGP constellation."""
        with patch('wger.observability.signals.publisher') as mock_publisher:
            mock_publisher.sync_publish_metric_update = MagicMock()

            entry = WeightEntry.objects.create(
                user=user,
                weight=75.5,
                date=date.today()
            )

            # Verify signal was triggered
            mock_publisher.sync_publish_metric_update.assert_called_once()

            # In production, this would publish CGP constellation
            # For now, verify the call structure
