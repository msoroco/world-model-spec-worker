"""CPU source audit protocol proof; synthetic footage is never delivery accepted."""
import argparse
import json
from pathlib import Path

from delivery_audit import inspect_original
from rail_left import CASES

ROOT=Path(__file__).resolve().parent
SCRATCH=ROOT.parents[1]/'.runtime-work/c204980-owner-nov26'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True)
    p.add_argument('--negative',action='store_true')
    a=p.parse_args()
    suffix=a.case.removeprefix(ROOT.name+'__')
    if a.case!=ROOT.name+'__'+suffix or suffix not in {case.case_id for case in CASES}:
        raise ValueError('unknown exact rail case')
    attempt=SCRATCH/f'compat-{suffix}-primary-v3'
    if suffix=='left_101ft':
        attempt=SCRATCH/'compat-left101-primary-v3'
    if a.negative:
        try:
            inspect_original(attempt,a.case+'__tampered',diagnostic_protocol=True)
        except ValueError as error:
            print('EXPECTED REJECTION: '+str(error))
            return 1
        raise AssertionError('changed exact case identity accepted')
    receipt=inspect_original(attempt,a.case,diagnostic_protocol=True)
    print(json.dumps({'case_id':a.case,'protocol_passed':True,
                      'source_manifest_sha256':receipt['source_manifest_sha256'],
                      'frames':receipt['frame_count'],'diagnostic_fixture':True,
                      'physical_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    raise SystemExit(main())
