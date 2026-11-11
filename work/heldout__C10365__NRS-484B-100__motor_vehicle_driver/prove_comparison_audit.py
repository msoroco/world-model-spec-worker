"""Run source-bound officer response and indication-window comparisons."""
import argparse
import json
import tempfile
from pathlib import Path

from officer_comparison_audit import audit as audit_response
from officer_response import measure
from officer_sweep_comparison_audit import audit as audit_sweep


def run(comparison, attempts, negative=False):
    if comparison == 'stop_response_window':
        if len(attempts) != 3:
            raise ValueError('Three exact sweep points required')
        if negative:
            # A missing member proves that the independent comparison rejects
            # an incomplete fixed-condition join without touching originals.
            return audit_sweep(attempts[:-1])
        return audit_sweep(attempts)
    if comparison not in ('stop_response', 'proceed_response') or len(attempts) != 2:
        raise ValueError('Unknown or incomplete response comparison')
    command = comparison.split('_')[0]
    with tempfile.TemporaryDirectory(prefix='officer-comparison-') as directory:
        files = []
        contexts = []
        for index, attempt in enumerate(map(Path, attempts)):
            context = json.loads((attempt / 'officer_context.json').read_text())
            observed = measure(attempt / 'officer_context.json', attempt / 'officer_direction.json',
                               attempt / 'subject_motion.json', expected_actor='motor_vehicle_driver',
                               expected_command=command)
            if negative and index == 1:
                observed['officer_id'] = 'changed-officer'
            target = Path(directory) / f'{index}.json'
            target.write_text(json.dumps(observed) + '\n')
            files.append(target)
            contexts.append(context)
        if contexts[0]['officer_id'] != contexts[1]['officer_id'] or contexts[0]['subject_id'] != contexts[1]['subject_id']:
            raise ValueError('Original officer or subject changed')
        result = audit_response(files, expected_actor='motor_vehicle_driver', expected_command=command,
                                fixed_subject_id=contexts[0]['subject_id'],
                                fixed_officer_id=contexts[0]['officer_id'])
        return dict(result, comparison_id=comparison)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempts', nargs='+', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.comparison, args.attempts, args.negative), indent=2))


if __name__ == '__main__':
    main()
