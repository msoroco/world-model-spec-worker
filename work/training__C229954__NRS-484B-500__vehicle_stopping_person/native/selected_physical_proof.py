"""CPU source-shaped physical triad; does not contact Native CARLA."""

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from physical_check import assess, motion
from prove_designated_stop import packet


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def result(kind, status, observation, sources):
    return {'format': 'worker-designated-stop-physical-fixture-result',
            'kind': kind, 'physical_checks': {'maneuver': {
                'status': status,
                'method': 'source-bound sampled approach and continuous rest',
                'sources': sources,
                'details': observation,
                'engineering_tolerances_not_legal': True}},
            'maneuver_completed': status == 'met',
            'realized_observables': observation if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True,
            'legal_verdict_claimed': False}


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='c229954-selected-physical-',
                                     dir='.runtime-work') as temp:
        original = packet(Path(temp) / 'original', True)
        for index, row in enumerate(original['rows']):
            row['position_m'] = [5 + min(index, 100) * 0.05, 0, 0]
        path = Path(original['sources']['native_trace']['path'])
        path.write_text(json.dumps(original['rows'], separators=(',', ':')) + '\n')
        original['sources']['native_trace']['sha256'] = sha(path)
        positive = assess(original)
        assert positive['status'] == 'met'
        good_sources = positive['source_hashes']
        incomplete_rows = copy.deepcopy(original['rows'])
        for row in incomplete_rows:
            row['position_m'] = [5, 0, 0]
        incomplete_path = Path(temp) / 'incomplete-motion.json'
        incomplete_path.write_text(json.dumps(incomplete_rows) + '\n')
        incomplete = motion(incomplete_rows)
        assert not incomplete['approach_observed']
        missing_rows = copy.deepcopy(original['rows'])
        missing_rows[200].pop('position_m')
        missing_path = Path(temp) / 'missing-position.json'
        missing_path.write_text(json.dumps(missing_rows) + '\n')
        try:
            motion(missing_rows)
        except ValueError as error:
            assert 'position missing' in str(error)
            missing = {'error': str(error)}
        else:
            raise AssertionError('Missing position passed')
        outcomes = {
            'complete_motion': result('complete_motion', 'met',
                                      positive['observation'], good_sources),
            'incomplete_motion': result('incomplete_motion', 'not_met',
                                        incomplete, good_sources | {'motion_fixture': sha(incomplete_path)}),
            'missing_evidence': result('missing_evidence', 'unverified',
                                       missing, good_sources | {'motion_fixture': sha(missing_path)})}
        for kind, value in outcomes.items():
            (output / (kind + '.json')).write_text(json.dumps(value, indent=2,
                                                      sort_keys=True) + '\n')
        print(json.dumps({'format': 'c229954-selected-physical-cpu-proof',
                          'statuses': {key: value['physical_checks']['maneuver']['status']
                                       for key, value in outcomes.items()},
                          'synthetic_only': True}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.output)
