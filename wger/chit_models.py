"""
CHIT/CGP Fitness Constellation Models for PMOVES-Health-wger

Converts wger workout and measurement data into geometric constellations
following the CHIT (Cymatic-Holographic Information Transfer) protocol.

This module transforms health data into CGP (CHIT Geometry Packet) format
for integration with PMOVES.AI's mathematical framework and consciousness
taxonomy.

Usage:
    from wger.chit_models import build_workout_constellation, build_metrics_constellation

    # Build workout constellation
    cgp = build_workout_constellation(workout_log, embeddings)
    publish_to_nats(cgp, subject="geometry.cgp.v1")

CHIT/CGP References:
- Specification: pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md
- Schema: pmoves/integrations/health-wger/chit_schemas/chit.cgp.v1.0.schema.json
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def build_workout_constellation(
    workout_log: Any,
    embeddings: Optional[np.ndarray] = None,
    k_constellations: int = 3
) -> Dict[str, Any]:
    """
    Convert workout log to CHIT/CGP constellation format.

    Creates a geometric constellation representing workout intensity,
    duration, and exercise patterns for integration with PMOVES.AI's
    mathematical consciousness framework.

    Args:
        workout_log: Django WorkoutLog or WorkoutSession instance
        embeddings: Optional exercise embedding vectors (numpy array)
        k_constellations: Number of constellations to generate (default: 3)

    Returns:
        CGP v1.0 compliant dictionary with workout constellation data

    Constellation Types:
        1. High Intensity: Vigorous exercise sessions (short duration, high effort)
        2. Moderate Intensity: Balanced sessions (moderate duration and effort)
        3. Low Intensity: Light activity sessions (long duration, low effort)

    Example:
        >>> from wger.core.models import WorkoutSession
        >>> session = WorkoutSession.objects.get(id=1)
        >>> cgp = build_workout_constellation(session)
        >>> validate_cgp(cgp, schema)  # Returns True
    """
    # Extract workout metadata
    try:
        duration = getattr(workout_log, 'duration', 0) or 0
        date = getattr(workout_log, 'date', datetime.now())
        workout_id = getattr(workout_log, 'id', 'unknown')

        # Extract exercise data if available
        exercises = []
        if hasattr(workout_log, 'exercise') and workout_log.exercise:
            exercises = [workout_log.exercise]
        elif hasattr(workout_log, 'routine') and workout_log.routine:
            exercises = list(getattr(workout_log.routine, 'exercises', []))

        # Calculate intensity metrics
        num_exercises = len(exercises)
        avg_duration_per_exercise = duration / max(num_exercises, 1)

        # Determine intensity category
        intensity_category = _classify_workout_intensity(duration, num_exercises)

        # Generate anchor direction (3D vector in embedding space)
        # Uses duration, exercise count, and intensity as dimensions
        anchor = _generate_workout_anchor(duration, num_exercises, intensity_category)

        # Compute radial bounds (projection range along anchor)
        radial_min, radial_max = _compute_workout_radial_bounds(duration, intensity_category)

        # Generate energy spectrum (histogram over 8 radial bins)
        spectrum = _generate_workout_spectrum(duration, num_exercises, intensity_category)

    except Exception as e:
        logger.error(f"Error extracting workout data: {e}")
        # Return minimal valid constellation on error
        return _create_minimal_workout_constellation()

    # Build CGP structure
    super_node = {
        "id": f"workout_{workout_id}",
        "label": "Workout Session",
        "summary": f"{' '.join(intensity_category.split('_')).title()} workout on {date.strftime('%Y-%m-%d')}",
        "x": float({"high": 1, "moderate": 2, "low": 3}.get(intensity_category, 2) * 100 - 150),
        "y": float(duration * 2 - 100),
        "constellations": [
            {
                "id": f"{intensity_category}_intensity",
                "label": f"{' '.join(intensity_category.split('_')).title()} Intensity",
                "summary": f"{num_exercises} exercises, {duration:.0f} minutes",
                "anchor": anchor.tolist(),
                "radial_minmax": [radial_min, radial_max],
                "spectrum": spectrum,
                "points": _build_workout_content_points(exercises) if exercises else []
            }
        ]
    }

    # Add hyperbolic encoding if embeddings provided
    if embeddings is not None:
        super_node["hyperbolic"] = {
            "poincare": _compute_poincare_coordinates(anchor).tolist(),
            "curvature": -1.0
        }

    # Build complete CGP
    cgp = {
        "spec": "chit.cgp.v1.0",
        "meta": {
            "source": "latent",
            "units_mode": "workouts",
            "K": k_constellations,
            "bins": 8,
            "backend": "wger-workout-encoder",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "encoder_version": "1.0.0"
        },
        "super_nodes": [super_node]
    }

    # Add NATS metadata for GEOMETRY_BUS integration
    cgp["nats"] = {
        "subject": "geometry.cgp.v1",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "publisher_id": "pmoves-health-wger",
        "stream": "GEOMETRY_CGP"
    }

    return cgp


def build_metrics_constellation(
    weight_entries: List[Any],
    measurement_entries: Optional[List[Any]] = None,
    k_constellations: int = 2
) -> Dict[str, Any]:
    """
    Convert weight and measurement data to CHIT/CGP constellation format.

    Creates geometric constellations representing health trends,
    progressions, and patterns over time for consciousness integration.

    Args:
        weight_entries: List of Django WeightEntry instances
        measurement_entries: Optional list of Measurement instances
        k_constellations: Number of constellations to generate (default: 2)

    Returns:
        CGP v1.0 compliant dictionary with metrics constellation data

    Constellation Types:
        1. Weight Progression: Trends in weight change over time
        2. Body Composition: Changes in measurements (if provided)

    Example:
        >>> from wger.weight.models import WeightEntry
        >>> entries = list(WeightEntry.objects.filter(user=user).order_by('date'))
        >>> cgp = build_metrics_constellation(entries)
    """
    if not weight_entries:
        logger.warning("No weight entries provided, returning minimal constellation")
        return _create_minimal_metrics_constellation()

    # Extract weight data
    weights = [float(entry.weight) for entry in weight_entries]
    dates = [entry.date for entry in weight_entries]

    # Calculate weight progression trends
    weight_diffs = np.diff(weights)
    avg_change = np.mean(weight_diffs) if len(weight_diffs) > 0 else 0

    # Classify trend direction
    trend_direction = "loss" if avg_change < -0.1 else ("gain" if avg_change > 0.1 else "stable")

    # Generate weight constellation
    weight_constellation = _build_weight_progression_constellation(
        weights, dates, trend_direction, weight_entries[0].user_id
    )

    super_nodes = [weight_constellation]

    # Add body composition constellation if measurements provided
    if measurement_entries:
        body_comp_constellation = _build_body_composition_constellation(measurement_entries)
        super_nodes.append(body_comp_constellation)

    # Build complete CGP
    cgp = {
        "spec": "chit.cgp.v1.0",
        "meta": {
            "source": "text",
            "units_mode": "measurements",
            "K": k_constellations,
            "bins": 6,
            "backend": "wger-metrics-encoder",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "encoder_version": "1.0.0"
        },
        "super_nodes": super_nodes,
        "nats": {
            "subject": "geometry.cgp.v1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "publisher_id": "pmoves-health-wger",
            "stream": "GEOMETRY_CGP"
        }
    }

    return cgp


# =============================================================================
# Internal Helper Functions
# =============================================================================

class WorkoutIntensity:
    """Workout intensity classification constants."""
    HIGH = 1
    MODERATE = 2
    LOW = 3


def _classify_workout_intensity(duration: float, num_exercises: int) -> str:
    """Classify workout intensity based on duration and exercise count."""
    # High intensity: Short duration, many exercises (vigorous)
    if duration < 30 and num_exercises >= 6:
        return "high"
    # Low intensity: Long duration, few exercises (light activity)
    elif duration > 60 and num_exercises <= 4:
        return "low"
    # Moderate intensity: Balanced
    else:
        return "moderate"


def _generate_workout_anchor(duration: float, num_exercises: int, intensity: str) -> np.ndarray:
    """Generate 3D anchor vector for workout constellation."""
    # Normalize dimensions to [0, 1] range
    norm_duration = min(duration / 120, 1.0)  # Max 2 hours
    norm_exercises = min(num_exercises / 12, 1.0)  # Max 12 exercises

    # Intensity encoding: high=1.0, moderate=0.5, low=0.0
    intensity_value = {"high": 1.0, "moderate": 0.5, "low": 0.0}[intensity]

    # Generate 3D anchor (normalized unit vector)
    anchor = np.array([norm_duration, norm_exercises, intensity_value])
    anchor = anchor / np.linalg.norm(anchor)  # Normalize to unit length

    return anchor


def _compute_workout_radial_bounds(duration: float, intensity: str) -> Tuple[float, float]:
    """Compute radial bounds for workout constellation."""
    # Base bounds on duration and intensity
    intensity_factors = {"high": 0.3, "moderate": 0.5, "low": 0.7}
    factor = intensity_factors.get(intensity, 0.5)

    center = (duration / 120) * factor
    spread = 0.15

    return (center - spread, center + spread)


def _generate_workout_spectrum(duration: float, num_exercises: int, intensity: str) -> List[float]:
    """Generate 8-bin energy spectrum for workout constellation."""
    # Base spectrum on intensity profile
    intensity_profiles = {
        "high": [0.05, 0.10, 0.15, 0.30, 0.20, 0.12, 0.06, 0.02],
        "moderate": [0.10, 0.12, 0.18, 0.22, 0.18, 0.12, 0.06, 0.02],
        "low": [0.15, 0.20, 0.25, 0.18, 0.12, 0.06, 0.03, 0.01]
    }

    base_spectrum = intensity_profiles.get(intensity, intensity_profiles["moderate"])

    # Adjust based on exercise count (more exercises = higher energy in middle bins)
    if num_exercises > 8:
        base_spectrum[3:5] = [x * 1.2 for x in base_spectrum[3:5]]
        # Re-normalize
        total = sum(base_spectrum)
        base_spectrum = [x / total for x in base_spectrum]

    return base_spectrum


def _build_workout_content_points(exercises: List[Any]) -> List[Dict[str, Any]]:
    """Build content points for exercises in workout."""
    points = []
    for idx, exercise in enumerate(exercises[:8]):  # Limit to 8 points
        exercise_name = getattr(exercise, 'name', f"Exercise {idx + 1}")
        points.append({
            "id": f"exercise_{idx}",
            "x": float(np.random.uniform(-50, 50)),
            "y": float(np.random.uniform(-50, 50)),
            "proj": float(np.random.uniform(0.5, 0.95)),
            "conf": float(np.random.uniform(0.8, 0.98)),
            "text": exercise_name,
            "char_len": len(exercise_name),
            "word_count": len(exercise_name.split())
        })
    return points


def _compute_poincare_coordinates(anchor: np.ndarray) -> np.ndarray:
    """Compute Poincaré disk coordinates from anchor vector."""
    # Simplified Poincaré disk projection (2D only)
    # For production, use proper hyperbolic geometry
    x = anchor[0] if len(anchor) > 0 else 0
    y = anchor[1] if len(anchor) > 1 else 0

    # Project to unit disk
    norm = np.sqrt(x**2 + y**2)
    scale = 2.0 / (1.0 + norm**2)

    return np.array([x * scale, y * scale]) * 0.5  # Scale to fit in disk


def _build_weight_progression_constellation(
    weights: List[float],
    dates: List[Any],
    trend_direction: str,
    user_id: int
) -> Dict[str, Any]:
    """Build weight progression constellation."""
    # Calculate statistics
    min_weight = min(weights)
    max_weight = max(weights)
    avg_weight = np.mean(weights)

    # Generate anchor based on trend
    if trend_direction == "loss":
        anchor = [0.4, -0.6, 0.7]
    elif trend_direction == "gain":
        anchor = [-0.5, 0.4, 0.7]
    else:  # stable
        anchor = [0.0, 0.0, 1.0]

    # Normalize anchor to unit length
    anchor = np.array(anchor) / np.linalg.norm(anchor)

    return {
        "id": f"weight_progression_{user_id}",
        "label": "Weight Progression",
        "summary": f"{trend_direction.title()} trend: {min_weight:.1f} → {max_weight:.1f} kg",
        "x": float((avg_weight - 70) * 2),  # Center around 70kg
        "y": float((max_weight - min_weight) * 10 - 50),
        "constellations": [
            {
                "id": f"weight_{trend_direction}",
                "label": f"Weight {trend_direction.title()}",
                "summary": f"{'Loss' if trend_direction == 'loss' else 'Gain'} period",
                "anchor": anchor.tolist(),
                "radial_minmax": [0.0, 0.9],
                "spectrum": [0.1, 0.15, 0.25, 0.25, 0.15, 0.1],
                "points": [
                    {
                        "id": f"weight_entry_{idx}",
                        "x": float(idx * 20 - 80),
                        "y": float((weight - 70) * 3),
                        "proj": float(idx / len(weights)),
                        "text": f"{weight:.1f} kg on {date.strftime('%Y-%m-%d')}"
                    }
                    for idx, (weight, date) in enumerate(zip(weights, dates))
                ]
            }
        ]
    }


def _build_body_composition_constellation(measurements: List[Any]) -> Dict[str, Any]:
    """Build body composition constellation from measurements."""
    # Simplified implementation - in production, calculate actual measurements
    return {
        "id": "body_composition",
        "label": "Body Composition",
        "summary": f"{len(measurements)} measurement entries",
        "constellations": [
            {
                "id": "measurement_trends",
                "label": "Measurement Trends",
                "anchor": [0.2, 0.3, 0.9],
                "radial_minmax": [0.0, 0.8],
                "spectrum": [0.12, 0.18, 0.22, 0.20, 0.16, 0.12]
            }
        ]
    }


def _create_minimal_workout_constellation() -> Dict[str, Any]:
    """Create minimal valid workout constellation for error recovery."""
    return {
        "spec": "chit.cgp.v1.0",
        "meta": {
            "source": "latent",
            "units_mode": "workouts",
            "K": 1,
            "bins": 5,
            "backend": "wger-workout-encoder"
        },
        "super_nodes": [
            {
                "id": "workout_unknown",
                "constellations": [
                    {
                        "id": "intensity_unknown",
                        "anchor": [0.5, 0.5, 0.7],
                        "radial_minmax": [0.0, 1.0],
                        "spectrum": [0.2, 0.2, 0.2, 0.2, 0.2]
                    }
                ]
            }
        ]
    }


def _create_minimal_metrics_constellation() -> Dict[str, Any]:
    """Create minimal valid metrics constellation for error recovery."""
    return {
        "spec": "chit.cgp.v1.0",
        "meta": {
            "source": "text",
            "units_mode": "measurements",
            "K": 1,
            "bins": 5,
            "backend": "wger-metrics-encoder"
        },
        "super_nodes": [
            {
                "id": "metrics_unknown",
                "constellations": [
                    {
                        "id": "trend_unknown",
                        "anchor": [0.0, 0.0, 1.0],
                        "radial_minmax": [0.0, 1.0],
                        "spectrum": [0.2, 0.2, 0.2, 0.2, 0.2]
                    }
                ]
            }
        ]
    }
