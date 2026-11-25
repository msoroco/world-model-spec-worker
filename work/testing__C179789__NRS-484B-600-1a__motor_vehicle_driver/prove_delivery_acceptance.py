"""CPU proof that the exact-case physical auditor rejects changed originals."""
import argparse
import json
import tempfile
from pathlib import Path

from delivery_acceptance import CASES, CHECKS, sha, verify_physical


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    if args.case not in CASES or len(CHECKS) != 6:
        raise ValueError('Acceptance case/check inventory differs')
    root = Path(__file__).resolve().parent
    entry = next(row for row in json.loads((root / 'execution-manifest.json').read_text())['cases']
                 if row['case_id'] == args.case)
    if sha(root / entry['construction']) != entry['construction_sha256']:
        raise ValueError('Exact primary construction changed')
    with tempfile.TemporaryDirectory(prefix='c179789-acceptance-') as temporary:
        attempt = Path(temporary)
        source = attempt / 'condition_history.jsonl'
        source.write_text('{"diagnostic":true}\n')
        check = {'status': 'met', 'method': 'source-bound diagnostic check',
                 'sources': {'condition_history.jsonl': sha(source)}}
        result = {'physical_acceptance_claimed': False, 'setup_confirmed': True,
                  'behavior_attempted': True, 'maneuver_completed': True,
                  'physical_checks': {key: check for key in ('setup', 'target', 'maneuver')}}
        verify_physical(result, attempt)
        if args.mode == 'negative':
            source.write_text('{"changed":true}\n')
            verify_physical(result, attempt)
            raise AssertionError('Changed source incorrectly accepted')
    print(json.dumps({'case_id': args.case, 'mode': args.mode,
                      'auditor_checks': CHECKS, 'diagnostic_only': True,
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
