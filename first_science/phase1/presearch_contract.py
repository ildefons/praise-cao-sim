"""Phase-1 discovery and confirmation contracts for the first PRAISE experiment.

This module is deliberately simulator-independent. It prevents the Phase-1
white-box discovery search from starting before every required search constant
has been explicitly frozen in ``config_phase1.json``. It also prevents N=100
confirmation from starting until exact discovery finalists and their admissibility
regions have been frozen and a fresh confirmation seed bank has been declared.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderInstructionMeanTriplet:
    """Hold mean service-instruction requirements for providers A, B, and C.

    The values parameterize the native per-invocation ``Message.instructions``
    distributions. Semantically, each value is the mean number of computational
    instructions required by that provider to execute one invocation. It is a
    provider/service property, not the external root workload or arrival rate.
    The values do not parameterize latency, cost, or quality directly.

    Called by:
        - ``calculate_symmetric_provider_instruction_means`` in this module.
        - Phase-1 native reference-search code once that runner is implemented.
    """

    provider_a: float
    provider_b: float
    provider_c: float


_REQUIRED_DISCOVERY_NON_NULL_PATHS = (
    "graph.pre_module_behavior",
    "graph.post_module_behavior",
    "workload.period",
    "workload.phase",
    "topology.placement",
    "topology.link_parameters",
    "provider_family.instruction_cv",
    "provider_family.effective_ipt",
    "provider_family.cost_rate",
    "provider_family.x",
    "provider_parameterization.center_instruction_mean_bounds",
    "provider_parameterization.dispersion_bounds",
    "horizon.grid",
    "horizon.simulation_stop_time",
    "discovery_search.calibration_seed_bank",
    "discovery_search.search_method",
    "discovery_search.initial_design_size",
    "discovery_search.total_candidate_budget",
)

_REQUIRED_SELECTED_WHITEBOX_FIELDS = (
    "case_id",
    "selection_role",
    "physical_setting_id",
    "center_instruction_mean",
    "dispersion",
    "l_max",
    "c_max",
    "q_min",
)


def calculate_symmetric_provider_instruction_means(
    center_instruction_mean: float,
    dispersion: float,
) -> ProviderInstructionMeanTriplet:
    """Calculate A/B/C mean service-instruction requirements from center/delta.

    Provider A receives ``center * (1-dispersion)``, B receives ``center``, and
    C receives ``center * (1+dispersion)``. ``center_instruction_mean`` is kept
    as the code/configuration name for compatibility, but scientifically it is
    the central mean computational instruction requirement per provider
    invocation. ``dispersion`` (delta) controls provider-to-provider
    heterogeneity in that mean requirement; it is not request-to-request
    stochastic variation. Invocation-to-invocation variation is governed
    separately by the frozen native distribution CV.

    These values parameterize the native stochastic ``Message.instructions``
    field; AICon/YAFS must causally generate service time, queueing, latency,
    cost, and quality from the simulated graph. The root workload W remains a
    separate fixed specification of invocation timing/pattern.

    Args:
        center_instruction_mean: Positive central mean service-instruction
            requirement per provider invocation.
        dispersion: Multiplicative provider-heterogeneity magnitude satisfying
            ``0 <= d < 1``.

    Returns:
        ProviderInstructionMeanTriplet with strictly positive A/B/C means.

    Called by:
        - ``test_symmetric_provider_instruction_parameterization`` in
          ``test_presearch_contract.py``.
        - Future Phase-1 native candidate construction code.
    """
    center = float(center_instruction_mean)
    delta = float(dispersion)
    if center <= 0.0:
        raise ValueError("center_instruction_mean must be positive")
    if not 0.0 <= delta < 1.0:
        raise ValueError("dispersion must satisfy 0 <= dispersion < 1")
    return ProviderInstructionMeanTriplet(
        provider_a=center * (1.0 - delta),
        provider_b=center,
        provider_c=center * (1.0 + delta),
    )


def assert_phase1_sampling_policy_is_consistent(configuration: dict[str, Any]) -> None:
    """Validate the frozen N=10 discovery / N=100 confirmation policy.

    The existing N=10 development atlas remains explicitly non-scientific. The
    scientific discovery search also uses N=10 trajectories per candidate, but
    under a separately frozen scientific search configuration. N=100 is reserved
    for fresh-seed confirmation of exact finalists selected by discovery.

    Args:
        configuration: Parsed ``config_phase1.json`` dictionary.

    Raises:
        ValueError: If development, discovery, or confirmation budgets/policies
            drift from the frozen discovery/confirmation separation.

    Called by:
        - ``assert_phase1_discovery_configuration_is_frozen`` in this module.
        - ``assert_phase1_confirmation_configuration_is_ready`` in this module.
        - ``test_discovery_is_n10_and_confirmation_is_n100`` in
          ``test_presearch_contract.py``.
    """
    development_smoke = configuration.get("development_smoke", {})
    discovery_search = configuration.get("discovery_search", {})
    confirmation = configuration.get("confirmation", {})

    if int(development_smoke.get("n_trajectories", -1)) != 10:
        raise ValueError("Phase-1 development smoke must use exactly N=10 trajectories")
    development_seeds = development_smoke.get("seed_bank")
    if (
        not isinstance(development_seeds, list)
        or len(development_seeds) != 10
        or len(set(development_seeds)) != 10
    ):
        raise ValueError("Phase-1 development smoke must define 10 unique deterministic seeds")
    if development_smoke.get("scientific_evidence") is not False:
        raise ValueError("Phase-1 development smoke must remain explicitly non-scientific")

    if int(discovery_search.get("n_trajectories_per_candidate", -1)) != 10:
        raise ValueError("scientific white-box discovery must use N=10 trajectories per candidate")
    if discovery_search.get("common_seed_bank_across_candidates") is not True:
        raise ValueError("discovery must use one common seed bank across candidate physical settings")

    if int(confirmation.get("n_trajectories_per_selected_whitebox", -1)) != 100:
        raise ValueError("selected-whitebox confirmation must use N=100 trajectories per finalist")
    if confirmation.get("fresh_seeds_required") is not True:
        raise ValueError("confirmation must require seeds fresh from the N=10 discovery seed bank")
    if confirmation.get("selected_whiteboxes_must_be_frozen_before_run") is not True:
        raise ValueError("confirmation requires finalists to be frozen before the N=100 run")
    if confirmation.get("recalibrate_A_on_confirmation") is not False:
        raise ValueError("confirmation must evaluate the exact frozen A; it must not recalibrate A")


def list_unfrozen_phase1_discovery_configuration_fields(
    configuration: dict[str, Any],
) -> list[str]:
    """Return scientific discovery-search fields that are still absent or null.

    The function implements the fail-closed discovery gate: no candidate may be
    evaluated scientifically until all listed physical, horizon, seed-bank and
    search-budget constants have been frozen in a versioned configuration.

    Called by:
        - ``assert_phase1_discovery_configuration_is_frozen`` in this module.
        - ``test_incomplete_discovery_configuration_fails_closed`` in
          ``test_presearch_contract.py``.
    """
    missing: list[str] = []
    for dotted_path in _REQUIRED_DISCOVERY_NON_NULL_PATHS:
        current: Any = configuration
        for component in dotted_path.split("."):
            if not isinstance(current, dict) or component not in current:
                current = None
                break
            current = current[component]
        if current is None:
            missing.append(dotted_path)
    return sorted(missing)


def assert_phase1_discovery_configuration_is_frozen(configuration: dict[str, Any]) -> None:
    """Reject scientific N=10 discovery until the pre-search freeze is complete.

    This gate checks the technology-neutral scientific invariants, the N=10
    discovery budget, and the physical/search constants required before any
    candidate white-box regime is evaluated.

    Called by:
        - Future Phase-1 scientific discovery-search entry point.
        - ``test_incomplete_discovery_configuration_fails_closed`` and
          ``test_complete_discovery_configuration_passes_contract`` in
          ``test_presearch_contract.py``.
    """
    assert_phase1_sampling_policy_is_consistent(configuration)
    missing = list_unfrozen_phase1_discovery_configuration_fields(configuration)
    if missing:
        raise ValueError(
            "Phase-1 discovery configuration is not frozen: " + ", ".join(missing)
        )

    provider_family = configuration["provider_family"]
    calibration = configuration["admissibility_calibration"]
    discovery_search = configuration["discovery_search"]
    horizon = configuration["horizon"]

    if provider_family.get("instruction_message_field") != "Message.instructions":
        raise ValueError("native stochasticity must enter through Message.instructions")
    if provider_family.get("direct_sampling_of_L_C_Q") is not False:
        raise ValueError("L, C, and Q must be simulator-derived, never directly sampled")
    if float(calibration.get("anchor_horizon")) != 120.0:
        raise ValueError("anchor_horizon must remain frozen at 120")
    if float(calibration.get("target_survival")) != 0.95:
        raise ValueError("target_survival must remain frozen at 0.95")
    if int(discovery_search.get("n_trajectories_per_candidate")) != 10:
        raise ValueError("scientific discovery must use N=10 trajectories per candidate")
    discovery_seeds = discovery_search.get("calibration_seed_bank")
    if (
        not isinstance(discovery_seeds, list)
        or len(discovery_seeds) != 10
        or len(set(discovery_seeds)) != 10
    ):
        raise ValueError("scientific discovery must define exactly 10 unique common seeds")
    if float(horizon.get("minimum")) != 0.0 or float(horizon.get("maximum")) != 240.0:
        raise ValueError("Phase-1 horizon domain must remain [0, 240]")


def assert_phase1_confirmation_configuration_is_ready(
    configuration: dict[str, Any],
    selected_whiteboxes_manifest: dict[str, Any],
) -> None:
    """Reject N=100 confirmation until exact discovery finalists are frozen.

    Confirmation is not another search/calibration loop. Each selected white box
    must preserve its discovery physical parameters and exact admissibility region
    ``A=(l_max,c_max,q_min)``. The N=100 seed bank must be unique and disjoint
    from the N=10 discovery seed bank.

    Called by:
        - Future Phase-1 selected-whitebox confirmation runner.
        - confirmation-gate tests in ``test_presearch_contract.py``.
    """
    assert_phase1_discovery_configuration_is_frozen(configuration)
    assert_phase1_sampling_policy_is_consistent(configuration)

    confirmation = configuration["confirmation"]
    confirmation_seeds = confirmation.get("confirmation_seed_bank")
    if (
        not isinstance(confirmation_seeds, list)
        or len(confirmation_seeds) != 100
        or len(set(confirmation_seeds)) != 100
    ):
        raise ValueError("confirmation must define exactly 100 unique fresh seeds")

    discovery_seeds = set(configuration["discovery_search"]["calibration_seed_bank"])
    if discovery_seeds.intersection(confirmation_seeds):
        raise ValueError("confirmation seed bank must be disjoint from the N=10 discovery seed bank")

    if selected_whiteboxes_manifest.get("status") != "FROZEN_FOR_CONFIRMATION":
        raise ValueError("selected whiteboxes must have status FROZEN_FOR_CONFIRMATION")
    whiteboxes = selected_whiteboxes_manifest.get("whiteboxes")
    if not isinstance(whiteboxes, list) or not whiteboxes:
        raise ValueError("at least one discovery whitebox must be frozen for confirmation")

    seen_case_ids: set[str] = set()
    for whitebox in whiteboxes:
        if not isinstance(whitebox, dict):
            raise ValueError("each selected whitebox must be a dictionary")
        missing = [field for field in _REQUIRED_SELECTED_WHITEBOX_FIELDS if field not in whitebox]
        if missing:
            raise ValueError(
                "selected whitebox missing required fields: " + ", ".join(sorted(missing))
            )
        case_id = str(whitebox["case_id"])
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate selected whitebox case_id: {case_id}")
        seen_case_ids.add(case_id)
        if float(whitebox["center_instruction_mean"]) <= 0.0:
            raise ValueError("selected center_instruction_mean must be positive")
        dispersion = float(whitebox["dispersion"])
        if not 0.0 <= dispersion < 1.0:
            raise ValueError("selected dispersion must satisfy 0 <= dispersion < 1")
        if float(whitebox["l_max"]) < 0.0 or float(whitebox["c_max"]) < 0.0:
            raise ValueError("selected l_max and c_max must be non-negative")


def create_contract_complete_test_configuration(configuration: dict[str, Any]) -> dict[str, Any]:
    """Create an artificial discovery-complete config used only by unit tests.

    The inserted values are test fixtures and must never be copied into the
    scientific configuration. They only exercise validation logic.

    Called by:
        - ``test_complete_discovery_configuration_passes_contract`` in
          ``test_presearch_contract.py``.
        - ``create_confirmation_ready_test_configuration`` in this module.
    """
    cfg = deepcopy(configuration)
    cfg["graph"]["pre_module_behavior"] = {"TEST_ONLY": True}
    cfg["graph"]["post_module_behavior"] = {"TEST_ONLY": True}
    cfg["workload"]["period"] = 1.0
    cfg["workload"]["phase"] = 0.0
    cfg["topology"]["placement"] = {"TEST_ONLY": True}
    cfg["topology"]["link_parameters"] = {"TEST_ONLY": True}
    cfg["provider_family"]["instruction_cv"] = 0.3
    cfg["provider_family"]["effective_ipt"] = 1.0
    cfg["provider_family"]["cost_rate"] = 1.0
    cfg["provider_family"]["x"] = 0.5
    cfg["provider_parameterization"]["center_instruction_mean_bounds"] = [1.0, 2.0]
    cfg["provider_parameterization"]["dispersion_bounds"] = [0.0, 0.2]
    cfg["horizon"]["grid"] = [0.0, 120.0, 240.0]
    cfg["horizon"]["simulation_stop_time"] = 240.0
    cfg["discovery_search"]["calibration_seed_bank"] = list(range(1100, 1110))
    cfg["discovery_search"]["search_method"] = "TEST_ONLY"
    cfg["discovery_search"]["initial_design_size"] = 1
    cfg["discovery_search"]["total_candidate_budget"] = 1
    return cfg


def create_confirmation_ready_test_configuration(configuration: dict[str, Any]) -> dict[str, Any]:
    """Create a test-only config with fresh N=100 confirmation seeds.

    Called by:
        - confirmation-gate tests in ``test_presearch_contract.py``.
    """
    cfg = create_contract_complete_test_configuration(configuration)
    cfg["confirmation"]["confirmation_seed_bank"] = list(range(2000, 2100))
    return cfg


def create_frozen_selected_whitebox_test_manifest() -> dict[str, Any]:
    """Create one test-only frozen discovery finalist for confirmation tests.

    Called by:
        - confirmation-gate tests in ``test_presearch_contract.py``.
    """
    return {
        "status": "FROZEN_FOR_CONFIRMATION",
        "whiteboxes": [
            {
                "case_id": "TEST_MIXED",
                "selection_role": "mixed",
                "physical_setting_id": "DTEST_d0.100",
                "center_instruction_mean": 1.5,
                "dispersion": 0.1,
                "l_max": 2.0,
                "c_max": 3.0,
                "q_min": 0.5,
            }
        ],
    }


# Compatibility aliases retained while the scientific runner is still being built.
def assert_phase1_presearch_configuration_is_frozen(configuration: dict[str, Any]) -> None:
    """Compatibility alias for the N=10 scientific discovery gate."""
    assert_phase1_discovery_configuration_is_frozen(configuration)


def list_unfrozen_phase1_presearch_configuration_fields(
    configuration: dict[str, Any],
) -> list[str]:
    """Compatibility alias for discovery-specific missing-field reporting."""
    return list_unfrozen_phase1_discovery_configuration_fields(configuration)


def assert_phase1_development_smoke_budget_is_separate_from_scientific_coarse_search(
    configuration: dict[str, Any],
) -> None:
    """Compatibility alias for the current discovery/confirmation sampling policy."""
    assert_phase1_sampling_policy_is_consistent(configuration)
