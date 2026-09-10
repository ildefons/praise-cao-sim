"""Simulator-independent regression tests for the frozen Phase-3 M0 contract."""
from __future__ import annotations

from math import isclose

from m0_analytic_composition import (
    AdmissibilityBoundary,
    boundary_is_sufficient_for_query,
    compose_graph_boundary,
    compose_parallel_all,
    compose_sequence,
    equal_violation_budget_rhos,
    evaluate_independent_m0_certificate,
    independent_product_probability,
)


def main() -> None:
    a = AdmissibilityBoundary(l_max=1.0, c_max=2.0, q_min=0.9)
    b = AdmissibilityBoundary(l_max=3.0, c_max=4.0, q_min=0.8)

    sequential = compose_sequence([a, b])
    assert sequential == AdmissibilityBoundary(l_max=4.0, c_max=6.0, q_min=0.8)

    parallel = compose_parallel_all([a, b])
    assert parallel == AdmissibilityBoundary(l_max=3.0, c_max=6.0, q_min=0.8)

    # Hand-checkable nested graph: deterministic pre -> ParAll(A,B) -> deterministic post.
    graph = {
        "type": "sequence",
        "children": [
            {"type": "leaf", "id": "pre"},
            {
                "type": "parallel_all",
                "children": [
                    {"type": "leaf", "id": "ProviderA"},
                    {"type": "leaf", "id": "ProviderB"},
                ],
            },
            {"type": "leaf", "id": "post"},
        ],
    }
    leaves = {
        "pre": AdmissibilityBoundary(0.01, 0.03, 1.0),
        "ProviderA": AdmissibilityBoundary(0.20, 0.60, 0.5),
        "ProviderB": AdmissibilityBoundary(0.30, 0.80, 0.5),
        "post": AdmissibilityBoundary(0.02, 0.03, 1.0),
    }
    nested = compose_graph_boundary(graph, leaves)
    assert isclose(nested.l_max, 0.33, abs_tol=1e-12)
    assert isclose(nested.c_max, 1.46, abs_tol=1e-12)
    assert isclose(nested.q_min, 0.5, abs_tol=1e-12)

    requested_looser = AdmissibilityBoundary(0.35, 1.50, 0.5)
    requested_too_strict_cost = AdmissibilityBoundary(0.35, 1.40, 0.5)
    assert boundary_is_sufficient_for_query(nested, requested_looser)
    assert not boundary_is_sufficient_for_query(nested, requested_too_strict_cost)

    rho_local = equal_violation_budget_rhos(
        0.95, ["ProviderA", "ProviderB", "ProviderC"]
    )
    assert set(rho_local) == {"ProviderA", "ProviderB", "ProviderC"}
    for rho in rho_local.values():
        assert isclose(rho, 0.9833333333333333, abs_tol=1e-15)

    product = independent_product_probability(
        {"ProviderA": 0.8, "ProviderB": 0.9, "ProviderC": 0.95}
    )
    assert isclose(product, 0.684, abs_tol=1e-12)

    certified = evaluate_independent_m0_certificate(
        induced_global_boundary=nested,
        requested_global_boundary=requested_looser,
        rho_global=0.95,
        provider_sigma={"ProviderA": 0.8, "ProviderB": 0.9},
        accounting_aligned=True,
        independent_local_events=True,
        card_points_available=True,
    )
    assert certified.certified
    assert certified.status == "CERTIFIED"
    assert isclose(float(certified.sigma_lower), 0.72, abs_tol=1e-12)
    assert certified.failed_preconditions == ()

    not_certified = evaluate_independent_m0_certificate(
        induced_global_boundary=nested,
        requested_global_boundary=requested_too_strict_cost,
        rho_global=0.95,
        provider_sigma={"ProviderA": 0.8, "ProviderB": 0.9},
        accounting_aligned=False,
        independent_local_events=False,
        card_points_available=False,
    )
    assert not not_certified.certified
    assert not_certified.sigma_lower is None
    assert not_certified.failed_preconditions == (
        "induced_boundary_not_contained_in_requested_A_G",
        "local_global_request_accounting_not_aligned",
        "required_local_events_not_established_independent",
        "required_I1_H_rho_points_not_available",
    )

    # M0 has no inverse A_G -> A_i construction path.
    public_names = {
        compose_graph_boundary.__name__,
        equal_violation_budget_rhos.__name__,
        evaluate_independent_m0_certificate.__name__,
    }
    assert "derive_local_regions_from_global" not in public_names

    print("PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS")
    print("M0_FORWARD_BOUNDARY_ALGEBRA_PASS")
    print("M0_EQUAL_VIOLATION_BUDGET_PASS")
    print("M0_INDEPENDENT_CERTIFICATE_GUARD_PASS")


if __name__ == "__main__":
    main()
