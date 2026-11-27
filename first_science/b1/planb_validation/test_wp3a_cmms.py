#!/usr/bin/env python3
"""WP3a tests: synthetic-only policy evaluation, optional read-only input gate."""
import unittest
from pathlib import Path
import numpy as np
from wp3a_policy_core import (Catalogue,Gaussian,History,POLICIES,NESTED,
                              streams,select_action,trajectory,kg_scores)
from wp3a_cmms_replay import CAT,BASE,BUDGETS,SCENARIOS,expected_counts
from wp3a_cmms_analysis import variance_components,interval,boot

import b1_budget_comparison_v1 as old
import b1_kg_one_step_v1 as oldkg
import b1_condition_selection_controlled_v1 as oldctl
from extend_b1_original_nine_policy_budgets_v1 import balanced_score_full_catalog


def make_history(model,seen):
    h=History(model)
    for a,c,v in seen:
        h.reveal(a,c,v)
    return h


def legacy_streams(seed):
    return tuple(np.random.default_rng(np.random.SeedSequence([seed,j])) for j in (0,33,44))


def legacy_action(p,seen,B,rngs):
    joint,arm,cell=rngs
    if p=="kg_one_step":
        return oldkg.select_kg(seen,joint,7)
    if p in ("random","balanced","informed","budgeted_top2"):
        # Original B=80 full-catalogue Balanced shape correction.
        saved=old.balanced_score
        try:
            old.balanced_score=balanced_score_full_catalog
            return old.select_action(p,seen,B,joint,7)
        finally:
            old.balanced_score=saved
    family="kg" if p.startswith("kg_") else "top2"
    arms,conditional,remaining=oldctl.acquisition(seen,family,B,old,oldkg)
    a=oldctl.pick(arms,arm)
    cs=remaining[a]
    c=cs[oldctl.pick(conditional[a],cell)] if p.endswith("_adaptive") else int(cell.choice(cs))
    return a,c


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.model=Gaussian(CAT,BASE)
        self.rng=np.random.default_rng(108)
        self.y=self.rng.uniform(.05,.95,(6,20))

    def test_design(self):
        self.assertEqual(CAT.X.shape,(20,10))
        self.assertEqual(len(SCENARIOS),14)
        self.assertEqual(expected_counts(POLICIES),(46800,1242000,18000))
        self.assertAlmostEqual(self.model.kappa,.8896)
        self.assertEqual(BUDGETS,tuple(round(120*b/84) for b in (10,15,20,25,30,35,40,45,55,65,70,75,80)))

    def test_posteriors_and_finite_targets(self):
        for params in SCENARIOS.values():
            coeff=Gaussian(CAT,params)
            cov=Gaussian(CAT,params,"additive_cov")
            for n in (0,1,3,7,13,19,20):
                observed=np.sort(self.rng.choice(20,n,replace=False))
                mask=sum(1<<int(c) for c in observed)
                v=self.y[0]
                m,f,q,g=coeff.moments(mask,v)
                ref=cov.moments(mask,v)
                np.testing.assert_allclose([m,f,q],ref[:3],rtol=0,atol=1e-12)
                np.testing.assert_allclose(g,ref[3],rtol=0,atol=1e-12)
                self.assertAlmostEqual(f,coeff.m0+coeff.scale*(m-coeff.m0),places=11)
                if n==20:
                    self.assertAlmostEqual(f,float(v.mean()),places=12)
        for structure in ("additive","independent","exchangeable","interaction25"):
            model=Gaussian(CAT,BASE,structure)
            self.assertGreaterEqual(float(np.linalg.eigvalsh(model.K).min()),-1e-12)
            np.testing.assert_allclose(np.diag(model.K),np.diag(self.model.K),rtol=0,atol=1e-12)
            if structure=="exchangeable":
                self.assertAlmostEqual(model.K.mean(),self.model.K.mean(),places=12)
            h=make_history(model,[(a,c,float(self.y[a,c])) for a in range(6) for c in (0,2,7)])
            np.testing.assert_allclose(h.finite,model.m0+model.scale*(h.mu-model.m0),rtol=0,atol=1e-12)
            np.testing.assert_allclose(kg_scores(h.finite,h.gain*model.scale**2),
                                       model.scale*kg_scores(h.mu,h.gain),rtol=0,atol=1e-12)

    def test_legacy_regression_all_nine(self):
        cat=Catalogue(old.METHODS,old.WORLDS,old.GRAPHS)
        model=Gaussian(cat,(.12,.07,.045,.055,.17))
        y=self.rng.uniform(.01,.5,(7,12))
        for n in (7,9,16,30,42,61,79,83):
            initial=[(a,0) for a in range(7)]
            remaining=[(a,c) for a in range(7) for c in range(1,12)]
            extra=self.rng.choice(len(remaining),n-7,replace=False)
            pairs=initial+[remaining[int(i)] for i in extra]
            seen=[(a,c,float(y[a,c])) for a,c in pairs]
            h=make_history(model,seen)
            mu,q,cov=old.posterior(seen,7)
            np.testing.assert_allclose(h.mu,mu,rtol=0,atol=1e-12)
            np.testing.assert_allclose(h.q,q,rtol=0,atol=1e-12)
            for a,c in zip(*np.where(h.available)):
                x=old.XX[c]; gain=float(old.V@cov[a]@x)**2/(old.NOISE**2+float(x@cov[a]@x))
                self.assertAlmostEqual(h.gain[a,c],gain,places=12)
                d=abs(mu[a]-min(mu[b] for b in range(7) if b!=a))
                self.assertAlmostEqual(kg_scores(h.mu,h.gain)[a,c],oldkg.kg_gain(d,np.sqrt(gain)),places=12)
            for B in (max(n+1,20),84):
                if B>84:
                    continue
                for p in POLICIES:
                    with self.subTest(history=n,budget=B,policy=p):
                        a=legacy_action(p,seen,B,legacy_streams(91))
                        b=select_action(p,h,B,legacy_streams(91))
                        self.assertEqual(a,b)

    def test_exhaustion_and_no_repeats(self):
        # Both best leaders exhausted; test joint and controlled fallbacks,
        # then a catalogue with only one remaining action.
        y=np.tile(np.linspace(.1,.9,6)[:,None],(1,20))
        seen=[(a,c,float(y[a,c])) for a in range(6) for c in (range(20) if a<2 else range(4))]
        h=make_history(self.model,seen)
        self.assertEqual(set(np.argsort(h.mu)[:2]),{0,1})
        for p in POLICIES:
            a,c=select_action(p,h,70,streams(p,0,0,70))
            self.assertGreaterEqual(a,2)
            self.assertTrue(h.available[a,c])
        seen=[(a,c,float(y[a,c])) for a in range(6) for c in range(20) if (a,c)!=(2,7)]
        h=make_history(self.model,seen)
        for p in POLICIES:
            self.assertEqual(select_action(p,h,120,streams(p,0,0,120)),(2,7))
        h.reveal(2,7,float(y[2,7]))
        with self.assertRaises(ValueError):
            h.reveal(2,7,float(y[2,7]))
        with self.assertRaises(ValueError):
            select_action("random",h,None,streams("random",0,0))

    def test_nested_prefix_and_seed(self):
        for p in NESTED:
            path,rows=trajectory(self.y,self.model,p,3,2,(14,21,29))
            short,rshort=trajectory(self.y,self.model,p,3,2,(14,21))
            self.assertEqual(short,path[:21])
            self.assertEqual(rshort,rows[:2])
            self.assertEqual((path,rows),trajectory(self.y,self.model,p,3,2,(14,21,29)))
            self.assertEqual(len(set(path)),len(path))
        for p in POLICIES[6:]:
            path,rows=trajectory(self.y,self.model,p,3,2,(29,))
            self.assertEqual((path,rows),trajectory(self.y,self.model,p,3,2,(29,)))
            self.assertEqual(len(set(path)),29)
        self.assertNotEqual(streams(POLICIES[4],0,0)[1].random(),streams(POLICIES[5],0,0)[1].random())

    def test_hidden_outcomes_do_not_affect_initial_action(self):
        other=1-self.y
        other[:,2]=self.y[:,2] # same initialization; all other losses changed
        for p in POLICIES:
            path,_=trajectory(self.y,self.model,p,2,5,(7,))
            changed,_=trajectory(other,self.model,p,2,5,(7,))
            self.assertEqual(path,changed)
        # Also arbitrary longer revealed history, not just initialization.
        observed=[(a,c) for a in range(6) for c in (0,4,8)]
        modified=1-self.y
        for a,c in observed:
            modified[a,c]=self.y[a,c]
        h=make_history(self.model,[(a,c,float(self.y[a,c])) for a,c in observed])
        g=make_history(self.model,[(a,c,float(modified[a,c])) for a,c in observed])
        for p in POLICIES:
            self.assertEqual(select_action(p,h,29,streams(p,0,0,29)),
                             select_action(p,g,29,streams(p,0,0,29)))

    def test_full_catalogue_boundary(self):
        h=make_history(self.model,[(a,c,float(self.y[a,c])) for a in range(6) for c in range(20)])
        np.testing.assert_allclose(h.finite,self.y.mean(axis=1),rtol=0,atol=1e-12)
        self.assertEqual(int(np.argmin(h.mu)),int(np.argmin(self.y.mean(axis=1))))


class InferenceTests(unittest.TestCase):
    def test_variance_nested_dependence(self):
        x=np.tile(np.arange(20,dtype=float)[None,None,:],(3,20,1))
        v=variance_components(x,True).sum()
        w=variance_components(x,False).sum()
        self.assertAlmostEqual(v,3*w)
        self.assertEqual(interval(0.,np.zeros(20)),(0.,0.,0.,None))
        lo,hi,se,df=interval(0.,variance_components(x,True))
        self.assertAlmostEqual(lo,-hi)
        self.assertGreater(se,0.)
        self.assertAlmostEqual(df,380.)
        # Nested draws must equal draws on the trajectory average.
        d=boot(x,True,100,np.random.default_rng(2))
        e=boot(x[:1],True,100,np.random.default_rng(2))
        np.testing.assert_array_equal(d,e)


if __name__=="__main__":
    unittest.main()
