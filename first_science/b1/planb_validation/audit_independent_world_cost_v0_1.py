#!/usr/bin/env python3
"""Read-only world / cost inventory for the PRAISE B1 independent-world feasibility gate.

Reads existing frozen contracts and local JSON manifests. Does NOT generate worlds,
run simulations, revise protocols, infer method-specific elapsed times or modify B1.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
WORLD_CONFIG = "first_science/phase5/config_phase5_recoverability_battery_v2.json"
GRAPH_CONFIG = "first_science/phase5/config_phase5_graph_prediction_v3b_fullsupport.json"
ORIGINAL_CONFIG = "first_science/b1/retrospective_m3/config_pilot_m3_generalization_v1.json"
SOURCE_FILES = (WORLD_CONFIG, GRAPH_CONFIG, ORIGINAL_CONFIG,
    "first_science/phase5/config_phase5_execution_contract_v2.json",
    "first_science/phase5/config_phase5_final_wb_v3b_fullsupport.json",
    "first_science/phase5/run_phase5_step0_v2.py",
    "first_science/phase5/run_phase5_i1_v2.py",
    "first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py",
    "first_science/phase5/run_phase5_final_wb_v3b_fullsupport.py",
    "first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py",
    "first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py")
WORLDS = ("P1","P3","P4")
GRAPHS = ("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")


def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(2**20),b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")


def write_csv(path,rows,fields):
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def inspect_contracts(repo):
    sources={}
    for p in SOURCE_FILES:
        full=repo/p
        if not full.is_file():raise FileNotFoundError(f"Missing source contract {full}")
        sources[p]=sha(full)
    world=read(repo/WORLD_CONFIG)
    graph=read(repo/GRAPH_CONFIG)
    original=read(repo/ORIGINAL_CONFIG)
    if len(world["provider_worlds"])!=4 or len(world["graphs"])!=4:
        raise ValueError("Historical Phase-5 world/graph structure changed")
    if [w["id"] for w in world["provider_worlds"]] != ["P1","P2","P3","P4"]:
        raise ValueError("Unexpected world roles")
    if set(graph["eligibility"]["eligible_provider_worlds"])!=set(WORLDS):
        raise ValueError("Historical eligible-world set changed")
    if graph["eligibility"]["gate_failed_provider_world"]!="P2":
        raise ValueError("Original Step-0 failed-world status changed")
    methods=graph["methods"]
    pred={
        "M1":int(methods["M1"]["joint_models"])*int(methods["M1"]["graph_trajectories_per_joint_model"]),
        "M2":int(methods["M2"]["joint_models"])*int(methods["M2"]["graph_trajectories_per_joint_model"]),
        "M3_FULL343":int(methods["M3"]["graph_budget_per_physical_cell"]),
        "ORIGINAL_TOP14_B1400":int(original["graph_budget"]),
        "ORIGINAL_TOP1_B1400":int(original["graph_budget"]),
        "FIXED_CV_TOP14":1400, # checked below against frozen runner constant
        "FIXED_CV_TOP1":1400,
    }
    fixed_source=(repo/SOURCE_FILES[-1]).read_text(encoding="utf-8")
    if "BUDGET = 1400" not in fixed_source or "METHODS = ((TOP14" not in fixed_source:
        raise ValueError("Fixed-CV production budget no longer matches source")
    wb=read(repo/"first_science/phase5/config_phase5_final_wb_v3b_fullsupport.json")
    wb_n=int(wb["execution"]["n_trajectories_per_eligible_physical_cell"]) if "execution" in wb else 1000
    if wb_n!=1000:raise ValueError("WB trajectory budget changed")
    if sum(pred.values())!=9800:
        raise ValueError("Historical 9,800 prediction graph trajectories/cell changed")
    desc={
        "world_rows":[{"id":w["id"],"D_instructions":w["D_instructions"],
                        "delta":w["delta"],"means":w["provider_means"],
                        "approx_utilization":w["approx_utilization"],
                        "original_eligible":w["id"] in WORLDS} for w in world["provider_worlds"]],
        "world_generator_status":"FIXED DESIGN POINTS; no prospective probability distribution specified",
        "provider_family":world["provider_family"],
        "workload":world["workload"],
        "graphs":[{"id":g["id"],"expression":g["expression"]} for g in world["graphs"]],
        "historical_eligibility":graph["eligibility"],
        "new_worlds_are_not_generated":True,
    }
    counts=[{"method":k,"trajectories_per_cell":v,"trajectories_12_cells":12*v}
            for k,v in pred.items()]
    counts.append({"method":"FINAL_WB","trajectories_per_cell":wb_n,"trajectories_12_cells":12*wb_n})
    cost={
        "unit":"native graph trajectory, not elapsed CPU hour and not equal marginal cost across methods",
        "count_by_method":counts,
        "prediction_trajectories_per_cell":sum(pred.values()),
        "prediction_trajectories_per_12_cell_battery":12*sum(pred.values()),
        "whitebox_trajectories_per_12_cell_battery":12*wb_n,
        "total_graph_trajectories_per_complete_12_cell_battery":12*(sum(pred.values())+wb_n),
        "original_PhaseII_M1_M2_M3_plus_WB_graph_count":12*(100+2700+1400+1000),
        "ratio_graph_count_vs_original_phaseII":12*(sum(pred.values())+wb_n)/(12*(100+2700+1400+1000)),
        "step0_calibration_and_confirmation_per_cell":400,
        "step0_trajectories_for_12_cells_if_every_calibration_passes":12*400,
        "I1_graph_trajectories_for_three_new_worlds":3*200,
        "original_style_provider_local_candidate_trajectories_for_three_worlds":3*3*48*100,
        "fixed_cv_provider_local_candidate_trajectories_for_three_worlds":3*3*48*100,
        "provider_local_count_notes":"Separate reconstructed candidate banks are used by the original-style and fixed-CV branches. They are provider-local simulations, NOT interchangeable with graph trajectories. Current historical caches do not transfer to unseen world parameters.",
        "excluded":"Other V3/V3b provider reconstruction, failures/retakes, query scoring and I/O, wall-time overlap, installation/setup, parallel contention",
        "new_battery_wall_hours":"NOT_ESTIMABLE from trajectory counts alone",
    }
    return desc,cost,sources


def inventory_manifests(repo):
    base=repo/"first_science/phase5/results"
    rows=[]
    def record(stage, rel, world="", graph="", provider=""):
        p=base/rel
        row={"stage":stage,"world":world,"graph":graph,"provider":provider,
             "path":str(p.relative_to(repo)),"status":"MISSING",
             "python_wall_seconds":"","simulation_wall_seconds":"",
             "completed_utc":"","json_sha256":""}
        if p.is_file():
            try:m=read(p)
            except (ValueError,UnicodeError) as e:
                row["status"]="UNPARSEABLE"; rows.append(row);return
            row["status"]=str(m.get("status","STATUS_NOT_RECORDED"))
            row["json_sha256"]=sha(p)
            row["completed_utc"]=str(m.get("completed_utc",""))
            for field in ("python_wall_seconds","simulation_wall_seconds"):
                v=m.get(field)
                if isinstance(v,(int,float)) and not isinstance(v,bool) and v>=0:
                    row[field]=float(v)
        rows.append(row)
    for world in WORLDS:
        record("I1",f"01_i1/{world}/i1_freeze_manifest.json",world=world)
        for provider in ("ProviderA","ProviderB","ProviderC"):
            record("original_provider_candidate",
                f"b1_pilot_m3_retrospective_v1/candidates/{world}/{provider}/provider_manifest.json",
                world=world,provider=provider)
        for graph in GRAPHS:
            cell=f"{world}__{graph}"
            record("Step0_calibration",f"02_step0/{cell}/step0_calibration_manifest.json",world,graph)
            record("Step0_confirmation",f"02_step0/{cell}/step0_confirmation_manifest.json",world,graph)
            record("PhaseII_M1_M2_M3_combined",f"04_prediction_v3b_fullsupport/{cell}/prediction_manifest.json",world,graph)
            record("WB_final",f"05_final_wb_v3b_fullsupport/{cell}/final_wb_manifest.json",world,graph)
            record("original_Top14_Top1_combined",f"b1_pilot_m3_retrospective_v1/predictions/{cell}/prediction_manifest.json",world,graph)
            record("fixedCV_Top14_Top1_combined",f"b1_fixed_cv_top1_top14_b1400_v1/predictions/{cell}/prediction_manifest.json",world,graph)
    groups=sorted(set(r["stage"] for r in rows))
    summary=[]
    for group in groups:
        subset=[r for r in rows if r["stage"]==group]
        vals=[float(r["python_wall_seconds"]) for r in subset if r["python_wall_seconds"]!=""]
        simulation=[float(r["simulation_wall_seconds"]) for r in subset if r["simulation_wall_seconds"]!=""]
        summary.append({"stage":group,"expected_manifest_count":len(subset),
            "present_manifest_count":sum(r["status"]!="MISSING" for r in subset),
            "count_with_measured_python_wall_seconds":len(vals),
            "sum_python_wall_hours":round(sum(vals)/3600,6) if vals else "",
            "median_python_wall_minutes":round(statistics.median(vals)/60,4) if vals else "",
            "min_python_wall_minutes":round(min(vals)/60,4) if vals else "",
            "max_python_wall_minutes":round(max(vals)/60,4) if vals else "",
            "count_with_simulation_wall_seconds":len(simulation)})
    return rows,summary


def report(repo,out,world,cost,rows,summary):
    parts=["# B1 independent-world and computational-cost feasibility: local source inventory","",
           "**Status: read-only engineering audit; NOT confirmation and NOT authorization for fresh simulation.**",
           "",
           "## Historical world definitions and transfer blocker","",
           "| World | D (million instructions) | delta | Original eligibility |",
           "|---|---:|---:|---|"]
    for w in world["world_rows"]:
        parts.append(f"| {w['id']} | {w['D_instructions']/1e6:g} | {w['delta']:.2f} | {'Eligible (4 graphs)' if w['original_eligible'] else 'Failed Step-0 (4 graphs)'} |")
    parts+=["","The original configs specify **fixed points**, not an independently sampled generative distribution. Fresh simulator seed banks alone do not create independent worlds. Prespecify physical-world sampling (including an explicit rejection/eligibility rule) before generating new worlds.",
            "",
            "## Frozen graph trajectory workload","",
            "| Component | Graph trajectories per cell | 12-cell battery |",
            "|---|---:|---:|"]
    for rec in cost["count_by_method"]:
        parts.append(f"| {rec['method']} | {rec['trajectories_per_cell']:,} | {rec['trajectories_12_cells']:,} |")
    parts+=["",f"Total native graph trajectories: **{cost['total_graph_trajectories_per_complete_12_cell_battery']:,}**, including WB. This is **{cost['ratio_graph_count_vs_original_phaseII']:.2f}×** the original M1/M2/M3-plus-WB graph trajectory count; it is **not** a wall-time multiplier.",
            f"Additional Step-0: **{cost['step0_trajectories_for_12_cells_if_every_calibration_passes']:,}** simulation trajectories, conditional on every calibration passing.",
            f"Public I1: **{cost['I1_graph_trajectories_for_three_new_worlds']:,}** world-graph trajectories.",
            f"Original-style candidate preparation: **{cost['original_style_provider_local_candidate_trajectories_for_three_worlds']:,}** provider-local candidate trajectories.",
            f"Fixed-CV candidate preparation: **{cost['fixed_cv_provider_local_candidate_trajectories_for_three_worlds']:,}** provider-local candidate trajectories in a separately reconstructed bank.",
            "These categories have different per-trajectory workloads and **must not be added as interchangeable CPU costs**. The provider-candidate counts are inferred from fixed 48 candidates/provider and 100 local rescores/candidate; initial V3/V3b reconstruction and other setup remain unpriced.",
            "",
            "## Recorded stage wall-time inventory","",
            "| Stage | Manifest coverage | With measured wall time | Sum measured per-unit hours | Median per-unit minutes |",
            "|---|---:|---:|---:|---:|"]
    for s in summary:
        sumhours = f"{s['sum_python_wall_hours']:.3f}" if s["sum_python_wall_hours"]!="" else "Not recorded"
        median = f"{s['median_python_wall_minutes']:.1f}" if s["median_python_wall_minutes"]!="" else "—"
        parts.append(f"| {s['stage']} | {s['present_manifest_count']}/{s['expected_manifest_count']} | {s['count_with_measured_python_wall_seconds']} | {sumhours} | {median} |")
    parts+=["","A stage's summed per-cell/wall durations are **not** an end-to-end makespan when cells ran concurrently. The Phase-II prediction manifests bundle M1, M2 and M3. Neither original-style nor fixed-CV prediction manifests necessarily provide dedicated elapsed seconds; missing numbers are **unknown**, not zero. Do not add simulation seconds to Python wall seconds for one stage (they overlap).",
            "",
            "## Stop/go interpretation","",
            "1. **World-generation BLOCKED:** choose an explicit probability distribution for independent physical provider configurations, with validity bounds and eligibility attrition measured on all draws. The existing frozen P1/P3/P4 are roles/points, not a random sampling law.",
            "2. **Full-battery costs NOT YET PRICED:** obtain stage-separated local timing for the original Top14/Top1, fixed-CV Top14/Top1, I1, Step-0 and candidate search, plus method-level marginal cost when methods share a world/provider cache. Historical Phase-II aggregated wall hours alone do not suffice.",
            "3. **Battery completeness risk:** a single failed world×graph Step-0 cell prevents the unchanged 7×12 selection estimand from being evaluated. Do not silently replace failures or change the five-budget policy; resolve predeclared sampling/eligibility handling.",
            "4. **Next feasibility gate:** measure a defensible per-complete-battery cost (with variability and startup overhead), and size the number of genuinely independent validation batteries before new simulation.",
            "5. **No method modification:** B1 v1 policies, all five budgets and historic results stay frozen. Incremental-budget continuation remains deferred.",
            "",
            "## Outputs","",
            "- world_contract_audit.json: exact frozen world/family definition and graph roles.",
            "- trajectory_workload_counts.json: deterministic trajectory accounting, not hour estimates.",
            "- historical_manifest_costs.csv: inventory of local archived stage manifest timing and status.",
            "- historical_stage_cost_summary.csv: coverage and measured per-unit wall times.",
            "- audit_manifest.json: code and input/output SHA-256 inventory.",
            ""]
    (out/"WORLD_COST_FEASIBILITY_AUDIT.md").write_text("\n".join(parts),encoding="utf-8")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=Path,default=ROOT.parent.parent)
    p.add_argument("--out",type=Path,default=Path.home()/"praise/planb_b1_world_cost_feasibility_v0_1")
    args=p.parse_args()
    repo=args.repo.expanduser().resolve()
    out=args.out.expanduser().resolve()
    out.mkdir(parents=True,exist_ok=True)
    world,cost,source_hashes=inspect_contracts(repo)
    rows,summary=inventory_manifests(repo)
    save(out/"world_contract_audit.json",world)
    save(out/"trajectory_workload_counts.json",cost)
    write_csv(out/"historical_manifest_costs.csv",rows,list(rows[0]))
    write_csv(out/"historical_stage_cost_summary.csv",summary,list(summary[0]))
    report(repo,out,world,cost,rows,summary)
    saved={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    save(out/"audit_manifest.json",{
        "status":"B1_INDEPENDENT_WORLD_COST_FEASIBILITY_AUDIT_V0_1",
        "read_only":True,"fresh_world_simulations":0,
        "B1_selection_policies_changed":False,
        "input_source_sha256":source_hashes,
        "output_sha256":saved})
    print("B1_WORLD_COST_SOURCE_AUDIT_PASS")
    print("FIXED_WORLDS_ONLY; INDEPENDENT_GENERATOR_NOT_SPECIFIED")
    print("GRAPH_TRAJECTORY_COUNT_PER_FRESH_COMPLETE_BATTERY",cost["total_graph_trajectories_per_complete_12_cell_battery"])
    for s in summary:
        print("TIMING",s["stage"],f"{s['present_manifest_count']}/{s['expected_manifest_count']} manifests",
            "measured",s["count_with_measured_python_wall_seconds"],
            "sum_wall_h",s["sum_python_wall_hours"] if s["sum_python_wall_hours"]!="" else "NOT_RECORDED")
    print("REPORT",out/"WORLD_COST_FEASIBILITY_AUDIT.md")


if __name__=="__main__":
    main()
