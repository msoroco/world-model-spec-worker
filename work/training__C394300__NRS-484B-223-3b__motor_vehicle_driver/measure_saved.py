"""Saved source-bound distance analysis draft; no delivery result or verdict."""
import argparse
import hashlib
import json
from pathlib import Path
from measure_center_lane import measure


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_entry_to_turn(attempt):
    attempt=Path(attempt)
    value=measure(attempt/'native_samples.jsonl',attempt/'road_geometry.json')
    return {'value':value,'method':'measure_entry_to_turn',
            'sources':{name:sha(attempt/name) for name in ('native_samples.jsonl','road_geometry.json')}}


def run(attempt,output):
    output=Path(output)
    if output.exists():raise ValueError('Retain prior analysis; choose a fresh output')
    attempt=Path(attempt)
    result={'format':'c394300-3b-saved-measurement-draft-v1',
            'measurements':{'center_lane_entry_to_turn_distance':measure_entry_to_turn(attempt)},
            'scope':'synthetic source-bound measurement only; no Core processing, Native physical or legal verdict'}
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(run(args.attempt,args.output)))
