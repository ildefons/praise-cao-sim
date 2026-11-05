"""Synthetic-only tests for the read-only B1 WB robustness audit."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import b1_wb_reference_robustness_v1 as wb


class ReferenceTests(unittest.TestCase):
    def test_shared_reference_cell_mae(self):
        n = len(wb.b1.CELLS) * wb.Q
        reference = np.full(n, .5)
        predictions = np.empty((7, n))
        for a in range(7):
            for c in range(12):
                predictions[a, c*wb.Q:(c+1)*wb.Q] = .5 + (a+c)/100.
        expected = np.array([[(a+c)/100. for c in range(12)] for a in range(7)])
        np.testing.assert_allclose(wb.cell_maes(predictions, reference), expected, atol=1e-12)

    def test_wb_outcomes_metadata_consistency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            meta=[]
            for w,g in wb.b1.CELLS:
                for q in range(15):
                    for h in range(60,241,5):
                        meta.append(dict(physical_cell_id=f"{w}__{g}",
                                         query_id=f"{w}__{g}_q{q}",H=float(h),sigma_wb=.5))
            frame=pd.DataFrame(meta)
            frame.insert(0,"point_index",np.arange(len(frame)))
            frame.to_csv(root/"meta.csv",index=False)
            o=np.zeros((1000,len(meta)),dtype=np.uint8)
            o[500:]=1
            np.savez_compressed(root/"out.npz",outcomes=o)
            m,a=wb.load_outcomes(root/"meta.csv",root/"out.npz")
            self.assertEqual(a.shape,(1000,6660))
            self.assertEqual(len(m),6660)
            frame.loc[0,"sigma_wb"]=.501
            frame.to_csv(root/"meta.csv",index=False)
            with self.assertRaisesRegex(ValueError,"fails to reproduce"):
                wb.load_outcomes(root/"meta.csv",root/"out.npz")

    def test_prediction_file_freeze_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)
            p=repo/"first_science/phase5/results/04_prediction_v3b_fullsupport/P1__G_PAR"
            p.mkdir(parents=True)
            f=p/"m1_predictions.csv"
            f.write_text("a,b\n1,2\n")
            manifest=dict(status="FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION",
                          inputs=dict(final_WB_read=False),
                          output_hashes_sha256=dict(m1_predictions=wb.b1.digest(f)))
            (p/"prediction_manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(wb.verify_curve(repo,"phaseII","P1__G_PAR","m1_predictions.csv"),f)
            f.write_text("a,b\n1,3\n")
            with self.assertRaisesRegex(ValueError,"changed since freeze"):
                wb.verify_curve(repo,"phaseII","P1__G_PAR","m1_predictions.csv")

    def test_frozen_probability_numeric_roundoff_vs_real_error(self):
        # M3 mixtures of normalized weights can exceed 1 by last-bit roundoff.
        values=np.full(wb.Q,0.5)
        values[0]=0.0
        values[1]=1.0+2e-15
        frame=pd.DataFrame({
            "query_id":[f"q{i}" for i in range(wb.Q)],
            "H":[60.+5.*(i%37) for i in range(wb.Q)],
            "sigma_hat":values,
        })
        recovered=wb.validated_frozen_probabilities(frame,Path("frozen.csv"),"P1__G_PARSEQ","M3_FULL343")
        expected=values.copy()
        expected[1]=1.0
        np.testing.assert_array_equal(recovered,expected)
        frame.loc[1,"sigma_hat"]=1.0001
        with self.assertRaisesRegex(ValueError,"Out-of-range"):
            wb.validated_frozen_probabilities(frame,Path("frozen.csv"),"P1__G_PARSEQ","M3_FULL343")
        frame.loc[1,"sigma_hat"]=np.nan
        with self.assertRaisesRegex(ValueError,"Nonfinite or unmatched"):
            wb.validated_frozen_probabilities(frame,Path("frozen.csv"),"P1__G_PARSEQ","M3_FULL343")

    def test_robustness_screening_manifest_json_serialization(self):
        # Regression: np.quantile emits numpy floats whose comparisons may
        # yield np.bool_, which cannot be serialized by json.dumps.
        ref_rows=[]
        for k in range(50):
            record={
                "winner":"M3_FULL343",
                "original_winner_still_best":1,
                "mu_M2":0.135,
                "mu_M3_FULL343":0.12,
                "primary_diff_mean_5B":-0.0028,
            }
            for B in wb.b1.BUDGETS:
                record[f"B{B}_top2_minus_balanced"]=-0.0028
            ref_rows.append(record)
        split_rows=[]
        for B in wb.b1.BUDGETS:
            for policy in wb.b1.POLICIES:
                split_rows.append({
                    "split":0,"direction":0,"budget":B,
                    "start":0,"replicate":0,"policy":policy,
                    "terminal_regret":0.001 if policy=="budgeted_top2" else 0.005,
                    "correct":1,"reference_best":"M3_FULL343",
                })
        with tempfile.TemporaryDirectory() as tmp:
            gates=wb.write_results(
                Path(tmp),pd.DataFrame(ref_rows),pd.DataFrame(split_rows),
                np.array([.157,.135,.120,.154,.162,.161,.192]),50,1)
            self.assertTrue(all(type(v) is bool for v in gates.values()))
            self.assertTrue(all(gates.values()))
            self.assertIsInstance(json.dumps({"screening_gate":gates}),str)
            self.assertTrue((Path(tmp)/"WB_REFERENCE_ROBUSTNESS_REPORT.md").exists())

    def test_disjoint_reference_affects_scoring_not_training(self):
        training=np.full((7,12),.45)
        training[0]=.02
        training[1]=.25
        heldout=np.full((7,12),.45)
        heldout[0]=.25
        heldout[1]=.01
        regret,correct,best=wb.split_episode(training,heldout,"balanced",7,0,0,20261106,0,0)
        self.assertEqual(best,"M2")
        self.assertEqual(correct,0)
        self.assertAlmostEqual(regret,.24)

    def test_frozen_recommendation_rescore(self):
        n=12*wb.Q
        outcomes=np.zeros((1000,n),dtype=np.uint8)
        outcomes[500:,:]=1
        matrix=np.zeros((7,12))
        for a in range(7):
            matrix[a,:]=.01+.02*a
        pred=np.array([np.full(n,.5+matrix[a,0]) for a in range(7)])
        frequencies=np.zeros((20,7))
        for i in range(5):
            frequencies[4*i+wb.b1.POLICIES.index("balanced"),2]=1
            frequencies[4*i+wb.b1.POLICIES.index("budgeted_top2"),0]=1
            frequencies[4*i+wb.b1.POLICIES.index("random"),3]=1
            frequencies[4*i+wb.b1.POLICIES.index("informed"),1]=1
        df=wb.reference_bootstrap(outcomes,pred,frequencies,matrix,8,20261106)
        self.assertTrue(df.original_winner_still_best.eq(1).all())
        np.testing.assert_allclose(df.primary_diff_mean_5B.to_numpy(float),-.04,atol=1e-12)


if __name__=="__main__":
    unittest.main()
