"""Non-scientific preflight smoke for I2b-v2 variability-weight reconstruction."""
from __future__ import annotations

import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row  # noqa:E402
from run_phase6_i2a_fullspectrum_reconstruction_p4_v1 import _sobol_initial_points  # noqa:E402
from run_phase6_i2b_varweight_reconstruction_p4_v1 import (  # noqa:E402
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
        raise RuntimeError("negative I2b-v2 smoke score")
    print("PHASE6_I2B_VARWEIGHT_RECONSTRUCTION_SMOKE_PASS")
    print("provider",provider)
    print("seeds",seeds)
    print("frozen_sobol_point_0",params)
    print("weighted_energy",score)
    print(by_lag[["lag_s","weight_mass","weighted_energy_contribution"]].to_string(index=False))
    print("scientific_result False")
    print("frozen_choice_changed False")


if __name__=="__main__":
    main()
