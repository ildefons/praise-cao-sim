"""Non-scientific preflight smoke for the frozen P4 I2b reconstruction.

Runs exactly one already-frozen initial Sobol parameter point for ProviderA on
two search-bank seeds.  Purpose: verify the public-target loader, provider
simulation adapter, same-trajectory temporal pairing, and energy scorer before
the long 256-trial reconstruction.

The smoke is not a scientific result and must not alter any frozen choice.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row  # noqa:E402
from run_phase6_i2a_fullspectrum_reconstruction_p4_v1 import _sobol_initial_points  # noqa:E402
from run_phase6_i2b_energy_reconstruction_p4_v1 import (  # noqa:E402
    WORLD,
    _assert_contracts,
    _load_i2b_target,
    _score_i2b,
)


def main()->None:
    cfg=_assert_contracts()
    provider="ProviderA"
    metadata,target,_=_load_i2b_target(provider)
    bounds=_bounds(_domain_row(WORLD,provider))
    p=_sobol_initial_points(
        int(cfg["search"]["sobol_initial_trials"]),
        int(cfg["search"]["sobol_seed"]),
        bounds,
    )[0]
    seeds=(int(cfg["search"]["search_seed_start"]),
           int(cfg["search"]["search_seed_start"])+1)
    score,by_lag=_score_i2b(
        metadata=metadata,
        target=target,
        mean_service_time=float(p["mean_service_time"]),
        cost_rate=float(p["cost_rate"]),
        service_cv=float(p["service_cv"]),
        seeds=seeds,
    )
    if score<0:
        raise RuntimeError("negative smoke score")
    print("PHASE6_I2B_ENERGY_RECONSTRUCTION_SMOKE_PASS")
    print("provider",provider)
    print("seeds",seeds)
    print("frozen_sobol_point_0",p)
    print("overall_energy_vstat",score)
    print(by_lag[["lag_s","window_count","mean_energy_vstat"]].to_string(index=False))
    print("scientific_result False")
    print("frozen_choice_changed False")


if __name__=="__main__":
    main()
