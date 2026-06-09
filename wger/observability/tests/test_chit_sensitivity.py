"""
Unit tests for CHIT sensitivity gating in the health NATS publisher (Phase 4).

Verifies the acceptance criterion from the W6-P1 Health lane: a CHIT packet with
``delta_sensitive=true`` enables the alert gate, and ``delta_sensitive=false``
suppresses it (and the same for ``hz_sensitive`` on frequency anomalies).
"""

import unittest

from django.test import SimpleTestCase, override_settings

from wger.observability.nats_publisher import (
    DELTA_ANOMALY_TYPES,
    HZ_ANOMALY_TYPES,
    HealthEventPublisher,
)


class ChitSensitivityGateTest(SimpleTestCase):
    """The CHIT gate suppresses an anomaly class when its toggle is disabled."""

    @staticmethod
    def _publisher(*, delta=True, hz=True):
        pub = HealthEventPublisher()
        pub.delta_sensitive = delta
        pub.hz_sensitive = hz
        return pub

    def test_delta_anomaly_allowed_when_delta_sensitive_true(self):
        self.assertTrue(self._publisher(delta=True).chit_gate_allows("weight_spike"))

    def test_delta_anomaly_suppressed_when_delta_sensitive_false(self):
        pub = self._publisher(delta=False, hz=True)
        # Suppressed regardless of the unrelated hz toggle.
        self.assertFalse(pub.chit_gate_allows("weight_spike"))

    def test_hz_anomaly_allowed_when_hz_sensitive_true(self):
        self.assertTrue(self._publisher(hz=True).chit_gate_allows("missing_data"))

    def test_hz_anomaly_suppressed_when_hz_sensitive_false(self):
        pub = self._publisher(delta=True, hz=False)
        # Suppressed regardless of the unrelated delta toggle.
        self.assertFalse(pub.chit_gate_allows("missing_data"))

    def test_unclassified_anomaly_always_passes(self):
        # Fail-open: a never-before-seen type is never silently dropped.
        pub = self._publisher(delta=False, hz=False)
        self.assertTrue(pub.chit_gate_allows("brand_new_anomaly_type"))

    def test_classification_sets_are_disjoint(self):
        # An anomaly type must not be gated by both toggles ambiguously.
        self.assertEqual(DELTA_ANOMALY_TYPES & HZ_ANOMALY_TYPES, frozenset())

    @override_settings(WGER_CHIT_DELTA_SENSITIVE=False)
    def test_delta_toggle_read_from_settings(self):
        pub = HealthEventPublisher()
        self.assertFalse(pub.delta_sensitive)
        self.assertFalse(pub.chit_gate_allows("weight_spike"))

    @override_settings(WGER_CHIT_HZ_SENSITIVE=False)
    def test_hz_toggle_read_from_settings(self):
        pub = HealthEventPublisher()
        self.assertFalse(pub.hz_sensitive)
        self.assertFalse(pub.chit_gate_allows("missing_data"))


class ChitSuppressedPublishTest(unittest.IsolatedAsyncioTestCase):
    """publish_anomaly_detected returns False (no emit) when CHIT-suppressed."""

    async def test_suppressed_anomaly_not_published(self):
        pub = HealthEventPublisher()
        pub.enabled = True  # would otherwise try to publish
        pub.delta_sensitive = False
        # The gate short-circuits before any NATS use, so the lack of a live
        # connection does not matter — suppression is what returns False here.
        result = await pub.publish_anomaly_detected(
            user_id="u1",
            anomaly_type="weight_spike",
            severity="high",
            description="test anomaly",
            affected_metrics={"weight": 99},
        )
        self.assertFalse(result)
