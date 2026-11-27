"""Synthetic physical progress and ownership-order CPU proof, not CARLA evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ORDER = ['capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started']
SOURCES = ('config.json', 'native-person-interaction.jsonl',
           'video_frames.jsonl', 'original-context-packet.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lifecycle(events):
    if events != ORDER:
        raise ValueError('saved processing precedes Native ownership closure')
    return True


def evaluate(attempt):
    root = Path(attempt)
    existing = {name: sha(root/name) for name in SOURCES if (root/name).is_file()}
    missing = sorted(set(SOURCES)-set(existing))
    if missing:
        status, reason, observables = 'unverified', 'required source missing', {}
    else:
        rows = [json.loads(line) for line in (root/'native-person-interaction.jsonl').read_text().splitlines()]
        mapping = [json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
        if len(rows) != 600 or len(mapping) != 600 or any(
                row.get('frame') != index or frame.get('video_frame') != index or
                row.get('native_frame') != frame.get('native_frame') or
                row.get('ego_actor_id') == row.get('person_actor_id')
                for index, (row, frame) in enumerate(zip(rows, mapping))):
            status, reason, observables = 'not_met', 'incomplete original actor/frame join', {}
        else:
            displacement = rows[-1]['ego_x_m']-rows[0]['ego_x_m']
            minimum_gap = min(abs(row['person_x_m']-row['ego_x_m']) for row in rows)
            goal = json.loads((root/'config.json').read_text())['physical_completion']['minimum_progress_m']
            met = displacement >= goal and minimum_gap < 3
            status, reason = ('met', 'synthetic progress and person-encounter criterion met') if met else (
                'not_met', 'synthetic progress or person encounter incomplete')
            observables = {'source_joined_frames': len(rows),
                           'forward_displacement_m': displacement,
                           'minimum_abs_person_longitudinal_gap_m': minimum_gap,
                           'engineering_progress_goal_m': goal,
                           'original_native_observed': False}
    case_id = json.loads((root/'config.json').read_text())['case_id']
    return {'case_id': case_id, 'diagnostic_fixture': True,
            'provenance_kind': 'synthetic_fixture', 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'source-joined full actor/frame progress and person-position check on controlled synthetic fixture',
                'sources': existing, 'missing_evidence': missing,
                'reason': reason}},
            'maneuver_completed': status == 'met',
            'realized_observables': observables}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + [ORDER[-1], ORDER[-2]])
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError('Premature saved processing accepted')
        print('PASS: capture ownership closure precedes saved processing')
    else:
        result = evaluate(args.attempt)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(result['case_id'], result['physical_checks']['maneuver']['status'])
