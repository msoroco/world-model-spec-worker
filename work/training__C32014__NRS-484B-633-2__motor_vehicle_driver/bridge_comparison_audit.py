"""Independent CPU comparison of source-shaped bridge attempts.

This checks original-sample joins and the intended physical contrast. It does
not establish Department authority, rendered signs, or a legal conclusion.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from measure import measure


def audit(below_dir, above_dir):
    folders = [Path(below_dir), Path(above_dir)]
    contexts = [json.loads((folder / 'bridge-context.json').read_text()) for folder in folders]
    histories = [folder / 'bridge-speed-history.jsonl' for folder in folders]
    results = [measure(history, folder / 'bridge-context.json')
               for history, folder in zip(histories, folders)]
    for key in ('bridge_x_m', 'sign_limit_mph', 'posting_distance_m',
                'native_bridge_survey', 'native_sign_survey'):
        if any(key not in context for context in contexts):
            raise ValueError('fixed bridge/sign context missing: ' + key)
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('fixed bridge/sign context differs: ' + key)
    if any(result['frames'] != 600 for result in results):
        raise ValueError('original 600-frame comparison missing')
    if results[0]['on_structure_samples_above_posted_maximum'] != 0:
        raise ValueError('below-posting attempt exceeded authored maximum')
    if results[1]['on_structure_samples_above_posted_maximum'] <= 0:
        raise ValueError('above-posting attempt did not exceed authored maximum')
    if results[1]['maximum_on_structure_mph'] <= results[0]['maximum_on_structure_mph']:
        raise ValueError('measured on-structure speed contrast missing')
    return {'passed': True, 'physical_acceptance_claimed': False,
            'department_determination_verified': False,
            'below': results[0], 'above': results[1]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--below', required=True)
    parser.add_argument('--above', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.below, args.above), sort_keys=True))
