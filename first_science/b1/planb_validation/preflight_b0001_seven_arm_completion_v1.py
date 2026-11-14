#!/usr/bin/env python3
"""B0001 seven-arm completion: rigorous read-only source/availability preflight.

Original seven-arm B1 policy demands 7 x 12 independent method-cell MAEs.
Only M1, M2, M3_FULL343 have been generated in B0001; the four missing
methods are original 48-point-LHS Top14/Top1 and new-world 5-fold-I1-CV
Top14/Top1, with separately allocated B=1400 graph trajectories.

This utility checks provenance and policies, and freezes an INCOMPLETE
compatibility record. It executes zero local or graph simulations, opens no
hidden physical parameters, and does not label anything confirmed. It will
REFUSE a seven-arm complete status until evidence actually exists.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

ARMS=("M1","M2","M3_FULL343","ORIGINAL_TOP14_B1400",
      "ORIGINAL_TOP1_B1400","FIXED_CV_TOP14","FIXED_CV_TOP1")
WORLDS=("P1","P3","P4")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
MISSING=ARMS[3:]
SOURCE={
    "original_style_runner":"first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py",
    "original_style_config":"first_science/b1/retrospective_m3/config_pilot_m3_generalization_v1.json",
    "pilot_transfer_runner":"first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py",
    "pilot_transfer_core":"first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py",
    "pilot_transfer_config":"first_science/b1/retrospective_m3/config_pilot_m3_policy_transfer_v1.json",
    "fixed_cv_runner":"first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py",
    "b1_policy":"first_science/b1/planb_validation/b1_budget_comparison_v1.py",
    "kg_policy":"first_science/b1/planb_validation/b1_kg_one_step_v1.py",
    "two_stage_policy":"first_science/b1/planb_validation/b1_condition_selection_controlled_v1.py",
}
STATUS="B0001_SEVEN_ARM_COMPLETION_PREFLIGHT_BLOCKED_FOUR_METHODS_MISSING"


def require(ok,msg):
    if not ok: raise RuntimeError("B0001 SEVEN-ARM PREFLIGHT: "+msg)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""):
            h.update(chunk)
    return h.hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    a=argparse.ArgumentParser(description=__doc__)
    for key in ("evaluation","postrun","reference_audit","staging","reference","out"):
        a.add_argument("--"+key,type=Path,required=True)
    args=a.parse_args()
    for key in ("evaluation","postrun","reference_audit","staging","reference","out"):
        setattr(args,key,getattr(args,key).expanduser().resolve())
    repo=Path(__file__).resolve().parents[3]
    require(not args.out.exists(),"Refusing overwrite of existing preflight output")
    for source in (args.evaluation,args.postrun,args.reference_audit,
                   args.staging,args.reference):
        require(args.out!=source and source not in args.out.parents,
                "Output overlaps immutable evidence namespace")
    sources={key:{"path":rel,"sha256":sha(repo/rel)}
             for key,rel in SOURCE.items()}
    original=load(repo/SOURCE["original_style_config"])
    pilot=load(repo/SOURCE["pilot_transfer_config"])
    require(original["status"]=="B1_RETROSPECTIVE_M3_V1_DESIGN_FROZEN"
            and original["n_candidates_per_provider"]==48
            and original["top_k"]==14
            and original["lambda"]==30
            and original["graph_budget"]==1400
            and original["include_matched_top1"] is True,
            "Historical original-style candidate/Top14 definition changed")
    require(pilot["status"]=="B1_PILOT_M3_POLICY_TRANSFER_V1_FROZEN"
            and pilot["n_candidates_per_provider"]==48
            and pilot["top_k"]==14
            and pilot["target_mass"]==0.999
            and pilot["graph_budget"]==1400
            and len(pilot["lambda_grid"])==17
            and pilot["include_matched_top1"] is True,
            "Historical fixed-CV candidate/domain/lambda procedure changed")
    archive=repo/"first_science"/"b1"/"planb_validation"/"B1_EXECUTABLE_POLICY_FREEZE_V1.md"
    require("Seven methods" in archive.read_text()
            and "no further simulator noise sampled" in archive.read_text(),
            "Original B1 protocol changed")
    evaluated=args.evaluation/"b0001_deterministic_evaluation_freeze.json"
    evaluation=load(evaluated)
    require(evaluation["status"]=="B0001_FULL343_DETERMINISTIC_EVALUATION_FROZEN"
            and evaluation["n_cells"]==12
            and evaluation["primary_points_per_method"]==6660,
            "Independent B0001 M1/M2/M3 evaluation incomplete")
    metrics_file=args.evaluation/"primary_metrics.csv"
    require(sha(metrics_file)==evaluation["output_hashes_sha256"]["primary_metrics"],
            "B0001 existing three-arm source hash drift")
    metrics=pd.read_csv(metrics_file)
    chosen=metrics[metrics.scope=="provider_world_x_graph"]
    require(set(chosen.method_id)=={"M0",*ARMS[:3]},
            "Expected only four current primary methods")
    per=chosen[chosen.method_id.isin(ARMS[:3])]
    require(len(per)==36 and per.n_points.eq(555).all(),
            "Three complete 12-cell B0001 method observations required")
    audit=load(args.postrun/"b0001_full343_postrun_integrity_audit.json")
    ref=load(args.reference_audit/"b0001_final_reference_mechanical_audit.json")
    require(audit["status"]==
            "B0001_FULL343_POSTRUN_INTEGRITY_AUDIT_PASS_FINAL_WB_EMBARGOED"
            and audit["trajectories_verified"]==50400
            and ref["status"]==
            "B0001_FINAL_REFERENCE_MECHANICAL_AUDIT_PASS_EVALUATION_UNLOCKED"
            and ref["n_reference_trajectories"]==12000,
            "Prediction/reference independent audits incomplete")
    require(evaluation["reference_mechanical_audit_sha256"]==
            sha(args.reference_audit/"b0001_final_reference_mechanical_audit.json"),
            "Reference audit mutated")
    staged=load(args.staging/"b0001_public_inputs_manifest.json")
    require(staged["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE"
            and staged["cells"]==12,
            "B0001 public staged source incomplete")
    for role in WORLDS:
        for graph in GRAPHS:
            path=args.staging/"frozen_queries"/f"{role}__{graph}"/"step0_frozen_queries.csv"
            require(len(pd.read_csv(path))==15,
                    "B0001 frozen query set incomplete: "+str(path))
            reference=args.reference/f"{role}__{graph}"/"final_wb_curves.csv"
            require(reference.is_file(),
                    "Existing frozen independent WB unavailable: "+str(reference))
    plan={
        "status":STATUS,
        "purpose":"B0001 seven-arm independent-world transfer validation",
        "interpretation_limit":"Four supplementary method instantiations were implemented after the B0001 WB was opened and inspected; not a fully untouched preregistered seven-arm holdout.",
        "original_methods":list(ARMS),
        "existing_methods":list(ARMS[:3]),
        "missing_methods":list(MISSING),
        "eligible_cells":12,
        "existing_three_arm_action_count":36,
        "missing_action_count":48,
        "full_seven_arm_action_count":84,
        "fixed_graph_budget_per_missing_method_and_cell":1400,
        "max_additional_graph_trajectories_if_fully_separate":67200,
        "candidate_model_requirement":{
            "original_style":"48 public I1-derived LHS candidates/provider; lambda=30; original-style top14 and matched top1 with separately budgeted 1400 trajectories each",
            "fixed_cv":"48 public I1-derived LHS candidates/provider; public blocked five-fold CV selects lambda from frozen 17-value grid; independently weighted top14 and matched top1 B=1400 each",
            "original_style_and_fixed_cv_support_can_be_equated":False,
            "B0001_V3b_seven_candidate_support_is_valid_replacement":False,
            "B0001_M3_nested_topK_predictions_are_valid_replacement":False,
        },
        "whitebox_reference_is_already_open":True,
        "prohibit_tuning_from_B0001_WB":True,
        "independent_worlds_but_no_claim_of_untouched_7_arm_preregistration":True,
        "source_sha256":sources,
        "b0001_evaluation_manifest_sha256":sha(evaluated),
        "b0001_primary_metrics_sha256":sha(metrics_file),
        "b0001_prediction_postrun_audit_sha256":
            sha(args.postrun/"b0001_full343_postrun_integrity_audit.json"),
        "b0001_reference_audit_sha256":
            sha(args.reference_audit/"b0001_final_reference_mechanical_audit.json"),
        "b0001_public_staging_manifest_sha256":
            sha(args.staging/"b0001_public_inputs_manifest.json"),
        "simulations_performed":0,
        "seven_arm_confirmation_authorized":False,
        "candidate_preparation_or_graph_execution_authorized":False,
        "required_next_stage":"isolated 48-candidate public-I1 reconstruction adapter and non-WB reproduction tests; freeze supports then independently execute four missing graph prediction methods",
    }
    args.out.mkdir(parents=True)
    path=args.out/"b0001_seven_arm_gap_preflight.json"
    path.write_text(json.dumps(plan,indent=2,sort_keys=True)+"\n",
                    encoding="utf-8")
    print("B0001_SEVEN_ARM_GAP_PREFLIGHT_PASS_THREE_EXISTING_FOUR_MISSING")
    print("INDEPENDENT_B0001_REFERENCE_ALREADY_OPEN")
    print("ORIGINAL_STYLE_48_LHS_AND_FIXED_CV_48_LHS_REQUIRED")
    print("NO_SIMULATIONS / SEVEN_ARM_CONFIRMATION_BLOCKED")
    print("FREEZE",path)


if __name__=="__main__":
    main()
