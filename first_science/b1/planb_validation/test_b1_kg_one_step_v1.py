"""Synthetic correctness tests; no archived outcomes or scientific replay."""
import math
import unittest

import numpy as np

import b1_kg_one_step_v1 as kg


class KGTests(unittest.TestCase):
    def test_one_step_normal_quadrature(self):
        # Independent integration, not calling the KG implementation or posterior.
        for mean, other, sd in [(.10,.12,.04),(.11,.03,.07),(.2,.2,.06),(.15,.04,.02)]:
            base = min(mean,other)
            z = np.linspace(-10,10,200001)
            phi = np.exp(-z*z/2)/math.sqrt(2*math.pi)
            improvement = base - np.minimum(mean+sd*z,other)
            integrated = float(np.trapezoid(improvement*phi,z))
            expected=kg.kg_gain(abs(mean-other),sd)
            self.assertAlmostEqual(integrated,expected,delta=2e-8)

    def test_zero_invalid_and_bounds(self):
        self.assertEqual(kg.kg_gain(0,0),0)
        self.assertEqual(kg.kg_gain(10,0),0)
        self.assertAlmostEqual(kg.kg_gain(0,.05),.05/math.sqrt(2*math.pi),places=12)
        for d,s in [(-1,1),(1,-1),(math.nan,.2)]:
            with self.assertRaises(ValueError):kg.kg_gain(d,s)
        for gap in [0,.01,.1,.3,1]:
            scores=[kg.kg_gain(gap,s) for s in [.001,.01,.03,.07,.1]]
            self.assertTrue(all(x>=0 for x in scores))
            self.assertTrue(all(a<=b+1e-14 for a,b in zip(scores,scores[1:])))

    def test_analytic_score_matches_posterior_hypotheticals(self):
        b=kg.frozen
        seen=[(a,1,float(.11 + .013*a)) for a in range(7)]
        means,_,covs=b.posterior(seen)
        a,c=0,4
        analytic=float(kg.scores_from_posterior(means,covs,[(a,c,0)])[0])
        x=b.XX[c]
        var=b.NOISE**2+x@covs[a]@x
        q=math.sqrt(var)
        # Current parameter posterior mean can be inferred by the conditioned
        # algorithm's individual Gaussian regression normal equations.
        precision=np.diag(1/b.PRIOR_VAR)+np.outer(b.XX[1],b.XX[1])/b.NOISE**2
        rhs=b.PRIOR_MEAN/b.PRIOR_VAR+b.XX[1]*seen[a][2]/b.NOISE**2
        theta=np.linalg.solve(precision,rhs)
        pred=float(x@theta)
        phi_nodes=np.linspace(-10,10,30001)
        for z in phi_nodes[::500]:
            hypothetical=list(seen)+[(a,c,pred+q*z)]
            mnew,_,_=b.posterior(hypothetical)
            target=means[a]+(float(b.V@covs[a]@x)/q)*z
            self.assertAlmostEqual(mnew[a],target,places=11)
        competitor=min(means[j] for j in range(7) if j!=a)
        shift=float(b.V@covs[a]@x)/q
        z=phi_nodes
        numer=float(np.trapezoid((min(means[a],competitor)-np.minimum(means[a]+shift*z,competitor))*np.exp(-.5*z*z)/math.sqrt(2*math.pi),z))
        self.assertAlmostEqual(numer,analytic,delta=1e-7)

    def test_eligible_mask_and_deterministic_rng(self):
        seen=[(a,0,.1+.005*a) for a in range(7)]
        p=np.random.default_rng(24)
        q=np.random.default_rng(24)
        self.assertEqual(kg.select_kg(seen,p),kg.select_kg(seen,q))
        for a,c,_ in seen: self.assertNotEqual((a,c),kg.select_kg(seen,np.random.default_rng(24)))
        with self.assertRaisesRegex(ValueError,'observed twice'):
            kg.select_kg(seen+[seen[0]],np.random.default_rng(12))

    def test_simulated_episode_budgets_all(self):
        matrix=np.linspace(.01,.2,84).reshape(7,12)
        for B in kg.EXPECTED_BUDGETS:
            r,trace=kg.episode(matrix,B,1,0)
            self.assertEqual(len(trace),B)
            self.assertEqual(r['evaluations'],B)
            self.assertEqual(len({(x['method'],x['world'],x['graph']) for x in trace}),B)
            self.assertEqual({x['world']+'__'+x['graph'] for x in trace[:7]}, {'P1__G_PARSEQ'})
            self.assertEqual(trace,kg.episode(matrix,B,1,0)[1])

    def test_no_hidden_data_leakage_before_reveal(self):
        # At initial seven evaluations, vary every unobserved entry; first
        # KG selection is invariant (same observed values and RNG).
        a=np.full((7,12),.17)
        b=np.full((7,12),.3)
        a[:,0]=b[:,0]=np.linspace(.09,.21,7)
        _,trace_a=kg.episode(a,10,0,0)
        _,trace_b=kg.episode(b,10,0,0)
        self.assertEqual([(x['method'],x['world'],x['graph']) for x in trace_a[:8]],
                         [(x['method'],x['world'],x['graph']) for x in trace_b[:8]])

    def test_frozen_archive_hash_check(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            matrix = Path(temp) / "matrix.csv"
            terminal = Path(temp) / "episodes.csv"
            matrix.write_text("this is not the frozen matrix\n")
            terminal.write_text("this is not the frozen terminal archive\n")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                kg.load_frozen_matrix(matrix)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                kg.load_frozen_episodes(terminal)

    def test_malformed_inputs_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'frozen evaluation budget'):
            kg.episode(np.ones((7,12)),11,0,0)
        with self.assertRaisesRegex(ValueError,'requires verified 7x12'):
            kg.episode(np.ones((7,11)),10,0,0)
        with self.assertRaisesRegex(ValueError,'Nonfinite'):
            kg.scores_from_posterior([.1,math.nan],np.zeros((2,8,8)),[(0,0,0)])


if __name__=='__main__':unittest.main()
