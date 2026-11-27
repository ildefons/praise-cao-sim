#!/usr/bin/env python3
"""WP3a dimension-generic finite-catalogue posterior and acquisition rules.

No reference data, filesystem access or RNG creation in selectors. The evaluator
owns the reference; a policy sees only a History and a working Gaussian model.
"""
from functools import lru_cache
import numpy as np
from scipy.special import ndtr

POLICIES = ("random", "balanced", "informed", "kg_one_step",
            "kg_two_stage_adaptive", "kg_two_stage_uniform", "budgeted_top2",
            "top2_two_stage_adaptive", "top2_two_stage_uniform")
NESTED = POLICIES[:6]
TOL = 1e-12


class Catalogue:
    def __init__(self, methods, h, s):
        self.methods, self.h, self.s = tuple(methods), tuple(h), tuple(s)
        self.A, self.C = len(methods), len(h)*len(s)
        if self.A < 2 or not self.C or any(len(set(x)) != len(x) for x in (methods,h,s)):
            raise ValueError("Invalid catalogue")
        self.cells = tuple((w,g) for w in h for g in s)
        self.hid = np.repeat(np.arange(len(h)), len(s))
        self.sid = np.tile(np.arange(len(s)), len(h))
        self.X = np.column_stack((np.ones(self.C), np.eye(len(h))[self.hid],
                                  np.eye(len(s))[self.sid]))
        self.v = self.X.mean(axis=0)


class Gaussian:
    """Cache history-independent linear posterior maps by observed-condition mask.

    Parameters are SDs followed by intercept mean. Additive uses coefficient
    algebra; the equivalent covariance implementation is an independent check.
    Other models are the frozen structural controls.
    """
    def __init__(self, cat, params, structure="additive", cache_size=16384):
        self.cat, self.params, self.structure = cat, tuple(params), structure
        a,h,s,self.noise,self.m0 = self.params
        if min(a,h,s,self.noise) <= 0 or not 0 <= self.m0 <= 1:
            raise ValueError("Invalid Gaussian parameters")
        self.var = np.array([a*a]+[h*h]*len(cat.h)+[s*s]*len(cat.s))
        X = cat.X
        K = (X*self.var) @ X.T
        D = np.diag(np.diag(K))
        if structure == "independent":
            K = D
        elif structure == "interaction25":
            K = .75*K+.25*D
        elif structure == "exchangeable":
            r = (K.sum()-np.trace(K))/(cat.C*(cat.C-1))
            K = (K[0,0]-r)*np.eye(cat.C)+r*np.ones_like(K)
        elif structure not in ("additive", "additive_cov"):
            raise ValueError(structure)
        self.K = K
        self.kappa = float(K.sum(axis=1)[0])
        if self.kappa <= 0 or not np.allclose(K.sum(axis=1), self.kappa):
            raise ValueError("WP2 constant-row-sum contract failed")
        self.scale = 1+self.noise**2/self.kappa
        self.cached = lru_cache(maxsize=cache_size)(self._maps)

    def _maps(self, mask):
        c = self.cat
        O = np.array([i for i in range(c.C) if mask & (1<<i)], dtype=int)
        U = np.array([i for i in range(c.C) if not mask & (1<<i)], dtype=int)
        K, s2 = self.K, self.noise**2
        if self.structure == "additive":
            X, v = c.X, c.v
            xo = X[O]
            S = np.linalg.inv(np.diag(1/self.var)+xo.T@xo/s2)
            P = X@S@xo.T/s2
            q = float(v@S@v)
            gain = (v@S@X.T)**2/(s2+np.einsum("ij,jk,ik->i",X,S,X))
        else:
            if len(O):
                P = np.linalg.solve(K[np.ix_(O,O)]+s2*np.eye(len(O)), K[O,:]).T
                Q = K-P@K[O,:]
            else:
                P, Q = np.empty((c.C,0)), K
            q = float(Q.mean())
            gain = Q.mean(axis=0)**2/(s2+np.diag(Q))
        # Two separate linear maps for the latent and finite catalogue targets.
        w = P.mean(axis=0)
        wf = (1+P[U].sum(axis=0))/c.C
        return O,w,wf,max(0.,q),np.maximum(gain,0.)

    def moments(self, mask, values):
        O,w,wf,q,gain = self.cached(int(mask))
        centered = values[O]-self.m0
        return self.m0+float(w@centered), self.m0+float(wf@centered), q, gain


class History:
    """Only revealed outcomes are stored. No full-matrix reference."""
    def __init__(self, model):
        self.model, self.cat = model, model.cat
        A,C = self.cat.A,self.cat.C
        self.masks = [0]*A
        self.values = np.zeros((A,C))
        self.available = np.ones((A,C),dtype=bool)
        self.n = np.zeros(A,dtype=int)
        self.nh = np.zeros((A,len(self.cat.h)),dtype=int)
        self.ns = np.zeros((A,len(self.cat.s)),dtype=int)
        self.mu = np.empty(A); self.finite = np.empty(A); self.q = np.empty(A)
        self.gain = np.empty((A,C)); self.step = 0
        for a in range(A):
            self._update(a)

    def _update(self,a):
        self.mu[a],self.finite[a],self.q[a],self.gain[a] = self.model.moments(
            self.masks[a],self.values[a])

    def reveal(self,a,c,value):
        if not (0 <= a < self.cat.A and 0 <= c < self.cat.C and self.available[a,c]):
            raise ValueError("Invalid or repeated acquisition")
        if not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid revealed loss")
        self.available[a,c] = False
        self.values[a,c] = value
        self.masks[a] |= 1<<c
        self.n[a] += 1
        self.nh[a,self.cat.hid[c]] += 1
        self.ns[a,self.cat.sid[c]] += 1
        self.step += 1
        self._update(a)

    def balanced(self):
        return -100*self.n[:,None]-10*self.nh[:,self.cat.hid]-2*self.ns[:,self.cat.sid]


def kg_scores(mu,gain):
    d = np.abs(mu-np.min(np.where(np.eye(len(mu),dtype=bool),np.inf,mu[None,:]),axis=1))
    s = np.sqrt(np.maximum(gain,0))
    z = np.divide(d[:,None],s,out=np.zeros_like(s),where=s>0)
    return np.where(s>0,np.maximum(0.,s*np.exp(-.5*z*z)/np.sqrt(2*np.pi)-d[:,None]*ndtr(-z)),0.)


def pick(scores,rng):
    scores = np.asarray(scores)
    best = np.max(scores)
    if not np.isfinite(best):
        raise ValueError("No feasible action")
    return int(rng.choice(np.flatnonzero(scores.ravel()>=best-TOL)))


def select_action(policy, history, budget, streams):
    """Same nine rules as B1. Budget is ignored by all six nested policies."""
    h = history
    A,C = h.cat.A,h.cat.C
    avail = h.available
    joint,arm,cell = streams
    if not avail.any():
        raise ValueError("Catalogue exhausted")
    def joint_pick(scores,allowed=avail):
        return divmod(pick(np.where(allowed,scores,-np.inf),joint),C)
    if policy == "random":
        x = np.flatnonzero(avail.ravel())
        return divmod(int(x[joint.integers(len(x))]),C)
    if policy == "balanced":
        return joint_pick(h.balanced())
    if policy == "informed":
        gap = h.mu[:,None]-h.mu[None,:]
        v = np.maximum(1e-10,h.q[:,None]+h.q[None,:])
        weights = np.exp(-.5*gap**2/v)
        np.fill_diagonal(weights,0.)
        return joint_pick(h.gain*weights.sum(axis=1)[:,None])
    if policy == "kg_one_step":
        return joint_pick(kg_scores(h.mu,h.gain))
    if policy.startswith("top2_") or policy == "budgeted_top2":
        if budget is None or not A <= budget <= A*C:
            raise ValueError("Top2 requires precommitted budget")
        coverage = h.step < A+(budget-A+1)//2
        leaders = np.argsort(h.mu,kind="stable")[:2]
        shortlist = avail & np.isin(np.arange(A),leaders)[:,None]
        if policy == "budgeted_top2":
            return joint_pick(h.balanced()) if coverage or not shortlist.any() else joint_pick(h.gain,shortlist)
        if coverage:
            allowed = avail
            arms = -h.n.astype(float)
            cond = -10*h.nh[:,h.cat.hid]-2*h.ns[:,h.cat.sid]
        elif shortlist.any():
            allowed,cond = shortlist,h.gain
            arms = np.divide(np.where(allowed,cond,0).sum(axis=1),allowed.sum(axis=1),
                             out=np.full(A,-np.inf),where=allowed.any(axis=1))
        else:
            # Original controlled Top2 fallback, distinct from joint Balanced.
            allowed,arms,cond = avail,-h.n.astype(float),np.zeros((A,C))
    elif policy in ("kg_two_stage_adaptive","kg_two_stage_uniform"):
        allowed,cond = avail,kg_scores(h.mu,h.gain)
        arms = np.divide(np.where(allowed,cond,0).sum(axis=1),allowed.sum(axis=1),
                         out=np.full(A,-np.inf),where=allowed.any(axis=1))
    else:
        raise ValueError("Unknown policy "+policy)
    a = pick(np.where(allowed.any(axis=1),arms,-np.inf),arm)
    cs = np.flatnonzero(allowed[a])
    c = int(cs[pick(cond[a,cs],cell)]) if policy.endswith("_adaptive") else int(cell.choice(cs))
    return a,c


def streams(policy,start,rep,budget=None,root=20261127):
    base = [root,start,rep,POLICIES.index(policy)]
    if policy not in NESTED:
        if budget is None:
            raise ValueError("Budget required")
        base.append(budget)
    return tuple(np.random.default_rng(np.random.SeedSequence(base+[i])) for i in (0,33,44))


def score(h,truth):
    # Deterministic argmin for implementation; any true minimizer is correct.
    a = int(np.argmin(h.mu))
    gap = max(0.,float(truth[a]-min(truth)))
    return a,gap,int(gap<=TOL)


def trajectory(y,model,policy,start,rep,checkpoints,root=20261127):
    """Evaluator only: reveal selected cells, score after acquisition."""
    cat = model.cat
    if y.shape != (cat.A,cat.C) or not checkpoints or tuple(sorted(set(checkpoints)))!=tuple(checkpoints):
        raise ValueError("Invalid matrix or checkpoints")
    B = max(checkpoints)
    if min(checkpoints)<cat.A or B>cat.A*cat.C or (policy not in NESTED and len(checkpoints)!=1):
        raise ValueError("Invalid budget schedule")
    truth = y.mean(axis=1)
    rng = streams(policy,start,rep,B,root)
    h = History(model)
    path, rows = [],[]
    def reveal(a,c):
        h.reveal(a,c,float(y[a,c]))
        path.append(a*cat.C+c)
    def checkpoint():
        if h.step in checkpoints:
            a,r,correct = score(h,truth)
            rows.append((h.step,a,r,correct))
    for a in range(cat.A):
        reveal(a,start)
    checkpoint()
    while h.step<B:
        reveal(*select_action(policy,h,B if policy not in NESTED else None,rng))
        checkpoint()
    return path,rows
