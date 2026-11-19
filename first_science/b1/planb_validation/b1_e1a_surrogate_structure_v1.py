#!/usr/bin/env python3
"""PRAISE E1a: exact-mask, read-only retrospective surrogate ablation.

This script never imports or runs a simulator or acquisition policy. It uses
two separately frozen 7x12 MAE matrices and compares predictions from three
families of per-method Gaussian priors under identical observed subsets.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

import b1_budget_comparison_v1 as frozen


PROTOCOL = "B1_E1A_EXHAUSTIVE_MASK_SURROGATES_V1"
INPUT_SHA256 = {
    "historical": "0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d",
    "fresh_reference": "5c81f50af9fad98596f0eac17ec3e9afc7848661acf476740af48663119606a3",
}
METHODS = tuple(frozen.METHODS)
CELLS = tuple(frozen.CELLS)
N_METHODS = 7
N_CELLS = 12
OBSERVATION_NOISE = 0.055
PRIOR_MEAN = 0.17
MODEL_ORDER = ("A_independent", "B_additive", "C_interaction_25", "C_interaction_50")
CONTRASTS = (
    ("B_minus_A", "B_additive", "A_independent"),
    ("C25_minus_B", "C_interaction_25", "B_additive"),
    ("C50_minus_B", "C_interaction_50", "B_additive"),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_legacy_prior() -> None:
    """Fail explicitly if the frozen source model changes underneath E1a."""
    if METHODS != (
        "M1", "M2", "M3_FULL343", "ORIGINAL_TOP14_B1400",
        "ORIGINAL_TOP1_B1400", "FIXED_CV_TOP14", "FIXED_CV_TOP1",
    ):
        raise ValueError("Frozen candidate method list changed")
    if CELLS != tuple((w, g) for w in ("P1", "P3", "P4")
                      for g in ("G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR")):
        raise ValueError("Frozen condition order changed")
    if not np.allclose(frozen.PRIOR_MEAN, [PRIOR_MEAN] + [0.0] * 7, atol=0, rtol=0):
        raise ValueError("Frozen prior mean changed")
    if not np.allclose(frozen.PRIOR_VAR,
                       [0.12 ** 2] + [0.07 ** 2] * 3 + [0.045 ** 2] * 4,
                       atol=0, rtol=0):
        raise ValueError("Frozen prior covariance changed")
    if frozen.NOISE != OBSERVATION_NOISE or frozen.XX.shape != (N_CELLS, 8):
        raise ValueError("Frozen working noise or design changed")


def model_kernels() -> dict[str, np.ndarray]:
    """All models have the SAME marginal prior means and variances.

    B is exactly the latent covariance induced by the original coefficient
    prior. A is independent over cells. C mixes B with an independent
    cell-specific interaction at a predeclared variance share eta.
    """
    verify_legacy_prior()
    b = (frozen.XX * frozen.PRIOR_VAR) @ frozen.XX.T
    a = np.diag(np.diag(b))
    kernels = {
        "A_independent": a,
        "B_additive": b,
        "C_interaction_25": 0.75 * b + 0.25 * a,
        "C_interaction_50": 0.50 * b + 0.50 * a,
    }
    for label, kernel in kernels.items():
        if kernel.shape != (N_CELLS, N_CELLS):
            raise AssertionError(f"Wrong covariance dimension: {label}")
        if not np.allclose(np.diag(kernel), np.diag(b), atol=1e-14, rtol=0):
            raise AssertionError(f"Unequal marginal scales: {label}")
        if np.linalg.eigvalsh(kernel).min() < -1e-12:
            raise AssertionError(f"Non-PSD prior: {label}")
    return kernels


def load_frozen_matrix(path: Path, archive: str) -> tuple[np.ndarray, str]:
    """Validate bytes AND exact 84-cell catalogue before using any outcomes."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing {archive} matrix: {path}")
    actual_hash = sha256(path)
    if actual_hash != INPUT_SHA256[archive]:
        raise ValueError(f"{archive} matrix SHA-256 mismatch: {actual_hash}")
    data = np.full((N_METHODS, N_CELLS), np.nan, dtype=float)
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"method", "world", "graph", "mae"}.issubset(reader.fieldnames or []):
            raise ValueError(f"{archive}: wrong CSV columns")
        nrows = 0
        for row in reader:
            nrows += 1
            name = row["method"]
            cell = (row["world"], row["graph"])
            if name not in METHODS or cell not in CELLS:
                raise ValueError(f"{archive}: unknown method/condition {name}/{cell}")
            i, j = METHODS.index(name), CELLS.index(cell)
            if math.isfinite(data[i, j]):
                raise ValueError(f"{archive}: duplicate {name}/{cell}")
            value = float(row["mae"])
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{archive}: invalid MAE {value}")
            data[i, j] = value
    if nrows != N_METHODS * N_CELLS or not np.isfinite(data).all():
        raise ValueError(f"{archive}: expected exactly 84 complete observations")
    return data, actual_hash


def posterior_predictions(
    matrix: np.ndarray, observed: tuple[int, ...], kernel: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Predict all twelve latent cell losses using ONLY observed columns.

    Returns a 7x12 posterior mean and twelve marginal variances for a new
    cell-level MAE. The nonzero residual variance is the frozen B1 *working*
    model discrepancy, not repeated observations of one catalogue entry.
    """
    obs = np.asarray(observed, dtype=int)
    if (obs.ndim != 1 or len(obs) < 1 or len(obs) >= N_CELLS or
            len(set(obs.tolist())) != len(obs) or
            np.any(obs < 0) or np.any(obs >= N_CELLS)):
        raise ValueError("Observed subset must contain 1..11 distinct valid cells")
    if matrix.shape != (N_METHODS, N_CELLS):
        raise ValueError("Expected a 7x12 matrix")
    covariance_observed = kernel[np.ix_(obs, obs)] + OBSERVATION_NOISE ** 2 * np.eye(len(obs))
    # n_observed x 12; the observed columns alone determine posterior means.
    weights = np.linalg.solve(covariance_observed, kernel[np.ix_(obs, range(N_CELLS))])
    mean = PRIOR_MEAN + (matrix[:, obs] - PRIOR_MEAN) @ weights
    latent_variance = np.diag(kernel) - np.einsum(
        "ik,ki->i", kernel[:, obs], weights
    )
    predictive_variance = latent_variance + OBSERVATION_NOISE ** 2
    if (not np.isfinite(mean).all() or not np.isfinite(predictive_variance).all() or
            np.any(predictive_variance <= 0)):
        raise AssertionError("Invalid Gaussian posterior")
    return mean, predictive_variance


def evaluate_mask(
    matrix: np.ndarray, observed: tuple[int, ...],
    kernel: np.ndarray
) -> tuple[dict[str, float | int | str], np.ndarray, np.ndarray]:
    pred, variance = posterior_predictions(matrix, observed, kernel)
    heldout = np.asarray([c for c in range(N_CELLS) if c not in observed], dtype=int)
    residual = pred[:, heldout] - matrix[:, heldout]
    sq = residual ** 2
    nll = 0.5 * (np.log(2.0 * np.pi * variance[heldout])[None, :] +
                 sq / variance[heldout][None, :])
    truth = matrix.mean(axis=1)
    chosen = int(np.argmin(pred.mean(axis=1)))
    best = int(np.argmin(truth))
    regret = float(truth[chosen] - truth[best])
    if regret < -1e-12:
        raise AssertionError("Negative simple regret")
    metrics: dict[str, float | int | str] = {
        "observed_indices": "|".join(map(str, observed)),
        "observed_mask_bits": sum(1 << int(c) for c in observed),
        "n_observed_per_method": len(observed),
        "n_heldout_per_method": len(heldout),
        "heldout_mae": float(np.abs(residual).mean()),
        "heldout_rmse": float(np.sqrt(sq.mean())),
        "heldout_gaussian_nll": float(nll.mean()),
        "domain_mean_mae": float(np.abs(pred.mean(axis=1) - truth).mean()),
        "recommended_method": METHODS[chosen],
        "reference_best_method": METHODS[best],
        "p_correct": int(chosen == best),
        "simple_regret": max(0.0, regret),
    }
    return metrics, heldout, np.abs(residual)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing empty output {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows: list[dict]) -> dict[str, float | int]:
    def vector(key: str) -> np.ndarray:
        return np.asarray([float(row[key]) for row in rows])
    regret = vector("simple_regret")
    mae = vector("heldout_mae")
    return {
        "n_masks": len(rows),
        "mean_heldout_mae": float(mae.mean()),
        "median_heldout_mae": float(np.median(mae)),
        "mean_heldout_rmse": float(vector("heldout_rmse").mean()),
        "mean_heldout_gaussian_nll": float(vector("heldout_gaussian_nll").mean()),
        "mean_domain_mean_mae": float(vector("domain_mean_mae").mean()),
        "mean_simple_regret": float(regret.mean()),
        "median_simple_regret": float(np.median(regret)),
        "p90_simple_regret": float(np.quantile(regret, 0.9)),
        "p_correct": float(vector("p_correct").mean()),
    }


def run(archives: dict[str, np.ndarray], output_root: Path,
        input_paths: dict[str, Path], input_hashes: dict[str, str]) -> None:
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output_root}")
    kernels = model_kernels()
    per_mask: list[dict] = []
    summaries: list[dict] = []
    pairs: list[dict] = []
    cells: list[dict] = []
    for archive, matrix in archives.items():
        truth = matrix.mean(axis=1)
        print(f"E1A_ARCHIVE {archive} best={METHODS[int(np.argmin(truth))]}", flush=True)
        for n in range(1, N_CELLS):
            masks = list(itertools.combinations(range(N_CELLS), n))
            results = {name: [] for name in MODEL_ORDER}
            cell_count = {name: np.zeros((N_METHODS, N_CELLS), dtype=int)
                          for name in MODEL_ORDER}
            cell_abs = {name: np.zeros((N_METHODS, N_CELLS), dtype=float)
                        for name in MODEL_ORDER}
            for mask in masks:
                for model in MODEL_ORDER:
                    metrics, heldout, residual_abs = evaluate_mask(matrix, mask, kernels[model])
                    results[model].append(metrics)
                    per_mask.append({"archive": archive, "model": model, **metrics})
                    cell_count[model][:, heldout] += 1
                    cell_abs[model][:, heldout] += residual_abs
            for model in MODEL_ORDER:
                stats = aggregate(results[model])
                summaries.append({"archive": archive, "model": model,
                                  "n_observed_per_method": n, **stats})
                for a, method in enumerate(METHODS):
                    for c, (world, graph) in enumerate(CELLS):
                        count = int(cell_count[model][a, c])
                        if count < 1:
                            raise AssertionError("A held-out cell was never evaluated")
                        cells.append({"archive": archive, "model": model,
                                      "n_observed_per_method": n,
                                      "method": method, "world": world, "graph": graph,
                                      "n_masks_holding_out_cell": count,
                                      "mean_abs_error": float(cell_abs[model][a, c] / count)})
            for label, left, right in CONTRASTS:
                x, y = results[left], results[right]
                for metric in ("heldout_mae", "domain_mean_mae", "simple_regret"):
                    diff = np.asarray([float(u[metric]) - float(v[metric])
                                       for u, v in zip(x, y, strict=True)])
                    pairs.append({"archive": archive, "comparison": label,
                                  "n_observed_per_method": n, "metric": metric,
                                  "n_paired_masks": len(diff),
                                  "mean_first_minus_second": float(diff.mean()),
                                  "median_first_minus_second": float(np.median(diff)),
                                  "fraction_first_better": float(np.mean(diff < -1e-12)),
                                  "fraction_tied": float(np.mean(np.abs(diff) <= 1e-12))})
            print(f"E1A_MASK_COUNT {archive} observed={n} masks={len(masks)}", flush=True)

    output_root.mkdir(parents=True, exist_ok=False)
    outputs = {
        "per_mask_metrics.csv": per_mask,
        "summary_by_observed_count.csv": summaries,
        "paired_structural_contrasts.csv": pairs,
        "heldout_cell_diagnostics.csv": cells,
        "condition_index.csv": [dict(index=c, world=w, graph=g)
                                for c, (w, g) in enumerate(CELLS)],
    }
    output_hashes = {}
    for filename, rows in outputs.items():
        path = output_root / filename
        write_csv(path, rows)
        output_hashes[filename] = sha256(path)
    manifest = {
        "status": "E1A_RETROSPECTIVE_MASK_ABLATION_PASS",
        "protocol": PROTOCOL,
        "scientific_scope": "EXPLORATORY; two fixed matrices, same provider worlds/graphs; no independent-world inference",
        "input_paths": {k: str(v.resolve()) for k, v in input_paths.items()},
        "input_sha256": input_hashes,
        "script_sha256": sha256(Path(__file__)),
        "frozen_additive_source_sha256": sha256(Path(frozen.__file__)),
        "methods": METHODS,
        "conditions": CELLS,
        "models": MODEL_ORDER,
        "B_prior_mean": PRIOR_MEAN,
        "B_prior_coefficient_variances": frozen.PRIOR_VAR.tolist(),
        "working_noise_standard_deviation": OBSERVATION_NOISE,
        "interaction_variance_fraction": {"C_interaction_25": 0.25,
                                          "C_interaction_50": 0.50},
        "subsets_per_archive": 2 ** N_CELLS - 2,
        "mask_rows_per_archive": (2 ** N_CELLS - 2) * len(MODEL_ORDER),
        "full_matrix_used_only_for_scoring": True,
        "observed_value_treatment": "Original B1 latent-Gaussian posterior with working residual variance",
        "uncertainty_interpretation": "Exact enumeration over masks; NOT world-level confidence intervals",
        "output_sha256": output_hashes,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"E1A_EXHAUSTIVE_MASK_PASS {output_root.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-matrix", required=True, type=Path)
    parser.add_argument("--fresh-reference-matrix", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if not args.preflight_only and args.out is None:
        parser.error("--out is required unless --preflight-only is set")
    if args.out is not None and args.out.exists():
        raise FileExistsError(f"Output path already exists: {args.out}")
    verify_legacy_prior()
    paths = {"historical": args.historical_matrix,
             "fresh_reference": args.fresh_reference_matrix}
    archives = {}
    hashes = {}
    for name, path in paths.items():
        archives[name], hashes[name] = load_frozen_matrix(path, name)
        print(f"E1A_INPUT_OK {name} sha256={hashes[name]}")
    kernels = model_kernels()
    print("E1A_MODEL_OK " + ",".join(kernels))
    if args.preflight_only:
        print("E1A_PREFLIGHT_PASS no outputs written")
        return
    run(archives, args.out, paths, hashes)


if __name__ == "__main__":
    main()
