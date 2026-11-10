#!/usr/bin/env python3
"""Synthetic mathematical test: two-method KG lookahead symmetry and its limits.

Not historical B1 evidence. Independent Gaussian posterior means; sampling any
method once updates its posterior mean by s_a * N(0,1). Second choice adaptive.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from numpy.polynomial.hermite import hermgauss


def kg1(means, stds, arm):
    gap = abs(means[arm] - min(means[j] for j in range(len(means)) if j != arm))
    s = float(stds[arm])
    if s == 0.:
        return 0.
    z = gap/s
    return max(0., s*math.exp(-z*z/2)/math.sqrt(2*math.pi)
               - .5*gap*math.erfc(z/math.sqrt(2)))


def continuation(means, stds, first, z):
    updated = list(means)
    updated[first] += stds[first]*z
    return max(kg1(updated,stds,j) for j in range(len(means)) if j!=first)


def q2_gauss_hermite(means, stds, first, order):
    nodes, weights = hermgauss(order)
    continuation_value = math.fsum(
        float(w)*continuation(means,stds,first,math.sqrt(2)*float(z))
        for z,w in zip(nodes,weights))/math.sqrt(math.pi)
    return kg1(means,stds,first)+continuation_value


def q2_quad(means, stds, first):
    def f(z):
        return (math.exp(-z*z/2)/math.sqrt(2*math.pi)
                *continuation(means,stds,first,z))
    total, error = 0., 0.
    cuts = (-9.,-4.,-2.,0.,2.,4.,9.)
    for left,right in zip(cuts[:-1],cuts[1:]):
        val,err = quad(f,left,right,epsabs=2e-12,epsrel=1e-10,limit=250)
        total += val
        error += err
    return kg1(means,stds,first)+total,error


def test():
    cases = (
        ("two_methods", [0.,.2], [.12,.12]),
        ("third_equal_uncertainty", [0.,.2,.4], [.12,.12,.12]),
        ("third_higher_uncertainty", [0.,.2,.4], [.12,.12,.20]),
    )
    rows = []
    for name,means,stds in cases:
        gains = [kg1(means,stds,i) for i in range(len(means))]
        integral = [q2_quad(means,stds,i) for i in (0,1)]
        gh61 = [q2_gauss_hermite(means,stds,i,61) for i in (0,1)]
        gh121 = [q2_gauss_hermite(means,stds,i,121) for i in (0,1)]
        row = dict(case=name,mean_values=str(means),update_std=str(stds),
                   kg1_first=gains[0],kg1_second=gains[1],
                   kg1_third=(gains[2] if len(gains)>2 else ""),
                   kg2_first=integral[0][0],kg2_second=integral[1][0],
                   kg2_first_minus_second=integral[0][0]-integral[1][0],
                   quad_error_sum=integral[0][1]+integral[1][1],
                   gh61_difference=gh61[0]-gh61[1],
                   gh121_difference=gh121[0]-gh121[1])
        rows.append(row)
        print("CASE",name,"KG1",gains,"KG2 difference",
              row["kg2_first_minus_second"],"quad_error_sum",
              row["quad_error_sum"],flush=True)
    if abs(rows[0]["kg2_first_minus_second"])>1e-8:
        raise AssertionError("Two-method equivalence unexpectedly fails")
    if abs(rows[1]["kg2_first_minus_second"])>1e-8:
        raise AssertionError("Equal-third control unexpectedly asymmetric")
    counterexample=rows[2]
    if not (counterexample["kg1_first"]==counterexample["kg1_second"] and
            counterexample["kg1_first"]>counterexample["kg1_third"]):
        raise AssertionError("Counterexample must exhibit top-two KG1 tie")
    if abs(counterexample["kg2_first_minus_second"])<1e-4:
        raise AssertionError("Counterexample must exhibit two-step separation")
    if abs(counterexample["kg2_first_minus_second"])<100*counterexample["quad_error_sum"]:
        raise AssertionError("Counterexample numerically inconclusive")
    print("KG_THEORY_CHECK_PASS")
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,help="Optional new output directory")
    args=p.parse_args()
    rows=test()
    if args.out is not None:
        out=args.out.expanduser().resolve()
        if out.exists():
            raise FileExistsError(f"Refusing overwrite: {out}")
        out.mkdir(parents=True)
        with (out/"synthetic_counterexample.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        (out/"manifest.json").write_text(json.dumps({
            "status":"SYNTHETIC_MATHEMATICAL_CHECK_NOT_B1_EVIDENCE",
            "cases":len(rows),
            "model":"independent Gaussian method means; one evaluation per method",
            "method":"adaptive two-step expectation integrated with SciPy quad"
        },indent=2)+"\n")


if __name__=="__main__":
    main()
