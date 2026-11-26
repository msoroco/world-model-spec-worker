"""CPU protocol proof for each fixed/difference rail comparison."""
import argparse
import json
from pathlib import Path

from comparison_audit import COMPARISONS, audit_pair

ROOT=Path(__file__).resolve().parent
SCRATCH=ROOT.parents[1]/'.runtime-work/c204980-owner-nov26'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--comparison',required=True,choices=sorted(COMPARISONS))
    p.add_argument('--negative',action='store_true')
    a=p.parse_args()
    cases=COMPARISONS[a.comparison]['case_ids']
    attempts={case:SCRATCH/(f'compat-{case.removeprefix(ROOT.name+"__")}-primary-v3')
              for case in cases}
    if cases[0].endswith('__left_101ft'):
        attempts[cases[0]]=SCRATCH/'compat-left101-primary-v3'
    if a.negative:
        attempts[cases[0]],attempts[cases[1]]=attempts[cases[1]],attempts[cases[0]]
        try:
            audit_pair(a.comparison,attempts,diagnostic_protocol=True)
        except ValueError as error:
            print('EXPECTED REJECTION: '+str(error))
            return 1
        raise AssertionError('swapped original case identities accepted')
    result=audit_pair(a.comparison,attempts,diagnostic_protocol=True)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    raise SystemExit(main())
