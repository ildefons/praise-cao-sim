"""I2b-v4 feasibility audit: mean full-segment excursion as a NEW public aggregate.

Uses existing Phase-5 provider request ledgers only to construct aggregate window
statistics. Never publishes trajectory identities or individual excursion values.
I2b-v3 public endpoint pairs alone CANNOT yield internal excursions.
No reconstruction or graph simulation. Development evidence only.
"""
from __future__ import annotations
import argparse
import sys
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))
from phase5_runtime_v2 import read_json,write_json,sha256_file,utc_now_iso,git_head
from run_phase6_i2a_marginal_audit_v1 import _compliance_samples_from_ledger

OUT=HERE/"results"/"35_i2b_v4_mean_range_feasibility"
P5=PHASE5/"results"/"01_i1"
P6=HERE/"results"/"22_i2b_public_representation"
WORLDS=("P4",)   # P4 is development only; expand only by explicit decision
PROVIDERS=("ProviderA","ProviderB","ProviderC")
LAGS=(20,30,40,50,75,100,150,200)
TOL=1e-12

def provider(world,provider):
    card=P5/world/"public"/provider/"card.json"
    ledger_path=P5/world/"private"/"sigma"/provider/"provider_request_ledgers.csv"
    pairs_path=P6/world/provider/"i2b_public_temporal_pairs.csv"
    for p in (card,ledger_path,pairs_path):
        if not p.is_file():
            raise FileNotFoundError(p)
    samples=_compliance_samples_from_ledger(pd.read_csv(ledger_path),metadata=read_json(card))
    pairs=pd.read_csv(pairs_path)
    rows=[]
    for rid,g in samples.groupby("region_id",sort=True):
        pivot=g.pivot(index="trajectory_private",columns="H",values="compliance_fraction").sort_index(axis=1)
        if pivot.shape!=(100,48) or not np.array_equal(pivot.columns.astype(int),np.arange(5,241,5)):
            raise RuntimeError("unexpected private temporal sampling")
        arr=pivot.to_numpy(dtype=float)
        for lag in LAGS:
            for start in range(5,241-lag,10):
                end=start+lag
                # H grid is 5 seconds, including both endpoints.
                ix=np.arange((start-5)//5,(end-5)//5+1,dtype=int)
                segment=arr[:,ix]
                ranges=np.ptp(segment,axis=1)
                d=arr[:,(end-5)//5]-arr[:,(start-5)//5]
                if np.any(ranges+TOL<np.abs(d)):
                    raise RuntimeError("internal range smaller than endpoint difference")
                rows.append(dict(provider_world_id=world,provider_id=provider,
                    region_id=str(rid),start_H=float(start),end_H=float(end),
                    lag_s=float(lag),n=100,
                    mean_range=float(np.mean(ranges)),
                    mean_squared_endpoint_change_private=float(np.mean(d*d)),
                    mean_absolute_endpoint_change_private=float(np.mean(np.abs(d)))))
    df=pd.DataFrame(rows)
    if len(df)!=630:
        raise RuntimeError("expected 630 windows")
    public=(pairs.groupby(["region_id","lag_s","start_H","end_H"],sort=True)
      .apply(lambda x:float(np.mean(np.square(x["compliance_end"].to_numpy()-x["compliance_start"].to_numpy()))),include_groups=False)
      .rename("v3_endpoint_variation").reset_index())
    df=df.merge(public,on=["region_id","lag_s","start_H","end_H"],validate="one_to_one")
    if not np.allclose(df.mean_squared_endpoint_change_private,df.v3_endpoint_variation,atol=1e-12,rtol=0):
        raise RuntimeError("private/public endpoint values disagree")
    df["v3_weight"]=0.0
    df["v4_mean_range_weight"]=0.0
    for (_, _),ids in df.groupby(["region_id","lag_s"]).groups.items():
        ix=list(ids)
        for src,dst in (("v3_endpoint_variation","v3_weight"),("mean_range","v4_mean_range_weight")):
            vals=df.loc[ix,src].to_numpy(dtype=float)
            total=vals.sum()
            share=vals/total if total>TOL else np.full(len(ix),1/len(ix))
            df.loc[ix,dst]=share/40.0
    for column in ("v3_weight","v4_mean_range_weight"):
        assert np.isclose(df[column].sum(),1,atol=TOL)
        assert np.allclose(df.groupby("region_id")[column].sum(),0.2,atol=TOL)
        assert np.allclose(df.groupby("lag_s")[column].sum(),0.125,atol=TOL)
    a=df.v3_weight.to_numpy();b=df.v4_mean_range_weight.to_numpy()
    summary=dict(provider_world_id=world,provider_id=provider,
        windows=len(df),
        neff_v3=float(1/np.sum(a*a)),neff_v4=float(1/np.sum(b*b)),
        max_weight_v3=float(max(a)),max_weight_v4=float(max(b)),
        weight_l1_shift=float(np.abs(a-b).sum()),
        weight_pearson=float(np.corrcoef(a,b)[0,1]),
        zero_range_windows=int((df.mean_range<=TOL).sum()),
        mean_internal_range=float(df.mean_range.mean()),
        mean_abs_endpoint_change=float(df.mean_absolute_endpoint_change_private.mean()))
    return df,summary,{"card":sha256_file(card),"source_private_ledger":sha256_file(ledger_path),"public_pairs":sha256_file(pairs_path)}

def main():
    ap=argparse.ArgumentParser()
    ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    frames=[];summary=[];hashes={}
    for world in WORLDS:
        for p in PROVIDERS:
            d,s,h=provider(world,p)
            frames.append(d);summary.append(s);hashes[f"{world}/{p}"]=h
            print(f"I2B-V4 RANGE AUDIT {world}/{p} Neff={s['neff_v4']:.1f} L1={s['weight_l1_shift']:.3f}",flush=True)
    frame=pd.concat(frames,ignore_index=True)
    st=pd.DataFrame(summary)
    windows=OUT/"v3_v4_window_weights.csv"; summaries=OUT/"provider_range_summary.csv"
    frame.to_csv(windows,index=False);st.to_csv(summaries,index=False)
    manifest=OUT/"i2b_v4_range_feasibility_manifest.json"
    write_json(manifest,dict(status="PHASE6_I2B_V4_MEAN_RANGE_FEASIBILITY_COMPLETE",
        development_evidence=True,code_commit=git_head(),
        scope="P4 providers only",new_public_observable=True,
        distinction="I2b-v3 anonymous endpoint pairs do not determine within-segment range",
        definition="mean across 100 private trajectories of max-minus-min observed compliance on 5s H grid inside each window",
        public_release="aggregate mean range per region/lag/start/end only; no trajectory identities or individual samples",
        frozen_outer_weight="equal 1/5 region and equal 1/8 lag",
        no_new_provider_simulation=True,no_reconstruction=True,no_graph_prediction=True,
        graph_wb_read=False,hidden_provider_parameters_read=False,
        input_hashes=hashes,
        output_sha256={"weights":sha256_file(windows),"summary":sha256_file(summaries)},
        completed_utc=utc_now_iso()))
    bundle=OUT/"i2b_v4_mean_range_feasibility_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in (windows,summaries,manifest):z.write(p,arcname=p.name)
    print("PHASE6_I2B_V4_MEAN_RANGE_FEASIBILITY_PASS")
    print(st.to_string(index=False))
    print("UPLOAD BUNDLE",bundle)

if __name__=="__main__":
    main()
