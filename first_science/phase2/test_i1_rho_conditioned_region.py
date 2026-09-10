"""Simulator-independent tests for rho-conditioned joint-GMM A_i construction."""
from __future__ import annotations

from math import isclose

import numpy as np
import pandas as pd

from i1_rho_conditioned_region import (
    _minimum_area_box_for_mass,
    derive_nested_rho_regions,
    fit_log_lc_gmm,
)


def _synthetic_provider(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | int]] = []
    for trajectory in range(12):
        component = rng.uniform(size=80) < 0.7
        z = np.empty((80, 2), dtype=float)
        z[component] = rng.multivariate_normal(
            mean=[-1.4, -0.35],
            cov=[[0.05, 0.025], [0.025, 0.07]],
            size=int(component.sum()),
        )
        z[~component] = rng.multivariate_normal(
            mean=[-0.75, 0.15],
            cov=[[0.04, 0.02], [0.02, 0.05]],
            size=int((~component).sum()),
        )
        lc = np.exp(z)
        for request_id, (latency, cost) in enumerate(lc):
            rows.append(
                {
                    "trajectory": trajectory,
                    "request_id": request_id,
                    "completion": 1.0,
                    "L": float(latency),
                    "C": float(cost),
                    "Q": 0.5,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    samples = np.array(
        [[1.0, 4.0], [2.0, 2.0], [3.0, 1.0], [4.0, 3.0]], dtype=float
    )
    l_max, c_max, coverage = _minimum_area_box_for_mass(samples, 0.5)
    assert isclose(l_max, 3.0, abs_tol=1e-12)
    assert isclose(c_max, 2.0, abs_tol=1e-12)
    assert isclose(coverage, 0.5, abs_tol=1e-12)

    ledger = _synthetic_provider()
    fit = fit_log_lc_gmm(ledger, max_components=3, random_state=1234)
    assert 1 <= fit.n_components <= 3
    assert set(fit.bic_by_components) == {1, 2, 3}
    assert fit.n_fit_rows == len(ledger)
    assert isclose(fit.q_value, 0.5, abs_tol=1e-12)

    rhos = (0.80, 0.90, 0.95)
    regions_1, audit_1 = derive_nested_rho_regions(
        ledger,
        rhos,
        max_components=3,
        model_samples=4000,
        random_state=1234,
    )
    regions_2, audit_2 = derive_nested_rho_regions(
        ledger,
        rhos,
        max_components=3,
        model_samples=4000,
        random_state=1234,
    )
    assert regions_1 == regions_2
    pd.testing.assert_frame_equal(audit_1, audit_2)
    assert [float(r["region_rho"]) for r in regions_1] == list(rhos)
    for previous, current in zip(regions_1, regions_1[1:]):
        assert float(current["l_max"]) >= float(previous["l_max"]) - 1e-12
        assert float(current["c_max"]) >= float(previous["c_max"]) - 1e-12
        assert isclose(
            float(current["q_min"]),
            float(previous["q_min"]),
            abs_tol=1e-12,
        )
    assert np.all(
        audit_1["synthetic_model_coverage"].to_numpy(dtype=float)
        + 1.0 / 4000
        >= audit_1["region_rho"].to_numpy(dtype=float)
    )

    try:
        derive_nested_rho_regions(ledger, (0.95, 1.0), model_samples=2000)
    except ValueError:
        pass
    else:
        raise AssertionError("rho_region=1 must be rejected for finite GMM regions")

    nondegenerate_q = ledger.copy()
    nondegenerate_q.loc[0, "Q"] = 0.6
    try:
        fit_log_lc_gmm(nondegenerate_q)
    except NotImplementedError:
        pass
    else:
        raise AssertionError(
            "non-degenerate Q must be blocked in this benchmark-specific version"
        )

    print("PHASE2_RHO_CONDITIONED_REGION_TESTS_PASS")
    print("JOINT_LOG_LC_GMM_BIC_PASS")
    print("MINIMUM_AREA_JOINT_MASS_BOX_PASS")
    print("NESTED_A_I_OF_RHO_PASS")
    print("FINITE_GMM_RHO_ONE_BLOCKED_PASS")
    print("NONDEGENERATE_Q_NOT_SILENTLY_GENERALIZED_PASS")


if __name__ == "__main__":
    main()
