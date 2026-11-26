"""Report saved-only processing failures without replaying Native capture."""
import argparse
import json
from pathlib import Path

from rail_left import CASES

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True)
    p.add_argument('--saved-output',type=Path,required=True)
    a=p.parse_args()
    suffix=a.case.removeprefix(ROOT.name+'__')
    if a.case!=ROOT.name+'__'+suffix or suffix not in {item.case_id for item in CASES}:
        raise ValueError('unknown exact rail case')
    versions=sorted(a.saved_output.glob('v[0-9][0-9][0-9][0-9]'))
    if not versions:
        raise ValueError('no saved processing version for exact case')
    version=versions[-1]
    feedback=version/'feedback.json'
    if feedback.is_file():
        value=json.loads(feedback.read_text())
        value['case_id']=a.case
        value['native_replay_requested']=False
        print(json.dumps(value,sort_keys=True))
    else:
        processing=version/'processing.json'
        if not processing.is_file():
            raise ValueError('saved version lacks receipt or actionable feedback')
        value=json.loads(processing.read_text())
        print(json.dumps({'case_id':a.case,'saved_processing_passed':value.get('passed'),
                          'missing_evidence':value.get('missing_evidence'),
                          'remaining':value.get('remaining',[]),
                          'native_replay_requested':False},sort_keys=True))


if __name__=='__main__':
    main()
