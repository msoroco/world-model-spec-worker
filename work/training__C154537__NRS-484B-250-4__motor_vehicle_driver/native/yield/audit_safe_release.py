"""Compare early entry with a held release against the same occupied crossing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from assess_statutory import assess


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    requests = {}
    facts = {}
    source_hashes = {}
    for suffix in ('controlled_6', 'controlled_7'):
        request_path = HERE / f'request-{suffix}.jsonl'
        survey_path = HERE / 'diagnostic' / suffix / 'scene-survey.json'
        motion_path = HERE / 'diagnostic' / suffix / 'native-motion.jsonl'
        request = rows(request_path)
        motion = rows(motion_path)
        if len(request) != 600 or len(motion) != 600:
            raise ValueError('Full request and original-shaped motion required')
        if any(m['ego_center_x_m'] != r['ego_center_xy_m'][0] or
               m['other']['center_xyz_m'][1] != r['other_center_xy_m'][1]
               for r, m in zip(request, motion)):
            raise ValueError('Saved ego or other motion differs from request')
        survey = json.loads(survey_path.read_text())
        requests[suffix] = request
        facts[suffix] = assess(survey, motion)
        source_hashes[suffix] = {'request': sha(request_path),
                                 'survey': sha(survey_path), 'motion': sha(motion_path)}
    early, held = requests['controlled_6'], requests['controlled_7']
    fixed = ('frame', 'time_s', 'other_center_xy_m', 'requested_signal_state',
             'requested_stop_line_present', 'requested_near_side_crosswalk_present',
             'requested_view_reference_center_x_m', 'intersection_entry_front_x_m',
             'source_kind', 'native_observed', 'legal_verdict')
    for a, b in zip(early, held):
        if any(a.get(key) != b.get(key) for key in fixed):
            raise ValueError('Crossing actor, signal, or stopping context differs')
        if a['frame'] <= 220 and a['ego_center_xy_m'] != b['ego_center_xy_m']:
            raise ValueError('Approach and complete-stop plateau differ')
    first, second = facts['controlled_6'], facts['controlled_7']
    if not first['other_within_intersection_at_ego_entry'] or \
            second['other_within_intersection_at_ego_entry'] or \
            first['ego_entry_frame'] != 225 or second['ego_entry_frame'] != 305 or \
            first['other_stopped_before_ego'] or second['other_stopped_before_ego']:
        raise ValueError('Early and held yielding facts differ from contrast')
    bad = json.loads(json.dumps(held))
    bad[250]['other_center_xy_m'][1] += 1
    if all(a['other_center_xy_m'] == b['other_center_xy_m'] for a, b in zip(early, bad)):
        raise AssertionError('Changed crossing actor accepted')
    return {'format': 'c154537-safe-release-cpu-audit-v1', 'passed': True,
            'source_hashes': source_hashes,
            'early_ego_entry_frame': first['ego_entry_frame'],
            'held_ego_entry_frame': second['ego_entry_frame'],
            'early_other_inside': True, 'held_other_inside': False,
            'changed_other_rejected': True, 'synthetic_source_shapes_only': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain prior audit')
    args.output.write_text(json.dumps(audit(), indent=2) + '\n')
