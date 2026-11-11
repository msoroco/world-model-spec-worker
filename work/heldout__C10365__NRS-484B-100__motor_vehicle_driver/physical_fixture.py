"""Source-shaped officer outcome fixtures; never actual Native findings."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from officer_response import measure

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, kind):
    manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact officer case')
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    slug = case.split('__')[-1]
    command = 'stop' if slug.startswith('stop_') else 'proceed'
    expected_response = ('no_observed_stop' if slug == 'stop_does_not_respond'
                         else 'no_observed_movement' if slug == 'proceed_does_not_respond'
                         else 'stopped_after_indication' if command == 'stop'
                         else 'moved_after_indication')
    with tempfile.TemporaryDirectory(prefix='officer-physical-', dir=REPO / '.runtime-work') as temporary:
        attempt = Path(temporary) / 'fixture'
        materialize(REPO, REPO / entry['fixture_recipe'], attempt)
        if kind == 'incomplete_motion':
            motion_path = attempt / 'subject_motion.json'
            motion = json.loads(motion_path.read_text())
            direction = json.loads((attempt / 'officer_direction.json').read_text())
            changed_speed = 2.0 if command == 'stop' else 0.0
            if slug.endswith('does_not_respond'):
                changed_speed = 0.0 if command == 'stop' else 2.0
            for row in motion['frames']:
                if row['frame'] > direction['frame']:
                    row['speed_mps'] = changed_speed
            motion_path.write_text(json.dumps(motion) + '\n')
            (attempt / 'subject_motion_history.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in motion['frames']))
        elif kind == 'missing_evidence':
            (attempt / 'officer_direction.json').unlink()
        source_names = ('officer_context.json', 'officer_direction.json',
                        'subject_motion.json', 'subject_motion_history.jsonl')
        sources = {name: sha(attempt / name) for name in source_names if (attempt / name).is_file()}
        observed = None
        try:
            observed = measure(attempt / 'officer_context.json', attempt / 'officer_direction.json',
                               attempt / 'subject_motion.json',
                               expected_actor='motor_vehicle_driver', expected_command=command)
        except ValueError as error:
            if kind != 'missing_evidence' or 'missing required source' not in str(error):
                raise
        matches = observed is not None and observed['observed_response'] == expected_response
        status = 'unverified' if kind == 'missing_evidence' else 'met' if matches else 'not_met'
        expected_status = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                           'missing_evidence': 'unverified'}[kind]
        if status != expected_status:
            raise ValueError('Physical officer fixture outcome differs from original source')
        return {
            'case_id': case, 'fixture_kind': kind, 'fixture_only': True,
            'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_checks': {'maneuver': {
                'status': status,
                'method': 'Original-shaped timed indication and joined post-indication subject speed; synthetic fixture',
                'sources': sources,
                'missing_evidence': ['officer_direction.json'] if kind == 'missing_evidence' else [],
            }},
            'maneuver_completed': matches,
            'realized_observables': {'observed_response': observed['observed_response'],
                                     'post_indication_samples': observed['post_indication_samples']} if matches else {},
            'provenance_kind': 'native',
            'provenance_note': 'Native-shaped protocol fixture only; no actual officer authority, gesture pixels or lawful order',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'], 'synthetic fixture only')


if __name__ == '__main__':
    main()
