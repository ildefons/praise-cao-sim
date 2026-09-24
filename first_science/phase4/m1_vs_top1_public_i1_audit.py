"""Read-only audit: frozen M1-v2 versus M3-v3 Top1 on the same public-I1 score.

No simulation is performed.  The script discovers the frozen M1 independent
replay whose sibling m1_v2_best.json exactly matches the frozen M1 parameter
manifest, then compares that replay with the maximum-weight M3-v3 candidate for
the same provider using the exact Jeffreys-smoothed Bernoulli-KL energy used by
M3.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent
PHASE3 = FIRST / "phase3"
RESULTS = HERE / "results" / "m1_vs_top1_public_i1_audit_v1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
N_PUBLIC = 100
N_REPLAY = 100
TOL = 1e-12


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def smooth(p, n: int):
    x = np.asarray(p, dtype=float)
    if np.any(x < -1e-10) or np.any(x > 1 + 1e-10):
        raise ValueError("probability outside [0,1]")
    x = np.clip(x, 0.0, 1.0)
    return (x * float(n) + 0.5) / (float(n) + 1.0)


def bernoulli_kl(p, r):
    p = np.asarray(p, dtype=float)
    r = np.asarray(r, dtype=float)
    return p * np.log(p / r) + (1.0 - p) * np.log((1.0 - p) / (1.0 - r))


def score(comparison: pd.DataFrame, arm: str, provider: str):
    required = {
        "provider_id", "region_id", "horizon", "region_rho", "rho",
        "sigma_i1", "sigma_m1_local",
    }
    missing = required.difference(comparison.columns)
    if missing:
        raise RuntimeError(f"{arm} {provider}: missing columns {sorted(missing)}")
    g = comparison.copy()
    if not (g["horizon"].astype(float) > 0).all():
        g = g[g["horizon"].astype(float) > 0].copy()
    if len(g) != 1200:
        raise RuntimeError(f"{arm} {provider}: expected 1200 H>0 points, found {len(g)}")

    public = g["sigma_i1"].to_numpy(float)
    pred = g["sigma_m1_local"].to_numpy(float)
    pj = smooth(public, N_PUBLIC)
    rj = smooth(pred, N_REPLAY)
    kl = bernoulli_kl(pj, rj)
    err = pred - public

    summary = {
        "provider": provider,
        "arm": arm,
        "n_points": int(len(g)),
        "mean_bernoulli_kl": float(np.mean(kl)),
        "mse": float(np.mean(err ** 2)),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "bias": float(np.mean(err)),
        "max_abs_error": float(np.max(np.abs(err))),
    }

    point = g[[
        "provider_id", "region_id", "horizon", "region_rho", "rho",
        "sigma_i1", "sigma_m1_local",
    ]].copy()
    point.insert(0, "arm", arm)
    point.insert(0, "provider", provider)
    point["p_i1_jeffreys"] = pj
    point["p_reconstruction_jeffreys"] = rj
    point["bernoulli_kl"] = kl
    point["error"] = err
    return summary, point


def discover_m1(provider: str, frozen_params: dict):
    candidates = sorted(
        PHASE3.glob("results/**/m1_v2_independent_replay_comparison.csv")
    )
    matches = []
    for comp in candidates:
        best = comp.parent / "m1_v2_best.json"
        if not best.exists():
            continue
        payload = read_json(best)
        if str(payload.get("provider_id")) != provider:
            continue
        params = payload.get("parameters", {})
        ok = all(
            np.isclose(
                float(params.get(k, np.nan)),
                float(frozen_params[k]),
                rtol=0.0,
                atol=TOL,
            )
            for k in ("mean_service_time", "cost_rate", "service_cv")
        )
        if ok and not bool(payload.get("smoke_mode", False)):
            matches.append((comp, best, payload))
    if len(matches) != 1:
        paths = [str(x[0]) for x in matches]
        raise RuntimeError(
            f"{provider}: expected exactly one frozen M1 replay match; "
            f"found {len(matches)}: {paths}"
        )
    return matches[0]


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)

    m1_freeze_path = PHASE3 / "phase3_i1_m1_v2_freeze_manifest_v1.json"
    m1_freeze = read_json(m1_freeze_path)
    if m1_freeze.get("status") != "FROZEN_PHASE3_I1_M1_V2_PILOT":
        raise RuntimeError("unexpected M1 freeze manifest status")

    weights_path = HERE / "results/m3_lambda_cv_v3/m3_v3_provider_weights.csv"
    weights = pd.read_csv(weights_path)
    if "weight_v3" not in weights.columns:
        raise RuntimeError("M3-v3 weights file lacks weight_v3")

    local_root = HERE / "results/m3_local_weighting_v1/local_surfaces"
    fit_rows = []
    param_rows = []
    point_rows = []
    input_hashes = {
        "m1_freeze_manifest": {"path": str(m1_freeze_path), "sha256": sha256(m1_freeze_path)},
        "m3_v3_provider_weights": {"path": str(weights_path), "sha256": sha256(weights_path)},
    }

    for provider in PROVIDERS:
        frozen = dict(m1_freeze["provider_surrogates"][provider])
        frozen_params = {
            "mean_service_time": float(frozen["mean_service_time"]),
            "cost_rate": float(frozen["cost_rate"]),
            "service_cv": float(frozen["service_cv"]),
        }
        m1_comp_path, m1_best_path, _ = discover_m1(provider, frozen_params)
        m1_comp = pd.read_csv(m1_comp_path)

        wp = weights[weights["provider"].astype(str) == provider].copy()
        if len(wp) != 48:
            raise RuntimeError(f"{provider}: expected 48 M3 support candidates, found {len(wp)}")
        top = wp.sort_values(
            ["weight_v3", "candidate_id"], ascending=[False, True], kind="mergesort"
        ).iloc[0]
        top_id = str(top["candidate_id"])
        top_comp_path = local_root / f"{top_id}_comparison.csv"
        top_comp = pd.read_csv(top_comp_path)

        m1_summary, m1_points = score(m1_comp, "M1_INDEPENDENT_REPLAY", provider)
        top_summary, top_points = score(top_comp, "TOP1_M3_LOCAL_REPLAY", provider)
        fit_rows.extend([m1_summary, top_summary])
        point_rows.extend([m1_points, top_points])

        p = {
            "provider": provider,
            "m1_mean_service_time": frozen_params["mean_service_time"],
            "m1_cost_rate": frozen_params["cost_rate"],
            "m1_service_cv": frozen_params["service_cv"],
            "top1_candidate_id": top_id,
            "top1_weight_v3": float(top["weight_v3"]),
            "top1_mean_service_time": float(top["mean_service_time"]),
            "top1_cost_rate": float(top["cost_rate"]),
            "top1_service_cv": float(top["service_cv"]),
        }
        p["top1_over_m1_mu_ratio"] = p["top1_mean_service_time"] / p["m1_mean_service_time"]
        p["top1_over_m1_kappa_ratio"] = p["top1_cost_rate"] / p["m1_cost_rate"]
        p["top1_over_m1_cv_ratio"] = p["top1_service_cv"] / p["m1_service_cv"]
        param_rows.append(p)

        input_hashes[f"{provider}_m1_best"] = {
            "path": str(m1_best_path), "sha256": sha256(m1_best_path)
        }
        input_hashes[f"{provider}_m1_replay"] = {
            "path": str(m1_comp_path), "sha256": sha256(m1_comp_path)
        }
        input_hashes[f"{provider}_top1_surface"] = {
            "path": str(top_comp_path), "sha256": sha256(top_comp_path)
        }

    fit = pd.DataFrame(fit_rows)
    params = pd.DataFrame(param_rows)
    pointwise = pd.concat(point_rows, ignore_index=True)

    # Add equally provider-weighted aggregate rows. Each provider has 1200 points.
    aggregates = []
    for arm, g in fit.groupby("arm", sort=False):
        aggregates.append({
            "provider": "PROVIDER_MEAN",
            "arm": arm,
            "n_points": int(g["n_points"].sum()),
            "mean_bernoulli_kl": float(g["mean_bernoulli_kl"].mean()),
            "mse": float(g["mse"].mean()),
            "rmse": float(np.sqrt(g["mse"].mean())),
            "mae": float(g["mae"].mean()),
            "bias": float(g["bias"].mean()),
            "max_abs_error": float(g["max_abs_error"].max()),
        })
    fit = pd.concat([fit, pd.DataFrame(aggregates)], ignore_index=True)

    fit_path = RESULTS / "m1_vs_top1_public_i1_fit.csv"
    params_path = RESULTS / "m1_vs_top1_parameters.csv"
    point_path = RESULTS / "m1_vs_top1_pointwise.csv"
    fit.to_csv(fit_path, index=False)
    params.to_csv(params_path, index=False)
    pointwise.to_csv(point_path, index=False)

    pivot = fit[fit["provider"].isin(PROVIDERS)].pivot(
        index="provider", columns="arm", values=["mean_bernoulli_kl", "mse", "mae"]
    )
    # Descriptive ratios only, no predeclared winner threshold.
    ratios = []
    for provider in PROVIDERS:
        a = fit[(fit.provider == provider) & (fit.arm == "M1_INDEPENDENT_REPLAY")].iloc[0]
        b = fit[(fit.provider == provider) & (fit.arm == "TOP1_M3_LOCAL_REPLAY")].iloc[0]
        ratios.append({
            "provider": provider,
            "m1_over_top1_energy_ratio": float(a.mean_bernoulli_kl / b.mean_bernoulli_kl)
                if b.mean_bernoulli_kl > 0 else np.inf,
            "m1_over_top1_mse_ratio": float(a.mse / b.mse) if b.mse > 0 else np.inf,
        })
    ratios_df = pd.DataFrame(ratios)

    manifest = {
        "status": "M1_VS_TOP1_PUBLIC_I1_READ_ONLY_AUDIT_COMPLETE_V1",
        "classification": "posthoc_read_only_mechanism_audit",
        "provider_simulation": False,
        "graph_simulation": False,
        "graph_whitebox_read": False,
        "new_candidate_generation": False,
        "public_i1_n": N_PUBLIC,
        "reconstruction_replay_n": N_REPLAY,
        "m3_score": "Jeffreys-smoothed Bernoulli KL, public I1 to reconstruction",
        "top1_rule": "maximum frozen M3-v3 provider weight independently for each provider",
        "inputs": input_hashes,
        "outputs": {
            "fit": {"path": str(fit_path), "sha256": sha256(fit_path)},
            "parameters": {"path": str(params_path), "sha256": sha256(params_path)},
            "pointwise": {"path": str(point_path), "sha256": sha256(point_path)},
        },
        "stop_rule": "Interpret as-is; do not retune M1, Top1, M3, scoring, or support from this audit.",
    }
    manifest_path = RESULTS / "m1_vs_top1_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("M1_VS_TOP1_PUBLIC_I1_FIT")
    print(fit.to_string(index=False))
    print("\nM1_VS_TOP1_PARAMETERS")
    print(params.to_string(index=False))
    print("\nM1_VS_TOP1_RATIOS")
    print(ratios_df.to_string(index=False))
    print("\nM1_VS_TOP1_PUBLIC_I1_AUDIT_COMPLETE")
    print(f"output={RESULTS}")


if __name__ == "__main__":
    main()
