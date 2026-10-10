"""Compare frozen true-parameter oracle scores to archived original search/rescore candidates."""
from pathlib import Path
import pandas as pd,zipfile,sys
P5=Path(__file__).resolve().parent.parent/'phase5'
if str(P5) not in sys.path:sys.path.insert(0,str(P5))
from phase5_runtime_v2 import write_json
H=Path(__file__).resolve().parent
R=H/"results"/"44_true_parameter_oracle"
roots={"I2B_V1":"24_i2b_energy_reconstruction_p4",
       "I2B_V3":"32_i2b_hierarchical_reconstruction_p4"}
columns={"I2B_V1":("search_i2b_energy_vstat","rescore_i2b_energy_vstat"),
         "I2B_V3":("search_i2b_hierarchical_energy","rescore_i2b_hierarchical_energy")}
def main():
    oracle=pd.read_csv(R/"oracle_scores_and_domains.csv")
    rows=[]
    for item in oracle.itertuples(index=False):
        loc=H/"results"/roots[item.method]/item.provider
        csv=loc/("search_trials_256.csv" if item.bank=="search" else "rescore_top24.csv")
        trials=pd.read_csv(csv)
        col=columns[item.method][0 if item.bank=="search" else 1]
        if col not in trials:raise RuntimeError(f"{csv}: missing {col}; columns={list(trials.columns)}")
        values=trials[col].astype(float)
        best=float(values.min())
        rows.append(dict(method=item.method,provider=item.provider,bank=item.bank,
            oracle=float(item.score),best_archived=best,
            oracle_minus_best=float(item.score)-best,
            oracle_better=bool(float(item.score)<best),
            n_archived=len(trials)))
    out=pd.DataFrame(rows)
    out.to_csv(R/"oracle_vs_archived_scores.csv",index=False)
    write_json(R/"score_comparison_manifest.json",dict(status="PHASE6_ORACLE_ARCHIVED_COMPARISON_PASS",
        comparison="same objective and seed bank only",frozen_candidates=True))
    with zipfile.ZipFile(R/"oracle_vs_archived_bundle.zip","w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("oracle_vs_archived_scores.csv","score_comparison_manifest.json"):
            z.write(R/name,name)
    print("PHASE6_ORACLE_ARCHIVED_COMPARISON_PASS")
    print(out.to_string(index=False))
    print("UPLOAD BUNDLE",R/"oracle_vs_archived_bundle.zip")
if __name__=="__main__":main()
