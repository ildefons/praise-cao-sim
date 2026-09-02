"""Phase-1 white-box selection policy after the survival-area revision.

The scientific object is the normalized restricted survival area over a fixed
horizon interval.  The numerical admissible band is configuration data rather
than a hard-coded algorithmic constant, so changing the band requires an
explicit versioned configuration edit but no code redesign.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurvivalAreaSelectionPolicy:
    """Validated nondegeneracy and failure-role selection parameters."""

    horizon_min: float
    horizon_max: float
    area_min: float
    area_max: float
    optimize_to_midpoint: bool
    min_dominant_cause_count: int
    dominance_ratio: float
    min_mixed_cause_count_each: int
    max_mixed_cause_imbalance: int


def load_survival_area_selection_policy(configuration: dict) -> SurvivalAreaSelectionPolicy:
    """Load and validate the versioned Phase-1 AUC selection policy.

    Called by:
        - ``whitebox_scientific_discovery.py`` configuration validation.
        - ``exact_auc_candidate_metrics.py``.
        - ``whitebox_candidate_selection.py``.
        - policy unit tests.
    """
    gate = configuration.get("selection_quality_gate")
    if not isinstance(gate, dict):
        raise ValueError("selection_quality_gate must be configured")
    if gate.get("metric") != "normalized_restricted_survival_area":
        raise ValueError("Phase-1 finalist metric must be normalized_restricted_survival_area")

    area = gate.get("normalized_restricted_survival_area")
    roles = gate.get("role_evidence")
    if not isinstance(area, dict) or not isinstance(roles, dict):
        raise ValueError("selection_quality_gate must define area and role_evidence blocks")

    policy = SurvivalAreaSelectionPolicy(
        horizon_min=float(area["horizon_min"]),
        horizon_max=float(area["horizon_max"]),
        area_min=float(area["minimum"]),
        area_max=float(area["maximum"]),
        optimize_to_midpoint=bool(area["optimize_to_midpoint"]),
        min_dominant_cause_count=int(roles["min_dominant_cause_count"]),
        dominance_ratio=float(roles["dominance_ratio"]),
        min_mixed_cause_count_each=int(roles["min_mixed_cause_count_each"]),
        max_mixed_cause_imbalance=int(roles["max_mixed_cause_imbalance"]),
    )

    if policy.horizon_min < 0.0 or policy.horizon_max <= policy.horizon_min:
        raise ValueError("survival-area horizon must have 0 <= min < max")
    if not 0.0 <= policy.area_min < policy.area_max <= 1.0:
        raise ValueError("normalized survival-area band must satisfy 0 <= min < max <= 1")
    if policy.optimize_to_midpoint:
        raise ValueError("survival-area band is a gate; midpoint optimization is forbidden")
    if policy.min_dominant_cause_count < 1:
        raise ValueError("min_dominant_cause_count must be positive")
    if policy.dominance_ratio <= 1.0:
        raise ValueError("dominance_ratio must exceed one")
    if policy.min_mixed_cause_count_each < 1:
        raise ValueError("min_mixed_cause_count_each must be positive")
    if policy.max_mixed_cause_imbalance < 0:
        raise ValueError("max_mixed_cause_imbalance must be non-negative")
    return policy
