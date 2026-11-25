"""Independent requested-context and saved-history audit for yielding alternatives."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent
sys.path.insert(0, str(NATIVE))
from assess_statutory import assess

FIXED = ('frame', 'time_s', 'ego_center_xy_m', 'ego_front_x_m',
         'requested_signal_state', 'requested_stop_line_present',
         'requested_near_side_crosswalk_present', 'requested_view_reference_center_x_m',
         'intersection_entry_front_x_m', 'source_kind', 'native_observed',
         'legal_verdict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    base_path = NATIVE / 'request-controlled_1.jsonl'
    base = rows(base_path)
    if len(base) != 600:
        raise ValueError('Base stopped request incomplete')
    receipts = {}
    for suffix, expected in (('controlled_5', (True, False)),
                             ('controlled_6', (False, True))):
        request_path = HERE / ('request-' + suffix + '.jsonl')
        candidate = rows(request_path)
        if len(candidate) != 600:
            raise ValueError('Yielding request incomplete: ' + suffix)
        for left, right in zip(base, candidate):
            if any(left.get(key) != right.get(key) for key in FIXED):
                raise ValueError('Fixed ego/signal/cell context differs: ' + suffix)
        source = HERE / 'diagnostic' / suffix
        survey_path = source / 'scene-survey.json'
        motion_path = source / 'native-motion.jsonl'
        survey = json.loads(survey_path.read_text())
        motions = rows(motion_path)
        if len(motions) != 600 or any(
                motion.get('other', {}).get('center_xyz_m', [None, None])[1] != request['other_center_xy_m'][1]
                for motion, request in zip(motions, candidate)):
            raise ValueError('Saved other-vehicle history differs: ' + suffix)
        facts = assess(survey, motions)
        observed = (facts['other_stopped_before_ego'],
                    facts['other_within_intersection_at_ego_entry'])
        if observed != expected or facts['ego_stop_frame'] is None or \
                facts['ego_stop_frame'] >= facts['ego_entry_frame']:
            raise ValueError('Statutory original-frame branch facts differ: ' + suffix)
        bad = json.loads(json.dumps(motions))
        del bad[0]['other']['body_xyz_m']
        try:
            assess(survey, bad)
        except ValueError as exc:
            if 'body history' not in str(exc):
                raise
        else:
            raise AssertionError('Missing other body history accepted')
        receipts[suffix] = {'request_sha256': sha(request_path),
                            'survey_sha256': sha(survey_path),
                            'motion_sha256': sha(motion_path),
                            'ego_stop_frame': facts['ego_stop_frame'],
                            'ego_entry_frame': facts['ego_entry_frame'],
                            'other_stopped_before_ego': observed[0],
                            'other_within_intersection_at_ego_entry': observed[1],
                            'missing_other_body_rejected': True}
    return {'format': 'c154537-yielding-branch-cpu-audit-v1', 'passed': True,
            'base_request_sha256': sha(base_path), 'cases': receipts,
            'synthetic_source_shapes_only': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain prior yielding audit')
    args.output.write_text(json.dumps(audit(), indent=2) + '\n')
