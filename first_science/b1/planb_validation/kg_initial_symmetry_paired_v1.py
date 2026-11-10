#!/usr/bin/env python3
"""Initial-state KG symmetries and paired two-step numerical audit.

Requires NumPy and SciPy. Historical B1 data are read-only. Computes
model-predictive acquisition values, not retrospective terminal regret.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import quad

import b1_budget_comparison_v1 as frozen
import b1_kg_one_step_v1 as kg

TOL = 1e-12
CUTS = (-10., -6., -4., -2., 0., 2., 4., 6., 10.)


def normal_pdf(z):
    return math.exp(-0.5*z*z)/math.sqrt(2.*math.pi)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def quad_piecewise(func, atol):
    value, err = 0., 0.
    for a,b in zip(CUTS[:-1], CUTS[1:]):
        v,e = quad(func, a, b, epsabs=atol / (len(CUTS)-1),
                   epsrel=1e-9, limit=250)
        value += v
        err += e
    return float(value), float(err)


def after_first(means, covs, available, first, z):
    a,c,_ = first
    x = frozen.XX[c]
    s = covs[a]
    sx = s @ x
    var = frozen.NOISE**2 + float(x @ sx)
    if var <= 0:
        raise AssertionError("Nonpositive first predictive variance")
    updated_means = means.copy()
    updated_means[a] += float(frozen.V @ sx)/math.sqrt(var)*z
    updated_covs = covs.copy()
    updated_covs[a] = s - np.outer(sx,sx)/var
    updated_covs[a] = .5*(updated_covs[a]+updated_covs[a].T)
    remaining = [v for v in available if v[:2] != first[:2]]
    return float(np.max(kg.scores_from_posterior(
        updated_means, updated_covs, remaining)))


def inspect_start(Y, start, atol):
    seen = [(a,start,float(Y[a,start])) for a in range(7)]
    means,_,covs = frozen.posterior(seen,7)
    # Verify initial method covariances are the same: crucial hypothesis.
    if not np.allclose(covs, covs[0], atol=1e-12, rtol=1e-12):
        raise AssertionError("Initial covariance symmetry fails")
    avail=[(a,c,0) for a in range(7) for c in range(12) if c!=start]
    scores=kg.scores_from_posterior(means,covs,avail)
    peak=float(np.max(scores))
    tied=[(e,float(g)) for e,g in zip(avail,scores) if g >= peak-TOL]
    leaders=np.argsort(means, kind="stable")[:2]
    other_world_graph=[c for c,(w,g) in enumerate(frozen.CELLS)
          if w!=frozen.CELLS[start][0] and g!=frozen.CELLS[start][1]]
    expected={(int(a),c) for a in leaders for c in other_world_graph}
    found={tuple(e[:2]) for e,_ in tied}
    if expected != found or len(tied)!=12:
        raise AssertionError(
            f"Initial tie structure differed at {start}: found={found}, expected={expected}")
    # Prove values by a numerical check of the four possible
    # relations to the initial condition, using common covariance.
    group_sd={}
    for label,cs in [
       ("same_world_other_graph",[c for c,(w,g) in enumerate(frozen.CELLS)
          if w==frozen.CELLS[start][0] and g!=frozen.CELLS[start][1]]),
       ("other_world_same_graph",[c for c,(w,g) in enumerate(frozen.CELLS)
          if w!=frozen.CELLS[start][0] and g==frozen.CELLS[start][1]]),
       ("other_world_other_graph",other_world_graph)]:
        numbers=[]
        for c in cs:
            x=frozen.XX[c];s=covs[0]
            numbers.append(float(frozen.V@s@x)/math.sqrt(
                frozen.NOISE**2+float(x@s@x)))
        if max(numbers)-min(numbers)>1e-12:
            raise AssertionError(f"Symmetry within group {label} fails")
        group_sd[label]=numbers[0]
    if group_sd["other_world_other_graph"] <= max(
       group_sd["other_world_same_graph"],
       group_sd["same_world_other_graph"]):
        raise AssertionError("Distinct condition group not maximally informative")

    candidate=[(int(a),other_world_graph[0],0) for a in leaders]
    one={e[0]:float(scores[avail.index(e)]) for e in candidate}
    a,b=candidate

    def i_a(z):
        return normal_pdf(z)*after_first(means,covs,avail,a,z)
    def i_b(z):
        return normal_pdf(z)*after_first(means,covs,avail,b,z)
    def i_delta(z):
        # Paired evaluation at the same standardized observation z cancels
        # much common quadrature error, especially at decision boundaries.
        return normal_pdf(z)*(after_first(means,covs,avail,a,z)-
                              after_first(means,covs,avail,b,z))

    fa,ea=quad_piecewise(i_a,atol)
    fb,eb=quad_piecewise(i_b,atol)
    delta,ed=quad_piecewise(i_delta,atol/2.)
    q_a=one[a[0]]+fa
    q_b=one[b[0]]+fb
    delta_total=one[a[0]]-one[b[0]]+delta
    consistency=abs((q_a-q_b)-delta_total)
    if consistency>max(1e-7, 50*(ea+eb+ed)):
        raise AssertionError(f"Separate/paired integration inconsistency {consistency}")
    return dict(
       start=start,starting_world=frozen.CELLS[start][0],
       starting_graph=frozen.CELLS[start][1],
       first_method_a=frozen.METHODS[a[0]],
       first_method_b=frozen.METHODS[b[0]],
       n_one_step_tied=len(tied),one_step_score_a=one[a[0]],
       one_step_score_b=one[b[0]],
       sd_same_world_other_graph=group_sd["same_world_other_graph"],
       sd_other_world_same_graph=group_sd["other_world_same_graph"],
       sd_other_world_other_graph=group_sd["other_world_other_graph"],
       two_step_score_a=q_a,two_step_score_b=q_b,
       two_step_a_minus_b=delta_total,
       paired_integration_error_est=ed,
       separate_integration_error_est=ea+eb,
       separate_paired_consistency=consistency,
       selected_method_by_two_step=(frozen.METHODS[a[0]] if delta_total>0
                                    else frozen.METHODS[b[0]]),
       ratio_abs_diff_to_error=abs(delta_total)/max(ed,1e-15))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--abs-tol",type=float,default=1e-9)
    args=p.parse_args()
    if args.abs_tol<=0 or not math.isfinite(args.abs_tol):
        p.error("Absolute tolerance must be positive finite")
    output=args.out.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")
    matrix=args.matrix.expanduser().resolve()
    Y=kg.load_frozen_matrix(matrix)
    rows=[]
    for start in range(len(frozen.CELLS)):
        row=inspect_start(Y,start,args.abs_tol)
        rows.append(row)
        print("STATE",start+1,"TWO_STEP_A_MINUS_B",
              f"{row['two_step_a_minus_b']:.10g}",
              "EST_INTEGRATION_ERROR",f"{row['paired_integration_error_est']:.3g}",
              "RATIO",f"{row['ratio_abs_diff_to_error']:.3g}",flush=True)
    output.mkdir(parents=True)
    write_csv(output/"two_method_comparison.csv",rows)
    manifest=dict(
        status="B1_KG_INITIAL_SYMMETRY_AND_PAIRED_KG2_DEVELOPMENT",
        matrix_sha256=frozen.digest(matrix),
        n_states=len(rows),
        pair_choice="two methods with top posterior means; canonical other-world other-graph condition",
        integration_method="scipy.integrate.quad on [-10,10] split at 8 intervals",
        quadrature_error_note="QUAD numerical error estimate is heuristic, not rigorous certificate; tail beyond +-10 omitted",
        abs_tolerance=args.abs_tol,
        outputs_sha256={f.name:frozen.digest(f) for f in output.glob("*.csv")},
    )
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("KG_INITIAL_SYMMETRY_PAIRED_KG2_PASS",output)


if __name__=="__main__":
    main()
