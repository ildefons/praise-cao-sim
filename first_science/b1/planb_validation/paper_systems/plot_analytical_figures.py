"""Render revised manuscript figures from analytical intervals, not new runs.
Usage: python plot_analytical_figures.py analytical_curve_intervals.csv original_summary.csv output_dir
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STYLES = {
    'random': ('Random', '#64748b', 'o', '-'),
    'balanced': ('Balanced', '#059669', 's', '-'),
    'informed': ('Informed', '#9333ea', '^', '-'),
    'kg_one_step': ('KG: joint', '#2563eb', 'D', ':'),
    'kg_two_stage_adaptive': ('KG: two-stage adaptive', '#2563eb', 'v', '-'),
    'kg_two_stage_uniform': ('KG: two-stage uniform', '#2563eb', 'P', '--'),
    'budgeted_top2': ('Top2: joint (B-specific)', '#ea580c', 'X', ':'),
    'top2_two_stage_adaptive': ('Top2: two-stage adaptive (B-specific)', '#ea580c', 'h', '-'),
    'top2_two_stage_uniform': ('Top2: two-stage uniform (B-specific)', '#ea580c', '*', '--'),
}
BUDGETS=[10,15,20,25,30,35,40,45,55,65,70,75,80]
YMAX={'historical': .025, 'fresh_reference': .012}

def main():
    src, original, target=map(Path,sys.argv[1:]);target.mkdir(parents=True,exist_ok=True)
    x=pd.read_csv(src); old=pd.read_csv(original)
    keys=['archive','policy','budget']; merged=x.merge(old,on=keys,validate='one_to_one')
    assert len(x)==len(old)==len(merged)==234
    assert np.allclose(merged.estimate,merged.mean_regret,rtol=0,atol=1e-12)
    assert np.allclose(x.plot_low,x.low.clip(lower=0),atol=1e-14,rtol=0)
    assert np.allclose(x.plot_high,x.high,atol=1e-14,rtol=0)
    assert (x.plot_low<=x.estimate).all() and (x.estimate<=x.plot_high).all()
    for archive,ymax in YMAX.items():
        fig,ax=plt.subplots(figsize=(12.4,7.2)); s=x[x.archive==archive]
        assert len(s)==117 and s.plot_high.max()<=ymax
        for policy,(label,color,marker,line) in STYLES.items():
            f=s[s.policy==policy].sort_values('budget'); assert f.budget.tolist()==BUDGETS
            ax.errorbar(f.budget,f.estimate,yerr=(f.estimate-f.plot_low,f.plot_high-f.estimate),color=color,linestyle=line,marker=marker,markersize=4.4,linewidth=1.65,elinewidth=.85,capsize=2,alpha=.88,label=label)
        ax.set(xlim=(8,82),ylim=(0,ymax),xticks=BUDGETS,xlabel='Validation budget (distinct method–condition evaluations)',ylabel='Mean terminal simple regret (MAE; lower is better)')
        ax.tick_params(axis='x',labelsize=8)
        # Overleaf already trims the upper 24 bp; preserve title in standalone PDF
        # while ensuring top-axis tick label is not clipped in the manuscript.
        ax.set_title('Historical archive' if archive=='historical' else 'Fresh-reference archive',pad=18)
        ax.grid(axis='y',alpha=.24)
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.16),ncol=3,fontsize=8,frameon=False,columnspacing=1.8)
        fig.subplots_adjust(left=.09,right=.98,top=.92,bottom=.27)
        p=target/f'{archive}_nested6_plus_top2_13_budgets.pdf'
        fig.savefig(p,dpi=220,bbox_inches='tight',pad_inches=.12);plt.close(fig)
        print(p, 'points', len(s),'max interval',s.plot_high.max())
if __name__=='__main__':main()
