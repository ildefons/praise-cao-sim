#!/usr/bin/env python3
"""Read-only exact LHS coordinate and mapped-domain transfer audit.

Compares original Phase4 pilot proposal positions with their counterparts in
P1/P3/P4. Same LHS coordinates need not mean same physical parameter proposal.
No simulator, Step0, reference WB or hidden parameters are loaded.
"""
from pathlib import Path
import numpy as np
import pandas as pd

FIRST = Path(__file__).resolve().parent.parent.parent
P4 = FIRST / "phase4" / "results"
RETRO = FIRST / "phase5" / "results" / "b1_pilot_m3_retrospective_v1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
VARS = ("mean_service_time", "cost_rate", "service_cv")
Z = ("z_log_mu", "z_log_kappa", "z_cv")


def main():
    original = pd.read_csv(P4 / "m2_a2_nonadaptive_coverage_v1" / "m2_a2_lhs_design.csv")
    pilot_w = pd.read_csv(P4 / "m3_lambda_cv_v3" / "m3_v3_provider_weights.csv")
    output = []
    for provider in PROVIDERS:
        old = original[original["provider"].astype(str) == provider].copy()
        old = old.sort_values("lhs_index").reset_index(drop=True)
        if len(old) != 48:
            raise RuntimeError(f"pilot {provider}: expected 48 LHS samples")
        pwt = pilot_w[pilot_w["provider"].astype(str) == provider]
        pilot_idx = int(pwt.loc[pwt["weight_v3"].idxmax(), "lhs_index"])
        for world in ("P1", "P3", "P4"):
            root = RETRO / "candidates" / world / provider
            new = pd.read_csv(root / "lhs_design.csv")
            new["_index"] = new["candidate_id"].astype(str).str.extract(
                r"_LHS_(\d+)$", expand=False
            ).astype(int)
            new = new.sort_values("_index").reset_index(drop=True)
            if len(new) != 48 or new["_index"].tolist() != list(range(48)):
                raise RuntimeError(f"{world}/{provider}: incomplete or unordered LHS")
            coords_equal = bool(np.allclose(
                old[list(Z)].to_numpy(float), new[list(Z)].to_numpy(float),
                rtol=0, atol=1e-14
            ))
            if not coords_equal:
                raise RuntimeError(f"{world}/{provider}: normalized LHS changed!")
            new_weights = pd.read_csv(root / "provider_weights.csv")
            top = new_weights.loc[new_weights["weight"].idxmax(), "candidate_id"]
            new_idx = int(str(top).split("_LHS_")[-1])
            o = old[list(VARS)].to_numpy(float)
            n = new[list(VARS)].to_numpy(float)
            item = {
                "world": world, "provider": provider,
                "same_LHS_z": coords_equal,
                "pilot_top1_index": pilot_idx,
                "new_top1_index": new_idx,
                "top1_index_changed": pilot_idx != new_idx,
                "median_mu_scale": float(np.median(n[:,0] / o[:,0])),
                "median_kappa_scale": float(np.median(n[:,1] / o[:,1])),
                "median_abs_cv_delta": float(np.median(np.abs(n[:,2] - o[:,2]))),
                "pilot_mu_range": f"{o[:,0].min():.4g}..{o[:,0].max():.4g}",
                "new_mu_range": f"{n[:,0].min():.4g}..{n[:,0].max():.4g}",
                "pilot_kappa_range": f"{o[:,1].min():.4g}..{o[:,1].max():.4g}",
                "new_kappa_range": f"{n[:,1].min():.4g}..{n[:,1].max():.4g}",
            }
            output.append(item)
    result = pd.DataFrame(output)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print("LHS DESIGN DOMAIN TRANSFER, 9 provider-world comparisons")
        print(result.to_string(index=False))
    print("\nAll normalized coordinates verified against the original 48-point LHS.")
    print("Range columns describe the 48 observed samples, not exact search bounds.")
    print("A changed Top1 index can reflect public I1 differences, finite rescore noise,")
    print("candidate-domain mapping, or their interaction; no cause is isolated here.")
    print("No simulation, hidden parameter, Step0 or WB read. Nothing written.")
    print("B1_DOMAIN_TRANSFER_AUDIT_PASS")


if __name__ == "__main__":
    main()
