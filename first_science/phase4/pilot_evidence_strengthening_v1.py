#!/usr/bin/env python3
"""Read-only pilot evidence-strengthening analysis.

No simulation is executed. This script reads already-frozen Phase-4 outputs and
recreates hidden-theta, signed-bias, and WB-reference-noise-adjusted tables.
"""
from pathlib import Path
import json
import math
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE
RESULT = ROOT / "results" / "pilot_evidence_strengthening_v1"
RESULT.mkdir(parents=True, exist_ok=True)

step0 = json.loads((ROOT / "config_phase4_sigma_regime_battery_step0_v2.json").read_text())
wb = step0["hidden_whitebox_model"]
params = pd.read_csv(ROOT / "results/m1_vs_top1_public_i1_audit_v1/m1_vs_top1_parameters.csv")
truth_mu = {
    p: instr * wb["execution_fraction_x"] / wb["effective_IPT"]
    for p, instr in wb["provider_instruction_means"].items()
}

theta = []
for _, r in params.iterrows():
    p = r["provider"]
    for arm, pre in [("M1", "m1_"), ("TOP1", "top1_")]:
        mu = float(r[pre + "mean_service_time"])
        kappa = float(r[pre + "cost_rate"])
        cv = float(r[pre + "service_cv"])
        tmu, tk, tcv = truth_mu[p], wb["cost_rate"], wb["instruction_cv"]
        theta.append({
            "provider": p, "arm": arm,
            "truth_mu_seconds": tmu, "estimate_mu_seconds": mu,
            "mu_ratio_est_over_truth": mu/tmu,
            "mu_abs_log10_fold_error": abs(math.log10(mu/tmu)),
            "truth_kappa": tk, "estimate_kappa": kappa,
            "kappa_ratio_est_over_truth": kappa/tk,
            "kappa_abs_log10_fold_error": abs(math.log10(kappa/tk)),
            "truth_cv": tcv, "estimate_cv": cv,
            "cv_ratio_est_over_truth": cv/tcv,
            "cv_abs_error": abs(cv-tcv),
        })
pd.DataFrame(theta).to_csv(RESULT / "hidden_theta_comparison.csv", index=False)

final = pd.read_csv(ROOT / "results/m3_v4_final_evaluation_v1/m3_v4_final_comparison.csv")
final = final[(final.horizon >= 60) & (final.horizon <= 240)].copy()
support = pd.read_csv(ROOT / "results/m3_top3_support_validation_v1/m3_top3_support_predictions.csv")
support = support[(support.horizon >= 60) & (support.horizon <= 240)].copy()
reg_name = {"G0":"Easy","G1":"Mid","G2":"Stress"}

bias = []
for reg in ["G0","G1","G2"]:
    sub = final[final.regime == reg]
    for method, col in [("M0","sigma_m0"),("M1","sigma_m1"),("M2","sigma_m2_mean"),("M3_TOP14","sigma_m3_B1400")]:
        use = sub.copy()
        if method == "M0":
            use = use[use.m0_status == "PREDICTED"]
        use = use[use[col].notna()]
        if len(use) == 0:
            bias.append({"regime":reg_name[reg],"method":method,"n_points":0,"n_queries":0,"bias":None,"mae":None,"interpretation":"NOT_APPLICABLE"})
        else:
            err = use[col] - use.sigma_whitebox
            bias.append({"regime":reg_name[reg],"method":method,"n_points":len(use),"n_queries":use[["rho_global","regime"]].drop_duplicates().shape[0],"bias":err.mean(),"mae":err.abs().mean(),"interpretation":"optimistic" if err.mean()>0 else "conservative" if err.mean()<0 else "unbiased"})
    s = support[support.regime == reg]
    for method, col in [("M3_TOP1","sigma_top1_1400"),("M3_TOP3","sigma_top3_1400")]:
        err = s[col] - s.sigma_whitebox
        bias.append({"regime":reg_name[reg],"method":method,"n_points":len(s),"n_queries":5,"bias":err.mean(),"mae":err.abs().mean(),"interpretation":"optimistic" if err.mean()>0 else "conservative" if err.mean()<0 else "unbiased"})
pd.DataFrame(bias).to_csv(RESULT / "signed_bias_by_regime.csv", index=False)

def noise_row(df, col, scope):
    use = df if scope == "ALL" else df[df.regime == scope]
    err = use[col] - use.sigma_whitebox
    mse = (err**2).mean()
    vwb = (use.sigma_whitebox * (1-use.sigma_whitebox) / (200-1)).mean()
    adj = max(0.0, mse-vwb)
    return {
        "scope": "ALL" if scope=="ALL" else reg_name[scope],
        "n_points": len(use),
        "mae": err.abs().mean(),
        "bias": err.mean(),
        "raw_mse": mse,
        "raw_rmse": math.sqrt(mse),
        "mean_estimated_WB_variance": vwb,
        "WB_noise_adjusted_mse": adj,
        "WB_noise_adjusted_rmse": math.sqrt(adj),
        "estimated_WB_noise_fraction_of_raw_mse": vwb/mse if mse>0 else None,
    }

noise = []
for method, col, df in [
    ("M1","sigma_m1",final),
    ("M2","sigma_m2_mean",final),
    ("M3_TOP1","sigma_top1_1400",support),
    ("M3_TOP3","sigma_top3_1400",support),
    ("M3_TOP14","sigma_m3_B1400",final),
]:
    for scope in ["ALL","G0","G1","G2"]:
        x = noise_row(df,col,scope)
        x["method"] = method
        noise.append(x)
pd.DataFrame(noise).to_csv(RESULT / "wb_noise_adjusted_discrepancy.csv", index=False)

print("PILOT_EVIDENCE_STRENGTHENING_V1_COMPLETE")
