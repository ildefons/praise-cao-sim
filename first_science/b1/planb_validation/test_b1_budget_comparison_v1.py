"""Synthetic-only unit tests; no reported numbers come from PRAISE observations."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import b1_budget_comparison_v1 as b1


def csv_write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)


class B1SyntheticTests(unittest.TestCase):
    def make_archive(self,repo):
        Y=[]
        for i,method in enumerate(b1.METHODS):
            offsets=np.sin((i+1)*(np.arange(12)+1))*.012
            offsets-=offsets.mean()
            Y.append(b1.SOURCE_MEANS[method]+offsets)
        Y=np.array(Y)
        loc=b1.source_locations(repo)
        for kind,(metric,manifest) in loc.items():
            src={'phaseII':b1.METHODS[:3], 'original':b1.METHODS[3:5],
                 'fixedCV':b1.METHODS[5:]}[kind]
            rows=[]
            for method in src:
                i=b1.METHODS.index(method)
                for c,(w,g) in enumerate(b1.CELLS):
                    if kind=='phaseII':
                        rows.append({'method_id':method,'scope':'provider_world_x_graph',
                            'scope_value':f'provider_world_id={w}|graph_id={g}',
                            'n_points':555,'MAE':repr(float(Y[i,c]))})
                    else:
                        name=method
                        if kind=='fixedCV':
                            name={'FIXED_CV_TOP14':'B1_FIXED_CV_TOP14_B1400',
                                  'FIXED_CV_TOP1':'B1_FIXED_CV_TOP1_B1400'}[method]
                        rows.append({'method':name,'scope':'cell','cell':f'{w}__{g}',
                            'n_points':555,'mae':repr(float(Y[i,c]))})
            csv_write(metric,rows)
            manifest.parent.mkdir(parents=True,exist_ok=True)
            if kind=='phaseII':
                data={'status':'FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION',
                    'eligible_cells':12,'primary_window':'H60..H240',
                    'output_hashes_sha256':{'primary_metrics':b1.digest(metric)}}
            elif kind=='original':
                freeze=metric.parents[1]/'global_prediction_freeze.json'
                freeze.write_text(json.dumps({'status':'B1_RETROSPECTIVE_ALL_12_PREDICTIONS_FROZEN'}))
                data={'status':'B1_RETROSPECTIVE_EVALUATION_COMPLETE',
                    'metrics_sha256':b1.digest(metric),'prediction_freeze_sha256':b1.digest(freeze)}
            else:
                freeze=metric.parents[1]/'global_prediction_freeze.json'
                freeze.write_text(json.dumps({'status':'B1_FIXED_CV_ALL_12_PREDICTIONS_FROZEN'}))
                data={'status':'B1_FIXED_CV_12_CELL_EVALUATION_COMPLETE',
                    'metrics_sha256':b1.digest(metric),'global_freeze_sha256':b1.digest(freeze)}
            manifest.write_text(json.dumps(data))
        return Y

    def test_matrix_84_and_frozen_means(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);truth=self.make_archive(repo)
            observed,checked=b1.build_matrix(repo)
            self.assertEqual(observed.shape,(7,12))
            np.testing.assert_allclose(observed,truth,atol=1e-12)
            self.assertEqual(set(checked),{'phaseII','fixedCV','original'})

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);self.make_archive(repo)
            file,_=b1.source_locations(repo)['original']
            file.unlink()
            with self.assertRaises(FileNotFoundError):b1.build_matrix(repo)

    def test_changed_metric_detected(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);self.make_archive(repo)
            file,_=b1.source_locations(repo)['phaseII']
            with file.open('a') as f:f.write('\n')
            with self.assertRaisesRegex(ValueError,'SHA-256'):b1.build_matrix(repo)

    def test_budgeted_episode_and_terminal_scoring(self):
        with tempfile.TemporaryDirectory() as d:
            Y=self.make_archive(Path(d))
            for B in b1.BUDGETS:
                for p in b1.POLICIES:
                    row,trace=b1.evaluate_episode(Y,p,B,0,3,20261105)
                    self.assertEqual(len(trace),B)
                    self.assertEqual(len({(x['method'],x['world'],x['graph']) for x in trace}),B)
                    self.assertEqual(row['evaluations'],B)
                    self.assertGreaterEqual(row['simple_regret'],0)
                    self.assertTrue(np.isfinite(row['simple_regret']))

    def test_unrevealed_changes_do_not_change_policy(self):
        with tempfile.TemporaryDirectory() as d:
            Y=self.make_archive(Path(d))
            for p in b1.POLICIES:
                row,trace=b1.evaluate_episode(Y,p,15,0,1,20261105)
                visited={(x['method'],x['world'],x['graph']) for x in trace}
                a,c=next((a,c) for a,name in enumerate(b1.METHODS)
                           for c,(w,g) in enumerate(b1.CELLS)
                           if (name,w,g) not in visited)
                changed=Y.copy();changed[a,c]+=0.15
                row2,trace2=b1.evaluate_episode(changed,p,15,0,1,20261105)
                self.assertEqual([(x['method'],x['world'],x['graph']) for x in trace],
                                 [(x['method'],x['world'],x['graph']) for x in trace2])
                self.assertEqual(row['recommended'],row2['recommended'])

    def test_bootstrap_and_statistical_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            Y=self.make_archive(Path(d))
            rows=[]
            for B in b1.BUDGETS:
                for s in range(12):
                    for rep in range(2):
                        for p in b1.POLICIES:
                            row,_=b1.evaluate_episode(Y,p,B,s,rep,20261105)
                            rows.append(row)
            summary,contrasts=b1.summarize(rows,b1.BUDGETS,2,100,20261105)
            self.assertEqual(len(summary),20)
            self.assertEqual(len(contrasts),18)
            self.assertEqual(sum(x['budget']=='MEAN_OVER_5_BUDGETS' for x in contrasts),3)
            for r in summary:
                self.assertLessEqual(r['regret_low'],r['regret_high'])
                self.assertTrue(0<=r['p_correct']<=1)

if __name__=='__main__':unittest.main()
