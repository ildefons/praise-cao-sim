"""Read-only semantic audit of public I1 and graph-conditioned provider traces.

Does not run simulations or reinterpret provider estimates as guarantees.
"""
from pathlib import Path
import json
import pandas as pd
from phase5_runtime_v2 import load_phase5_contracts,graph_record
HERE=Path(__file__).resolve().parent
FIRST=HERE.parent
OUT=HERE/"results"/"47_guarantee_semantics_audit"
def require(text,needle,path):
    if needle not in text:raise RuntimeError(f"Expected semantic invariant not present in {path.name}: {needle}")
def main():
    out=OUT
    out.mkdir(parents=True,exist_ok=True)
    sources={
        "i1_acquisition":FIRST/"phase2"/"i1_provider_acquisition.py",
        "i1_card":FIRST/"phase2"/"i1_provider_card.py",
        "i1_phase5":HERE/"run_phase5_i1_v2.py",
        "graph":HERE/"phase5_graph_simulator_v2.py",
        "ledger":FIRST/"phase3"/"m1_graph_simulator_v2.py",
    }
    texts={k:v.read_text() for k,v in sources.items()}
    require(texts["i1_acquisition"],"provider_completion_time - provider_arrival_time",sources["i1_acquisition"])
    require(texts["i1_acquisition"],"native_reception_time",sources["i1_acquisition"])
    require(texts["i1_card"],"wilson_binomial_interval",sources["i1_card"])
    require(texts["i1_phase5"],"W0/ParAll",sources["i1_phase5"])
    require(texts["graph"],"depends_on=tuple",sources["graph"])
    require(texts["ledger"],"extract_top_level_request_ledger_from_native_trace",sources["ledger"])
    contracts=load_phase5_contracts(HERE)
    graph=graph_record(contracts,"G_SEQPAR")
    rows=[]
    for p in ("ProviderA","ProviderB","ProviderC"):
        card_path=HERE/"results"/"01_i1"/"P4"/"public"/p/"card.json"
        surface_path=HERE/"results"/"01_i1"/"P4"/"public"/p/"sigma_surface.csv"
        card=json.loads(card_path.read_text())
        surface=pd.read_csv(surface_path)
        rows.append(dict(provider=p,public_card_schema=card.get("schema"),
            public_card_status=card.get("status"),
            surface_rows=len(surface),
            horizons=int(surface.horizon.nunique()) if "horizon" in surface else None,
            card_has_explicit_guarantee=any("guarantee" in str(k).lower() for k in card),
            card_has_wilson=any("wilson" in str(k).lower() for k in card),
            evidence="W0/ParAll local provider arrival accounting",
            graph_target="G_SEQPAR native branch dependency execution",
            match="NOT_ESTABLISHED"))
    table=pd.DataFrame(rows)
    table.to_csv(out/"provider_interface_audit.csv",index=False)
    report={
        "status":"SEMANTIC_AUDIT_COMPLETE_TRANSFER_NOT_ESTABLISHED",
        "graph_ast":graph["ast"],
        "sources":{k:str(p.relative_to(FIRST)) for k,p in sources.items()},
        "verified":[
            "I1 local latency is completion minus arrival at provider, with queue waiting",
            "I1 provider-arrived but uncompleted requests are preserved as censored records",
            "I1 acquisition is native W0/ParAll, reused across graph topologies",
            "G_SEQPAR uses dependency release; graph-conditioned arrival law may change",
            "Graph top-level request ledger discards native provider rows",
            "Current optional provider rows include only native completed module executions, not all expected branch arrivals",
            "Public sigma_hat/Wilson estimates alone do not prove contractual lower-bound semantics"
        ],
        "blockers":[
            "Need explicit assertion/coverage basis before calling empirical public I1 a lower guarantee",
            "Need full graph-specific provider arrival and censoring reconstruction, including dependent branch release",
            "Need matched workload/conditional guarantee contract or justified transfer across W0/ParAll and G_SEQPAR",
            "Need match accounting origin, regions, rho and H before one-sided constraints"
        ],
        "next_experiment":"Native trace diagnostic with per-provider receive/completion and unobserved branches, then exact first-violation survival curves with fixed local regions",
        "simulations":0
    }
    (out/"audit_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(report["status"])
    print(table.to_string(index=False))
    print("REPORT",out/"audit_report.json")
if __name__=="__main__":main()
