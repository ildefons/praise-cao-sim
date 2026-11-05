#!/usr/bin/env python3
"""Validate the 84-entry PRAISE B1 archive and export the canonical 7x12 matrix.

This stage does not run comparisons or simulate anything. It fails closed if a
frozen metrics file or its provenance hash is absent/inconsistent.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import b1_budget_comparison_v1 as b1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--out',type=Path,
        default=Path.home()/'praise/planb_b1_fixed_budget_v1')
    args=p.parse_args()
    Y,checked=b1.build_matrix(args.repo.resolve())
    args.out.mkdir(parents=True,exist_ok=True)
    target=args.out/'seven_method_matrix.csv'
    rows=[{'method':b1.METHODS[a],'world':w,'graph':g,'mae':float(Y[a,c])}
          for a in range(7) for c,(w,g) in enumerate(b1.CELLS)]
    b1.write_csv(target,rows,['method','world','graph','mae'])
    manifest={'status':'B1_SEVEN_METHOD_MATRIX_VERIFIED_V1',
        'n_algorithms':7,'n_cells':12,'n_actions':84,
        'primary_score':'MAE over 555 related query-horizon values per physical cell',
        'methods':b1.METHODS,'cells':b1.CELLS,'source_evidence':checked,
        'canonical_matrix_sha256':b1.digest(target),
        'limits':['Historical post-result evidence, not independent validation',
                  '12 cells / 3 independent provider worlds; query points correlated',
                  'MAE point estimates reuse finite original white-box reference']}
    (args.out/'matrix_provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('SEVEN_METHOD_MATRIX_VERIFIED 7 methods x 12 cells = 84 atomic evaluations')
    for name,mae in zip(b1.METHODS,Y.mean(axis=1)):
        print(f'  {name}: {mae:.6f}')
    print('MATRIX_FILE',target.resolve())
    print('MATRIX_SHA256',b1.digest(target))


if __name__=='__main__':main()
