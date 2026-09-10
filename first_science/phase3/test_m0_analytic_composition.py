"""Simulator-independent regression tests for the frozen Phase-3 M0 baseline."""
from __future__ import annotations

from math import isclose

from m0_analytic_composition import (
    AdmissibilityBoundary,
    boundary_is_sufficient_for_query,
    compose_graph_boundary,
    compose_parallel_all,
    compose_sequence,
    evaluate_independent_m0_prediction,
    independent_product_probability,
    same_rho_as_global,
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

    # Frozen M0 rho policy: every provider is read at exactly rho_G.
    rho_local = same_rho_as_global(
        0.95, ["ProviderA", "ProviderB", "ProviderC"]
    )
    assert rho_local == {
        "ProviderA": 0.95,
        "ProviderB": 0.95,
        "ProviderC": 0.95,
    }

    product = independent_product_probability(
        {"ProviderA": 0.8, "ProviderB": 0.9, "ProviderC": 0.95}
    )
    assert isclose(product, 0.684, abs_tol=1e-12)

    predicted = evaluate_independent_m0_prediction(
        induced_global_boundary=nested,
        requested_global_boundary=requested_looser,
        rho_global=0.95,
        provider_sigma={"ProviderA": 0.8, "ProviderB": 0.9},
        card_points_available=True,
    )
    assert predicted.predicted
    assert predicted.status == "PREDICTED"
    assert isclose(float(predicted.sigma_hat), 0.72, abs_tol=1e-12)
    assert predicted.rho_local == {"ProviderA": 0.95, "ProviderB": 0.95}
    assert predicted.failed_preconditions == ()

    # M0 does not reinterpret this product as a certificate/lower bound.
    assert not hasattr(predicted, "sigma_lower")
    assert not hasattr(predicted, "certified")

    not_applicable = evaluate_independent_m0_prediction(
        induced_global_boundary=nested,
        requested_global_boundary=requested_too_strict_cost,
        rho_global=0.95,
        provider_sigma={"ProviderA": 0.8, "ProviderB": 0.9},
        card_points_available=False,
    )
    assert not not_applicable.predicted
    assert not_applicable.status == "NOT_APPLICABLE"
    assert not_applicable.sigma_hat is None
    assert not_applicable.failed_preconditions == (
        "induced_boundary_not_contained_in_requested_A_G",
        "required_I1_H_rho_points_not_available",
    )

    # M0 has no inverse A_G -> A_i construction and no rho-budget allocator.
    public_names = {
        compose_graph_boundary.__name__,
        same_rho_as_global.__name__,
        evaluate_independent_m0_prediction.__name__,
    }
    assert "derive_local_regions_from_global" not in public_names
    assert "equal_violation_budget_rhos" not in public_names

    print("PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS")
    print("M0_FORWARD_BOUNDARY_ALGEBRA_PASS")
    print("M0_SAME_RHO_POLICY_PASS")
    print("M0_INDEPENDENT_PRODUCT_BASELINE_PASS")
    print("M0_NOT_A_CERTIFICATE_PASS")


if __name__ == "__main__":
    main()
