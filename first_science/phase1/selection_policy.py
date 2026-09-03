"""Configuration-driven Phase-1 SLA-compliance finalist selection policy.

The scientific selection object is the normalized area under
sigma_G(A,H,rho*) = P(c_G(A,H) >= rho*) with rho*=0.95 and cumulative [0,H]
accounting from the prescribed t=0 origin. The numerical area band remains a
versioned configuration parameter and is a gate, never a midpoint target.
"""
from __future__ import annotations

from dataclasses import dataclass

from sla_compliance_analysis import SlaComplianceDefinition


@dataclass(frozen=True)
class SlaComplianceAreaSelectionPolicy:
    """Hold validated SLA-compliance area and failure-role selection settings."""

    sla_definition: SlaComplianceDefinition
    horizon_min: float
    horizon_max: float
    area_min: float
    area_max: float
    optimize_to_midpoint: bool
    dominance_ratio: float


def load_sla_compliance_area_selection_policy(
    configuration: dict,
) -> SlaComplianceAreaSelectionPolicy:
    """Load the versioned Phase-1 SLA-compliance finalist policy.

    Args:
        configuration: Parsed ``config_phase1_discovery_v1.json``.

    Returns:
        Validated SLA definition, area gate and L/C role criterion.

    Side effects:
        None.

    Called by:
        - ``whitebox_scientific_discovery.py`` configuration validation.
        - ``sla_compliance_candidate_metrics.py``.
        - ``whitebox_candidate_selection.py``.
        - ``run_n100_matched_confirmation.py``.
        - policy unit tests.
    """
    sla = configuration.get("sla_compliance")
    gate = configuration.get("selection_quality_gate")
    if not isinstance(sla, dict):
        raise ValueError("sla_compliance must be configured")
    if not isinstance(gate, dict):
        raise ValueError("selection_quality_gate must be configured")
    if gate.get("metric") != "normalized_sla_compliance_area":
        raise ValueError(
            "Phase-1 finalist metric must be normalized_sla_compliance_area"
        )

    area = gate.get("normalized_sla_compliance_area")
    roles = gate.get("role_evidence")
    if not isinstance(area, dict) or not isinstance(roles, dict):
        raise ValueError("selection gate must define area and role_evidence blocks")

    sla_definition = SlaComplianceDefinition(
        rho=float(sla["search_rho"]),
        accounting_origin=float(sla["accounting_origin"]),
        zero_decision_compliance=float(sla["zero_decided_requests_compliance"]),
    )
    policy = SlaComplianceAreaSelectionPolicy(
        sla_definition=sla_definition,
        horizon_min=float(area["horizon_min"]),
        horizon_max=float(area["horizon_max"]),
        area_min=float(area["minimum"]),
        area_max=float(area["maximum"]),
        optimize_to_midpoint=bool(area["optimize_to_midpoint"]),
        dominance_ratio=float(roles["dominance_ratio"]),
    )

    if not 0.0 < sla_definition.rho <= 1.0:
        raise ValueError("SLA rho must lie in (0,1]")
    if abs(sla_definition.accounting_origin) > 1e-12:
        raise ValueError("Phase-1 cumulative accounting origin must be t=0")
    if abs(sla_definition.zero_decision_compliance - 1.0) > 1e-12:
        raise ValueError("zero-decided-request compliance convention must be 1")
    if sla.get("accounting_window") != "cumulative_[0,H]_from_t0":
        raise ValueError("Phase-1 SLA accounting must be cumulative [0,H] from t=0")
    if sla.get("rolling_windows_allowed") is not False:
        raise ValueError("rolling SLA windows are forbidden in the anchor benchmark")

    if policy.horizon_min < sla_definition.accounting_origin - 1e-12:
        raise ValueError("SLA-compliance area cannot start before accounting origin")
    if policy.horizon_max <= policy.horizon_min:
        raise ValueError("SLA-compliance area horizon must satisfy min < max")
    if not 0.0 <= policy.area_min < policy.area_max <= 1.0:
        raise ValueError("normalized SLA-compliance area band must lie in [0,1]")
    if policy.optimize_to_midpoint:
        raise ValueError("SLA-compliance area band is a gate; midpoint optimization is forbidden")
    if policy.dominance_ratio <= 1.0:
        raise ValueError("L/C dominance_ratio must exceed one")
    return policy


def classify_lc_failure_role(
    latency_failure_count: int,
    cost_failure_count: int,
    dominance_ratio: float,
) -> str:
    """Classify all-request L/C failure composition using one ratio criterion.

    Args:
        latency_failure_count: Number of decided requests failing by latency.
        cost_failure_count: Number of decided in-time requests failing cost.
        dominance_ratio: Ratio at or above which one dimension is dominant.

    Returns:
        ``latency``, ``cost``, ``mixed`` or ``no_lc_failure``.

    Side effects:
        None.

    Called by:
        - ``run_n100_matched_confirmation.py`` confirmation diagnostics.
        - policy unit tests.
    """
    latency = int(latency_failure_count)
    cost = int(cost_failure_count)
    ratio = float(dominance_ratio)
    if latency < 0 or cost < 0:
        raise ValueError("failure counts must be non-negative")
    if ratio <= 1.0:
        raise ValueError("dominance_ratio must exceed one")
    if latency == 0 and cost == 0:
        return "no_lc_failure"
    if latency > 0 and latency >= ratio * max(cost, 1):
        return "latency"
    if cost > 0 and cost >= ratio * max(latency, 1):
        return "cost"
    if latency > 0 and cost > 0:
        return "mixed"
    return "latency" if latency > 0 else "cost"


@dataclass(frozen=True)
class SurvivalAreaSelectionPolicy:
    """Legacy first-passage survival-area policy retained for reproducibility."""

    horizon_min: float
    horizon_max: float
    area_min: float
    area_max: float
    optimize_to_midpoint: bool
    min_dominant_cause_count: int
    dominance_ratio: float
    min_mixed_cause_count_each: int
    max_mixed_cause_imbalance: int


def load_survival_area_selection_policy(
    configuration: dict,
) -> SurvivalAreaSelectionPolicy:
    """Load the superseded first-passage AUC policy for historical scripts.

    This compatibility loader exists only so archived Phase-1 first-passage
    diagnostics remain executable. Current finalist selection must call
    ``load_sla_compliance_area_selection_policy`` instead.

    Called by:
        - superseded ``exact_auc_candidate_metrics.py`` and its regression tests.
    """
    gate = configuration.get("selection_quality_gate")
    if not isinstance(gate, dict):
        raise ValueError("selection_quality_gate must be configured")
    if gate.get("metric") != "normalized_restricted_survival_area":
        raise ValueError(
            "legacy loader requires normalized_restricted_survival_area"
        )
    area = gate.get("normalized_restricted_survival_area")
    roles = gate.get("role_evidence")
    if not isinstance(area, dict) or not isinstance(roles, dict):
        raise ValueError("legacy selection gate is incomplete")
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
    if policy.optimize_to_midpoint:
        raise ValueError("legacy survival-area midpoint optimization is forbidden")
    return policy
