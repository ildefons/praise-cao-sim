"""Pure read-only tests for proposed B1 independent physical-world sampling."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import preview_new_worlds_v0_1 as pw


class PreviewWorldsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = pw.load_json(pw.REPO / pw.CONTRACT)
        cls.proposal = pw.load_json(pw.DRAFT)

    def test_deterministic_disjoint_candidate_identifiers(self):
        first=pw.make_preview(self.proposal,self.source)
        second=pw.make_preview(self.proposal,self.source)
        self.assertEqual(first,second)
        n=(self.proposal["sampling"]["preview_batteries"] * len(pw.ROLES) *
           self.proposal["sampling"]["max_attempts_per_role"])
        self.assertEqual(len(first),n)
        self.assertEqual(len({c["candidate_id"] for c in first}),n)
        self.assertTrue(all(c["step0_status"] == "NOT_RUN" for c in first))
        self.assertTrue(all(c["security"] == "PRIVATE_GENERATING_PARAMETERS_NOT_FOR_POLICY"
                            for c in first))

    def test_valid_physics_no_exact_recycled_original_worlds(self):
        samples=pw.make_preview(self.proposal,self.source)
        historical={(int(w["D_instructions"]),float(w["delta"]))
                    for w in self.source["provider_worlds"]}
        for c in samples:
            self.assertLessEqual(c["max_approx_utilization"],.995)
            self.assertGreater(c["D_instructions"],0)
            self.assertNotIn((c["D_instructions"],c["delta"]),historical)
            if c["role"] in ("P1","P3"):
                self.assertEqual(c["delta"],0.)
            else:
                self.assertTrue(.06 <= c["delta"] <= .095)
            for provider in ("ProviderA","ProviderB","ProviderC"):
                self.assertGreater(c["provider_means"][provider],0)

    def test_reject_physics_and_step0_drift(self):
        p=copy.deepcopy(self.proposal)
        p["sampling"]["role_distributions"]["P4"]["D_million_uniform"]=[350.,390.]
        with self.assertRaisesRegex(ValueError,"utilization"):
            pw.make_preview(p,self.source)
        p=copy.deepcopy(self.proposal)
        p["eligibility"]["confirmation_n_per_cell"]=100
        with self.assertRaisesRegex(ValueError,"N=200"):
            pw.make_preview(p,self.source)
        p=copy.deepcopy(self.proposal)
        p["eligibility"]["all_four_graphs_required"]=["G_PAR"]
        with self.assertRaisesRegex(ValueError,"four graphs"):
            pw.make_preview(p,self.source)

    def test_prospective_first_pass_gating_and_pending(self):
        samples=[c for c in pw.make_preview(self.proposal,self.source)
                 if c["battery_id"]=="B0001"]
        grp={role:sorted([c["candidate_id"] for c in samples if c["role"]==role])
             for role in pw.ROLES}
        passes={g:pw.PASS for g in pw.GRAPHS}
        failed={**passes,"G_PARSEQ":pw.FAIL}
        evidence={
            grp["P1"][0]:failed,
            grp["P1"][1]:passes,
            grp["P3"][0]:passes,
            grp["P4"][0]:failed,
            grp["P4"][1]:passes,
        }
        result=pw.first_eligible_attempts(samples,evidence,"B0001")
        self.assertEqual(result,{"P1":grp["P1"][1],"P3":grp["P3"][0],
                                 "P4":grp["P4"][1]})
        evidence.pop(grp["P1"][0])
        pending=pw.first_eligible_attempts(samples,evidence,"B0001")
        self.assertIsNone(pending["P1"])  # cannot skip earlier unassessed attempt
        with self.assertRaisesRegex(ValueError,"Four exact graph"):
            pw.classify_four_graphs({"G_PAR":pw.PASS})
        with self.assertRaisesRegex(ValueError,"Unknown or incomplete"):
            pw.classify_four_graphs({g:"PENDING" for g in pw.GRAPHS})

    def test_output_refuses_overwrite(self):
        samples=pw.make_preview(self.proposal,self.source)
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"draft_preview"
            pw.write_preview(target,self.proposal,self.source,samples,{"contract":"a"})
            doc=json.loads((target/"PRIVATE_world_candidates.json").read_text())
            self.assertEqual(doc["provider_simulations_generated"],0)
            self.assertEqual(len(doc["candidates"]),len(samples))
            self.assertFalse(doc["execution_authorized"])
            self.assertTrue((target/"dry_run_manifest.json").exists())
            with self.assertRaises(FileExistsError):
                pw.write_preview(target,self.proposal,self.source,samples,{"contract":"a"})


if __name__=="__main__":
    unittest.main()
