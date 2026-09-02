"""Phase-1 pre-search contract for the first PRAISE scientific experiment.

This module is deliberately simulator-independent.  It prevents the Phase-1
reference-regime search from starting before every required pre-search constant
has been explicitly frozen in ``config_phase1.json``.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderInstructionMeanTriplet:
    """Hold the native gamma-instruction means for providers A, B, and C.

    The values parameterize the native per-request ``Message.instructions``
    distributions. They do not parameterize latency, cost, or quality directly.

    Called by:
        - ``calculate_symmetric_provider_instruction_means`` in this module.
        - Phase-1 native reference-search code once that runner is implemented.
    """

    provider_a: float
    provider_b: float
    provider_c: float


_REQUIRED_NON_NULL_PATHS = (
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
    "coarse_search.calibration_seed_bank",
    "coarse_search.search_method",
    "coarse_search.initial_design_size",
    "coarse_search.total_candidate_budget",
)


def calculate_symmetric_provider_instruction_means(
    center_instruction_mean: float,
    dispersion: float,
) -> ProviderInstructionMeanTriplet:
    """Calculate A/B/C native instruction-demand means from center and dispersion.

    Provider A receives ``center * (1-dispersion)``, B receives ``center``, and
    C receives ``center * (1+dispersion)``.  This only parameterizes the native
    stochastic ``Message.instructions`` field; AICon/YAFS must causally generate
    service time, queueing, latency, cost, and quality from the simulated graph.

    Args:
        center_instruction_mean: Positive central nominal instruction mean.
        dispersion: Multiplicative provider dispersion satisfying ``0 <= d < 1``.

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


def list_unfrozen_phase1_presearch_configuration_fields(configuration: dict[str, Any]) -> list[str]:
    """Return required Phase-1 pre-search fields that are still absent or null.

    The function implements the fail-closed gate required by the design: no
    reference-regime candidate may be evaluated until all listed physical,
    horizon, seed-bank, and search-budget constants have been frozen once in a
    versioned configuration.

    Args:
        configuration: Parsed ``config_phase1.json`` dictionary.

    Returns:
        Sorted dotted paths whose values are missing or ``None``.

    Called by:
        - ``assert_phase1_presearch_configuration_is_frozen`` in this module.
        - ``test_incomplete_configuration_fails_closed`` in
          ``test_presearch_contract.py``.
    """
    missing: list[str] = []
    for dotted_path in _REQUIRED_NON_NULL_PATHS:
        current: Any = configuration
        for component in dotted_path.split("."):
            if not isinstance(current, dict) or component not in current:
                current = None
                break
            current = current[component]
        if current is None:
            missing.append(dotted_path)
    return sorted(missing)


def assert_phase1_presearch_configuration_is_frozen(configuration: dict[str, Any]) -> None:
    """Reject a Phase-1 scientific run until the pre-search freeze is complete.

    This gate also checks a small set of already-frozen scientific invariants:
    Step 0 remains technology-neutral; L/C/Q are not directly sampled; the
    anchor is H*=120 with target 0.95; and the coarse candidate budget is N=100.

    Args:
        configuration: Parsed ``config_phase1.json`` dictionary.

    Raises:
        ValueError: If required constants are unfrozen or frozen invariants are
            violated.

    Called by:
        - Future Phase-1 ``main.py`` entry point before any AICon/YAFS run.
        - ``test_incomplete_configuration_fails_closed`` and
          ``test_complete_configuration_passes_contract`` in
          ``test_presearch_contract.py``.
    """
    missing = list_unfrozen_phase1_presearch_configuration_fields(configuration)
    if missing:
        raise ValueError("Phase-1 pre-search configuration is not frozen: " + ", ".join(missing))

    provider_family = configuration["provider_family"]
    calibration = configuration["admissibility_calibration"]
    coarse_search = configuration["coarse_search"]
    horizon = configuration["horizon"]

    if provider_family.get("instruction_message_field") != "Message.instructions":
        raise ValueError("native stochasticity must enter through Message.instructions")
    if provider_family.get("direct_sampling_of_L_C_Q") is not False:
        raise ValueError("L, C, and Q must be simulator-derived, never directly sampled")
    if float(calibration.get("anchor_horizon")) != 120.0:
        raise ValueError("anchor_horizon must remain frozen at 120")
    if float(calibration.get("target_survival")) != 0.95:
        raise ValueError("target_survival must remain frozen at 0.95")
    if int(coarse_search.get("n_trajectories_per_candidate")) != 100:
        raise ValueError("coarse search must use N=100 trajectories per candidate")
    if float(horizon.get("minimum")) != 0.0 or float(horizon.get("maximum")) != 240.0:
        raise ValueError("Phase-1 horizon domain must remain [0, 240]")


def create_contract_complete_test_configuration(configuration: dict[str, Any]) -> dict[str, Any]:
    """Create an artificial complete config used only by contract unit tests.

    The inserted values are intentionally marked as test fixtures and must never
    be copied into the scientific configuration.  Their only purpose is to
    exercise the validation logic without inventing Phase-1 scientific defaults.

    Args:
        configuration: Parsed incomplete scientific configuration.

    Returns:
        Deep-copied configuration with synthetic test-only values filled in.

    Called by:
        - ``test_complete_configuration_passes_contract`` in
          ``test_presearch_contract.py`` only.
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
    cfg["coarse_search"]["calibration_seed_bank"] = [1, 2]
    cfg["coarse_search"]["search_method"] = "TEST_ONLY"
    cfg["coarse_search"]["initial_design_size"] = 1
    cfg["coarse_search"]["total_candidate_budget"] = 1
    return cfg
