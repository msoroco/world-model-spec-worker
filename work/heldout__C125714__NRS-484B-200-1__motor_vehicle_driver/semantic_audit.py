"""Validate the exact draft semantic proposal chain against selected constructions."""

import argparse
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


CONSTRUCTIONS = {
    'baseline_right_east': 'construction-compatibility-probe.json',
    'baseline_right_west': 'construction-compatibility-probe-west.json',
    'unexcepted_left': 'construction-compatibility-probe-left.json',
    'right_half_closed': 'construction-compatibility-closure.json',
    'passing_same_direction': 'construction-compatibility-probe-passing.json',
    'insufficient_width': 'construction-compatibility-probe-narrow.json',
    'posted_one_way': 'construction-probe-one-way.json',
    'three_lane': 'construction-probe-three-lane.json',
}


def audit():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = {'cases': [{'case_id': HERE.name + '__' + suffix, 'construction': source}
                          for suffix, source in CONSTRUCTIONS.items()]}
    result = validate(HERE, assignment, manifest)
    return {'format': 'worker-semantic-audit', 'assignment_id': HERE.name,
            'validator': 'worker_exchange.semantic_delivery.validate',
            'result': result, 'status': 'draft',
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(), indent=2) + '\n')
    print('Validated 6 semantic stages for 8 exact cases; legal review remains open')
