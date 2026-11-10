#!/usr/bin/env python3
"""Read-only scientific audit of one isolated Phase-5 Step-0 confirmation failure.

Outputs query-level calibration/confirmation contrasts and an OPTIONAL
trajectory-cluster bootstrap for the failed frozen query, without modifying
any original evidence, refitting queries, or rerunning simulations.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
PHASE5 = REPO/"first_science"/"phase5"
EXPECTED_CANDIDATE = "B0001_P1_A01"
EXPECTED_GRAPH = "G_PAR"
CELL = "P1__G_PAR"
RHO_TOL = 1e-9
REGIMES = {"Easy":(.95,1.),"Mid":(.75,.90),"Stress":(.40,.75)}
HORIZONS = tuple(range(60,241,5))


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def pick_column(frame,keys):
    for c in keys:
        if c in frame.columns:
            return c
    raise ValueError("No expected column in "+str(frame.columns.tolist())+" candidates "+str(keys))


def audit(pilot,out,n_boot,seed):
    pilot=pilot.expanduser().resolve()
    out=out.expanduser().resolve()
    if out.exists():
        raise FileExistsError("Refusing overwrite "+str(out))
    provenance=read(pilot/"pilot_provenance_PRIVATE.json")
    summary=read(pilot/"pilot_summary.json")
    if provenance["candidate_id"]!=EXPECTED_CANDIDATE or provenance["graph_id"]!=EXPECTED_GRAPH:
        raise ValueError("Wrong candidate/graph")
    if summary["candidate_id"]!=EXPECTED_CANDIDATE or summary["graph_id"]!=EXPECTED_GRAPH:
        raise ValueError("Summary is not the selected pilot")
    root=pilot/"step0"/CELL
    cm=read(root/"step0_calibration_manifest.json")
    fm=read(root/"step0_confirmation_manifest.json")
    if cm["status"]!="FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2":
        raise ValueError("Calibration did not pass")
    if fm["status"]!="GATE_FAILED_STEP0":
        raise ValueError("Confirmation did not fail")
    selected_path=root/"step0_selected_queries.csv"
    confirmed_path=root/"step0_confirmation.csv"
    curves_path=root/"step0_confirmation_curves.csv"
    calib_ledger_path=root/"step0_calibration_whitebox_ledger.csv"
    confirm_ledger_path=root/"step0_confirmation_whitebox_ledger.csv"
    for p in (selected_path,confirmed_path,curves_path,calib_ledger_path,confirm_ledger_path):
        if not p.is_file():
            raise FileNotFoundError(p)
    if cm["output_hashes_sha256"]["step0_selected_queries"]!=sha(selected_path):
        raise ValueError("Selected queries have changed since calibration")
    selected=pd.read_csv(selected_path)
    confirmed=pd.read_csv(confirmed_path)
    curves=pd.read_csv(curves_path)
    if len(selected)!=15 or len(confirmed)!=15:
        raise ValueError("Expected exactly 15 selected and 15 confirmation queries")
    if selected.query_id.duplicated().any() or confirmed.query_id.duplicated().any():
        raise ValueError("Duplicate query ID")
    if set(selected.query_id)!=set(confirmed.query_id):
        raise ValueError("Calibration and confirmation query sets differ")
    a=pick_column(selected,["sigma_mean_H60_H240"])
    b=pick_column(confirmed,["sigma_mean_H60_H240"])
    joined=selected[["query_id","rho","regime","scale",a]].merge(
        confirmed[["query_id",b]],on="query_id",validate="one_to_one",
        suffixes=("_calibration","_confirmation"))
    calibration_col=a+"_calibration"
    confirmation_col=b+"_confirmation"
    if calibration_col not in joined: # only applies if source columns identical
        raise AssertionError("Query means do not have expected suffixes")
    joined["difference_confirmation_minus_calibration"]=joined[confirmation_col]-joined[calibration_col]
    joined["band_lower"]=[REGIMES[v][0] for v in joined.regime]
    joined["band_upper"]=[REGIMES[v][1] for v in joined.regime]
    joined["calibration_lower_margin"]=joined[calibration_col]-joined.band_lower
    joined["confirmation_lower_margin"]=joined[confirmation_col]-joined.band_lower
    joined["calibration_upper_margin"]=joined.band_upper-joined[calibration_col]
    joined["confirmation_upper_margin"]=joined.band_upper-joined[confirmation_col]
    joined["calibration_nearest_margin"]=joined[["calibration_lower_margin","calibration_upper_margin"]].min(axis=1)
    joined["confirmation_nearest_margin"]=joined[["confirmation_lower_margin","confirmation_upper_margin"]].min(axis=1)
    joined["confirmation_pass"]=(joined.confirmation_nearest_margin>=-1e-12)
    joined=joined.sort_values(["rho","regime"]).reset_index(drop=True)
    bad=joined[~joined.confirmation_pass]
    if len(bad)!=1 or not (bad.iloc[0].regime=="Easy" and abs(float(bad.iloc[0].rho)-.99)<RHO_TOL):
        raise AssertionError("Observed confirmation failure differs from input report")
    failed=bad.iloc[0]
    curve=curves[curves.query_id==failed.query_id].copy()
    if len(curve)<37:
        raise ValueError("Expected full confirmation horizon curve")
    horizon_col=pick_column(curve,["horizon","H"])
    value_col=pick_column(curve,["sigma_confirmation"])
    curve[horizon_col]=curve[horizon_col].astype(float)
    diagnostic=curve[curve[horizon_col].isin(HORIZONS)]
    if len(diagnostic)!=37:
        raise ValueError("Expected 37 diagnostic horizons")
    if abs(diagnostic[value_col].mean()-float(failed[confirmation_col]))>2e-6:
        raise ValueError("Saved curve and confirmation summary disagree")
    out.mkdir(parents=True)
    joined.to_csv(out/"fifteen_query_calibration_confirmation.csv",index=False)
    curve.to_csv(out/"failed_query_confirmation_curve.csv",index=False)
    source_files=[selected_path,confirmed_path,curves_path,calib_ledger_path,confirm_ledger_path,
                  root/"step0_calibration_manifest.json",root/"step0_confirmation_manifest.json"]
    result={
        "status":"READ_ONLY_FAILED_STEP0_QUERY_AUDIT",
        "candidate_id":EXPECTED_CANDIDATE,"graph_id":EXPECTED_GRAPH,
        "n_queries":15,"failed_queries":bad.query_id.tolist(),
        "failed_query":{
            "query_id":str(failed.query_id),"rho":float(failed.rho),"regime":str(failed.regime),
            "scale":float(failed.scale),
            "calibration_mean":float(failed[calibration_col]),
            "confirmation_mean":float(failed[confirmation_col]),
            "delta":float(failed["difference_confirmation_minus_calibration"]),
            "calibration_margin":float(failed.calibration_nearest_margin),
            "confirmation_margin":float(failed.confirmation_nearest_margin)
        },
        "all_queries":{
            "negative_differences":int((joined["difference_confirmation_minus_calibration"]<0).sum()),
            "positive_differences":int((joined["difference_confirmation_minus_calibration"]>0).sum()),
            "mean_signed_difference":float(joined["difference_confirmation_minus_calibration"].mean()),
            "median_abs_difference":float(joined["difference_confirmation_minus_calibration"].abs().median()),
            "min_calibration_margin":float(joined.calibration_nearest_margin.min()),
        },
        "horizon_curve":{
            "first_H":float(diagnostic[horizon_col].min()),
            "last_H":float(diagnostic[horizon_col].max()),
            "minimum":float(diagnostic[value_col].min()),
            "maximum":float(diagnostic[value_col].max()),
            "first_value":float(diagnostic.sort_values(horizon_col).iloc[0][value_col]),
            "last_value":float(diagnostic.sort_values(horizon_col).iloc[-1][value_col]),
        },
        "source_sha256":{str(p.relative_to(pilot)):sha(p) for p in source_files},
        "bootstrap":None,
    }

    if n_boot:
        if n_boot < 50 or n_boot > 10000:
            raise ValueError("--bootstrap requires 50..10000 replicates")
        sys.path.insert(0,str(PHASE5))
        from sla_compliance_analysis import (
            SlaComplianceDefinition, calculate_empirical_sla_sigma_from_ledgers,
        )
        # The original scorer is evaluated ONCE for each 200-trajectory ledger.
        # Its returned per-trajectory sla_compliant indicators are the exact
        # sufficient statistics for the frozen mean-over-horizons estimand:
        # mean_trajectory(mean_H(sla_compliant)).
        # Resampling complete trajectory statistics preserves dependence
        # among the 37 horizon readouts and costs O(B*N), not O(B*full ledger).
        rec=selected.set_index("query_id").loc[failed.query_id]
        rng=np.random.default_rng(seed)
        statistics={}
        for label,ledger_path,reference in (
                ("calibration",calib_ledger_path,float(failed[calibration_col])),
                ("confirmation",confirm_ledger_path,float(failed[confirmation_col]))):
            print("BOOTSTRAP_PRECOMPUTE",label,"loading ledger",flush=True)
            ledger=pd.read_csv(ledger_path)
            sigma, trajectory_curves, _ = calculate_empirical_sla_sigma_from_ledgers(
                ledger,
                latency_threshold=float(rec.A_G_l_max),
                cost_threshold=float(rec.A_G_c_max),
                quality_threshold=float(rec.A_G_q_min),
                horizons=list(HORIZONS),
                stop_time=240.0,
                sla_definition=SlaComplianceDefinition(
                    rho=float(failed.rho),
                    accounting_origin=0.0,
                    zero_decision_compliance=1.0,
                ),
            )
            matrix=trajectory_curves.pivot(
                index="trajectory",columns="horizon",values="sla_compliant",
            ).reindex(columns=list(HORIZONS))
            if matrix.shape!=(200,37) or matrix.isna().any().any():
                raise ValueError(f"{label}: expected complete 200x37 trajectory grid")
            values=matrix.to_numpy(dtype=float)
            if not np.isin(values,[0.,1.]).all():
                raise ValueError(f"{label}: nonbinary SLA compliance")
            # Invariant: the aggregate reconstructed by the original scorer
            # must match BOTH the frozen full-horizon curve and the saved mean.
            recovered=float(values.mean())
            aggregate=float(sigma.sigma.mean())
            if not (abs(recovered-reference)<=2e-9 and
                    abs(aggregate-reference)<=2e-9):
                raise AssertionError(
                    f"{label} original-scorer invariant failed: "
                    f"saved={reference:.12g}, recovered={recovered:.12g}, "
                    f"aggregate={aggregate:.12g}")
            means=values.mean(axis=1)
            print("BOOTSTRAP_PRECOMPUTE_PASS",label,
                  "trajectories",len(means),"mean",recovered,flush=True)
            # Vectorized, low-memory resampling; chunking permits progress.
            draws=np.empty(n_boot,dtype=float)
            chunk_size=250
            for start in range(0,n_boot,chunk_size):
                end=min(start+chunk_size,n_boot)
                indices=rng.integers(0,len(means),size=(end-start,len(means)))
                draws[start:end]=means[indices].mean(axis=1)
                print("BOOTSTRAP_PROGRESS",label,end,"/",n_boot,flush=True)
            statistics[label]=draws
        diffs=statistics["confirmation"]-statistics["calibration"]
        result["bootstrap"]={
            "method":"exact per-trajectory horizon-averaged SLA indicators, frozen query; bootstrap trajectory indices",
            "replicates":n_boot,"seed":seed,
            "calibration_95_percentile_interval":np.quantile(statistics["calibration"],[.025,.975]).tolist(),
            "confirmation_95_percentile_interval":np.quantile(statistics["confirmation"],[.025,.975]).tolist(),
            "difference_95_percentile_interval":np.quantile(diffs,[.025,.975]).tolist(),
            "confirmation_below_easy_lower_empirical_fraction":float(
                np.mean(statistics["confirmation"]<REGIMES["Easy"][0])),
            "caution":"Descriptive bootstrap conditional on the frozen query; calibration-based scale selection is not accounted for."
        }
        with (out/"failed_query_bootstrap_samples.csv").open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["replicate","calibration","confirmation","difference"])
            for i in range(n_boot):
                w.writerow([i,float(statistics["calibration"][i]),float(statistics["confirmation"][i]),float(diffs[i])])
    (out/"analysis.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    report=[
        "# Independent Step-0 failure: read-only scientific analysis",
        "",
        "**Eligibility remains FAILED. The selected query and raw evidence were not changed.**",
        "",
        f"- Failed query: {failed.query_id}, scale {float(failed.scale):.2f}",
        f"- Calibration mean: {float(failed[calibration_col]):.6f}",
        f"- Confirmation mean: {float(failed[confirmation_col]):.6f}",
        f"- Shift: {float(failed['difference_confirmation_minus_calibration']):+.6f}",
        f"- Confirmation lower-edge margin: {float(failed.confirmation_lower_margin):+.6f}",
        f"- Negative shifts across 15: {result['all_queries']['negative_differences']}",
        f"- Positive shifts across 15: {result['all_queries']['positive_differences']}",
        f"- Median absolute shift across 15: {result['all_queries']['median_abs_difference']:.6f}",
        "",
        "## Interpretation",
        "Calibration-selected scales are frozen before confirmation. A near-boundary",
        "confirmation failure may be sampling variation; there is no basis to call",
        "it systematic from one selected query and one new world. Differences across",
        "the 15 queries share the same trajectories and should not be treated as",
        "15 independent replicates. Likewise, 37 horizons are repeated readouts.",
        "",
    ]
    if result["bootstrap"]:
        b=result["bootstrap"]
        report+=["## Trajectory-bootstrap descriptive uncertainty",
          f"- Calibration CI: {b['calibration_95_percentile_interval']}",
          f"- Confirmation CI: {b['confirmation_95_percentile_interval']}",
          f"- Confirmation-minus-calibration CI: {b['difference_95_percentile_interval']}",
          f"- Bootstrap fraction below Easy lower edge (frozen query): {b['confirmation_below_easy_lower_empirical_fraction']:.3f}",
          "This is not a hypothesis test accounting for adaptive scale selection.",
          ""]
    (out/"READ_ONLY_ANALYSIS.md").write_text("\n".join(report))
    print("STEP0_FAILURE_READONLY_ANALYSIS_PASS")
    print("FAILED_QUERY",failed.query_id,"CALIBRATION",float(failed[calibration_col]),
          "CONFIRMATION",float(failed[confirmation_col]))
    print("QUERY_SHIFTS negative",result["all_queries"]["negative_differences"],
          "positive",result["all_queries"]["positive_differences"])
    if result["bootstrap"]:
        print("BOOTSTRAP_DIFF_CI",result["bootstrap"]["difference_95_percentile_interval"])
    print("OUT",out)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--bootstrap",default=0,type=int,help="Optional cluster bootstrap replications")
    ap.add_argument("--seed",default=20261110,type=int)
    args=ap.parse_args()
    audit(args.pilot,args.out,args.bootstrap,args.seed)


if __name__=="__main__":
    main()
