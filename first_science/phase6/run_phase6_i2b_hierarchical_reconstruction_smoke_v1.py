"""Non-scientific preflight smoke for I2b-v3 hierarchical reconstruction."""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row  # noqa:E402
from run_phase6_i2a_fullspectrum_reconstruction_p4_v1 import _sobol_initial_points  # noqa:E402
from run_phase6_i2b_hierarchical_reconstruction_p4_v1 import (  # noqa:E402
    WORLD,
    _assert_contracts,
    _load_i2b_target,
    _target_weights,
    _score_params,
)


def main()->None:
    cfg=_assert_contracts()
    provider="ProviderA"
    metadata,target,_=_load_i2b_target(provider)
    weights=_target_weights(target)

    # Contract checks on the frozen hierarchical weights.
    regions=sorted({k[0] for k in weights})
    lags=sorted({k[1] for k in weights})
    for rid in regions:
        mass=sum(w for (r,_,_,_),w in weights.items() if r==rid)
        if abs(mass-0.2)>1e-12:
            raise RuntimeError(f"region mass invariant failed for {rid}: {mass}")
    for lag in lags:
        mass=sum(w for (_,d,_,_),w in weights.items() if d==lag)
        if abs(mass-0.125)>1e-12:
            raise RuntimeError(f"lag mass invariant failed for {lag}: {mass}")
    vals=np.asarray(list(weights.values()),dtype=float)

    bounds=_bounds(_domain_row(WORLD,provider))
    params=_sobol_initial_points(
        int(cfg["search"]["sobol_initial_trials"]),
        int(cfg["search"]["sobol_seed"]),
        bounds,
    )[0]
    seeds=(
        int(cfg["search"]["search_seed_start"]),
        int(cfg["search"]["search_seed_start"])+1,
    )
    score,by_lag,_=_score_params(
        metadata=metadata,target=target,weights=weights,
        mu=float(params["mean_service_time"]),
        cost=float(params["cost_rate"]),
        cv=float(params["service_cv"]),
        seeds=seeds,
    )
    if score<0:
        raise RuntimeError("negative I2b-v3 smoke score")

    print("PHASE6_I2B_HIERARCHICAL_RECONSTRUCTION_SMOKE_PASS")
    print("provider",provider)
    print("seeds",seeds)
    print("max_window_weight",float(vals.max()))
    print("effective_window_count",float(1.0/np.sum(vals*vals)))
    print("frozen_sobol_point_0",params)
    print("hierarchical_energy",score)
    print(by_lag[["lag_s","weight_mass","weighted_energy_contribution"]].to_string(index=False))
    print("scientific_result False")
    print("frozen_choice_changed False")


if __name__=="__main__":
    main()
