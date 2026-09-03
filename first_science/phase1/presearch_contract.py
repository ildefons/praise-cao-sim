"""Phase-1 discovery and confirmation contracts for the PRAISE SLA benchmark.

This simulator-independent module turns source-of-truth design decisions into
machine-checkable invariants. It prevents scientific discovery/confirmation from
running after configuration drift. The current primary sigma is SLA compliance:
P(c_G(A,H) >= rho*) with rho*=0.95 and cumulative [0,H] accounting from t=0.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from selection_policy import load_sla_compliance_area_selection_policy


@dataclass(frozen=True)
class ProviderInstructionMeanTriplet:
    """Hold A/B/C mean service-instruction requirements per invocation.

    Called by:
        - ``calculate_symmetric_provider_instruction_means`` in this module.
        - Phase-1 parameterization tests.
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
    "sla_compliance.search_rho",
    "sla_compliance.accounting_origin",
    "sla_compliance.zero_decided_requests_compliance",
    "sla_compliance.accounting_window",
    "selection_quality_gate.normalized_sla_compliance_area",
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
    "rho",
    "accounting_origin",
    "accounting_window",
)


def calculate_symmetric_provider_instruction_means(
    center_instruction_mean: float,
    dispersion: float,
) -> ProviderInstructionMeanTriplet:
    """Calculate symmetric A/B/C service-instruction means.

    Args:
        center_instruction_mean: Positive central mean instructions/invocation.
        dispersion: Provider-to-provider multiplicative heterogeneity.

    Returns:
        ProviderInstructionMeanTriplet with A=center(1-d), B=center,
        C=center(1+d).

    Side effects:
        None.

    Called by:
        - ``test_symmetric_provider_instruction_parameterization`` in
          ``test_presearch_contract.py``.
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


def assert_phase1_sampling_policy_is_consistent(
    configuration: dict[str, Any],
) -> None:
    """Validate N=10 discovery / fresh N=100 confirmation separation.

    Called by:
        - discovery and confirmation contract assertions in this module.
        - ``test_presearch_contract.py``.
    """
    development = configuration.get("development_smoke", {})
    discovery = configuration.get("discovery_search", {})
    confirmation = configuration.get("confirmation", {})

    if int(development.get("n_trajectories", -1)) != 10:
        raise ValueError("Phase-1 development smoke must use N=10")
    development_seeds = development.get("seed_bank")
    if (
        not isinstance(development_seeds, list)
        or len(development_seeds) != 10
        or len(set(development_seeds)) != 10
    ):
        raise ValueError("development smoke must define 10 unique seeds")
    if development.get("scientific_evidence") is not False:
        raise ValueError("development smoke must remain non-scientific")

    if int(discovery.get("n_trajectories_per_candidate", -1)) != 10:
        raise ValueError("scientific white-box discovery must use N=10")
    if discovery.get("common_seed_bank_across_candidates") is not True:
        raise ValueError("discovery must use a common seed bank across settings")

    if int(confirmation.get("n_trajectories_per_selected_whitebox", -1)) != 100:
        raise ValueError("selected-whitebox confirmation must use N=100")
    if confirmation.get("fresh_seeds_required") is not True:
        raise ValueError("confirmation must require fresh seeds")
    if confirmation.get("selected_whiteboxes_must_be_frozen_before_run") is not True:
        raise ValueError("confirmation requires frozen selected white boxes")
    if confirmation.get("recalibrate_A_on_confirmation") is not False:
        raise ValueError("confirmation must not recalibrate A")


def list_unfrozen_phase1_discovery_configuration_fields(
    configuration: dict[str, Any],
) -> list[str]:
    """Return required scientific discovery fields that are absent or null.

    Called by:
        - ``assert_phase1_discovery_configuration_is_frozen`` in this module.
        - ``test_presearch_contract.py``.
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


def assert_phase1_sla_semantics_are_frozen(
    configuration: dict[str, Any],
) -> None:
    """Reject drift from rho*=0.95 cumulative [0,H]-from-t=0 semantics.

    Called by:
        - discovery and confirmation contract assertions in this module.
        - SLA contract tests.
    """
    sla = configuration.get("sla_compliance", {})
    if abs(float(sla.get("search_rho", -1.0)) - 0.95) > 1e-12:
        raise ValueError("Phase-1 search rho must remain frozen at 0.95")
    if abs(float(sla.get("accounting_origin", -1.0))) > 1e-12:
        raise ValueError("Phase-1 SLA accounting origin must remain t=0")
    if sla.get("accounting_window") != "cumulative_[0,H]_from_t0":
        raise ValueError("SLA accounting must remain cumulative [0,H] from t=0")
    if sla.get("rolling_windows_allowed") is not False:
        raise ValueError("rolling/restarted SLA windows are forbidden")
    if abs(float(sla.get("zero_decided_requests_compliance", -1.0)) - 1.0) > 1e-12:
        raise ValueError("zero-decided-request compliance convention must remain 1")
    if sla.get("alternative_rho_values_may_drive_search") is not False:
        raise ValueError("alternative rho values may not drive Phase-1 search")


def assert_phase1_discovery_configuration_is_frozen(
    configuration: dict[str, Any],
) -> None:
    """Reject scientific N=10 discovery/reranking after design drift.

    Called by:
        - ``whitebox_scientific_discovery.py``.
        - ``test_presearch_contract.py``.
    """
    assert_phase1_sampling_policy_is_consistent(configuration)
    missing = list_unfrozen_phase1_discovery_configuration_fields(configuration)
    if missing:
        raise ValueError(
            "Phase-1 discovery configuration is not frozen: "
            + ", ".join(missing)
        )
    assert_phase1_sla_semantics_are_frozen(configuration)
    policy = load_sla_compliance_area_selection_policy(configuration)

    provider = configuration["provider_family"]
    discovery = configuration["discovery_search"]
    horizon = configuration["horizon"]

    if provider.get("instruction_message_field") != "Message.instructions":
        raise ValueError(
            "native stochasticity must enter through Message.instructions"
        )
    if provider.get("direct_sampling_of_L_C_Q") is not False:
        raise ValueError("L, C and Q must be simulator-derived")
    if int(discovery.get("n_trajectories_per_candidate")) != 10:
        raise ValueError("scientific discovery must use N=10")
    discovery_seeds = discovery.get("calibration_seed_bank")
    if (
        not isinstance(discovery_seeds, list)
        or len(discovery_seeds) != 10
        or len(set(discovery_seeds)) != 10
    ):
        raise ValueError("scientific discovery requires 10 unique common seeds")
    if (
        float(horizon.get("minimum")) != 0.0
        or float(horizon.get("maximum")) != 240.0
        or float(horizon.get("simulation_stop_time")) != 240.0
    ):
        raise ValueError("Phase-1 physical horizon must remain [0,240]")
    if abs(policy.horizon_min - 0.0) > 1e-12 or abs(policy.horizon_max - 240.0) > 1e-12:
        raise ValueError("current SLA-compliance area must use [0,240]")


def assert_phase1_confirmation_configuration_is_ready(
    configuration: dict[str, Any],
    selected_whiteboxes_manifest: dict[str, Any],
) -> None:
    """Reject N=100 confirmation until revised SLA finalists are frozen.

    The seed bank must contain 100 unique seeds disjoint from development,
    discovery and every explicitly recorded inspected/exploratory N=100 bank.
    Each frozen case must carry the exact A plus rho/accounting semantics.

    Called by:
        - ``run_n100_matched_confirmation.py``.
        - confirmation contract tests.
    """
    assert_phase1_discovery_configuration_is_frozen(configuration)
    assert_phase1_sampling_policy_is_consistent(configuration)
    assert_phase1_sla_semantics_are_frozen(configuration)

    confirmation_seeds = configuration["confirmation"].get(
        "confirmation_seed_bank"
    )
    if (
        not isinstance(confirmation_seeds, list)
        or len(confirmation_seeds) != 100
        or len(set(confirmation_seeds)) != 100
    ):
        raise ValueError(
            "confirmation must define exactly 100 unique fresh seeds"
        )

    previously_used = set(
        configuration["development_smoke"]["seed_bank"]
    ) | set(
        configuration["discovery_search"]["calibration_seed_bank"]
    )
    exploratory = configuration.get(
        "confirmation_round_1_exploratory", {}
    ).get("seed_bank", [])
    if isinstance(exploratory, list):
        previously_used |= set(exploratory)
    if previously_used.intersection(confirmation_seeds):
        raise ValueError(
            "confirmation seed bank must be disjoint from all prior inspected banks"
        )

    if selected_whiteboxes_manifest.get("status") != "FROZEN_FOR_CONFIRMATION":
        raise ValueError(
            "selected whiteboxes must have status FROZEN_FOR_CONFIRMATION"
        )
    whiteboxes = selected_whiteboxes_manifest.get("whiteboxes")
    if not isinstance(whiteboxes, list) or not whiteboxes:
        raise ValueError("at least one white box must be frozen")

    expected_rho = float(configuration["sla_compliance"]["search_rho"])
    seen_case_ids: set[str] = set()
    for whitebox in whiteboxes:
        if not isinstance(whitebox, dict):
            raise ValueError("each selected white box must be a dictionary")
        missing = [
            field
            for field in _REQUIRED_SELECTED_WHITEBOX_FIELDS
            if field not in whitebox
        ]
        if missing:
            raise ValueError(
                "selected whitebox missing required fields: "
                + ", ".join(sorted(missing))
            )
        case_id = str(whitebox["case_id"])
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate selected whitebox case_id: {case_id}")
        seen_case_ids.add(case_id)
        if float(whitebox["center_instruction_mean"]) <= 0.0:
            raise ValueError("selected instruction mean must be positive")
        dispersion = float(whitebox["dispersion"])
        if not 0.0 <= dispersion < 1.0:
            raise ValueError("selected dispersion must satisfy 0 <= d < 1")
        if float(whitebox["l_max"]) < 0.0 or float(whitebox["c_max"]) < 0.0:
            raise ValueError("selected l_max/c_max must be non-negative")
        if abs(float(whitebox["rho"]) - expected_rho) > 1e-12:
            raise ValueError("selected whitebox rho differs from frozen rho*=0.95")
        if abs(float(whitebox["accounting_origin"])) > 1e-12:
            raise ValueError("selected whitebox accounting origin must be t=0")
        if whitebox["accounting_window"] != "cumulative_[0,H]_from_t0":
            raise ValueError("selected whitebox accounting window is inconsistent")


def create_contract_complete_test_configuration(
    configuration: dict[str, Any],
) -> dict[str, Any]:
    """Create a complete artificial config used only by unit tests.

    Called by:
        - ``test_presearch_contract.py``.
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


def create_confirmation_ready_test_configuration(
    configuration: dict[str, Any],
) -> dict[str, Any]:
    """Create a test-only config with fresh N=100 confirmation seeds.

    Called by:
        - ``test_presearch_contract.py``.
    """
    cfg = create_contract_complete_test_configuration(configuration)
    cfg["confirmation"]["confirmation_seed_bank"] = list(range(4000, 4100))
    return cfg


def create_frozen_selected_whitebox_test_manifest() -> dict[str, Any]:
    """Create one test-only frozen SLA finalist manifest.

    Called by:
        - ``test_presearch_contract.py``.
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
                "rho": 0.95,
                "accounting_origin": 0.0,
                "accounting_window": "cumulative_[0,H]_from_t0",
            }
        ],
    }
