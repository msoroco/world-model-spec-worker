"""Independent 600-frame request comparison for near-side crosswalk priority."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NO_CROSSWALK = HERE.parent / 'request-controlled_1.jsonl'
CROSSWALK = HERE / 'request-controlled_4.jsonl'
FIXED = ('frame', 'time_s', 'other_center_xy_m', 'requested_signal_state',
         'requested_stop_line_present', 'intersection_entry_front_x_m',
         'source_kind', 'native_observed', 'legal_verdict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(left, right):
    if len(left) != 600 or len(right) != 600:
        raise ValueError('Exact 600-frame pair required')
    if left[0]['ego_center_xy_m'] != right[0]['ego_center_xy_m'] or \
            left[-1]['ego_center_xy_m'] != right[-1]['ego_center_xy_m']:
        raise ValueError('Initial or terminal route differs')
    for index, (a, b) in enumerate(zip(left, right)):
        if a.get('frame') != index or b.get('frame') != index or \
                any(a.get(key) != b.get(key) for key in FIXED):
            raise ValueError('Fixed frame, signal or participant context differs')
        if a['ego_center_xy_m'][1] != b['ego_center_xy_m'][1] or \
                abs(a['ego_front_x_m'] - a['ego_center_xy_m'][0] - 2) > 1e-5 or \
                abs(b['ego_front_x_m'] - b['ego_center_xy_m'][0] - 2) > 1e-5:
            raise ValueError('Ego lane or body-front relation differs')
        if a.get('requested_near_side_crosswalk_present') is not False or \
                b.get('requested_near_side_crosswalk_present') is not True or \
                a.get('requested_view_reference_center_x_m') != -9.0 or \
                b.get('requested_crosswalk_near_edge_x_m') != -10.0:
            raise ValueError('Crosswalk reference contrast differs')
    if not any(a['ego_center_xy_m'][0] == -9.0 and
               a['ego_center_xy_m'] == left[i - 1]['ego_center_xy_m']
               for i, a in enumerate(left) if i) or not any(
                   b['ego_front_x_m'] == -10.0 and
                   b['ego_center_xy_m'] == right[i - 1]['ego_center_xy_m']
                   for i, b in enumerate(right) if i):
        raise ValueError('Contrasting stop plateaus absent')
    return {'format': 'c154537-crosswalk-request-comparison-v1', 'passed': True,
            'no_crosswalk_sha256': sha(NO_CROSSWALK), 'crosswalk_sha256': sha(CROSSWALK),
            'fixed_context_checked': list(FIXED),
            'deliberate_difference': 'absent crosswalk/view stop versus near-side crosswalk stop',
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def self_test():
    left, right = read(NO_CROSSWALK), read(CROSSWALK)
    receipt = audit(left, right)
    negative = json.loads(json.dumps(right))
    negative[120]['other_center_xy_m'][1] += 1
    try:
        audit(left, negative)
    except ValueError as exc:
        if 'Fixed frame' not in str(exc):
            raise
    else:
        raise AssertionError('Changed participant accepted')
    negative = json.loads(json.dumps(right))
    negative[120]['requested_near_side_crosswalk_present'] = False
    try:
        audit(left, negative)
    except ValueError as exc:
        if 'Crosswalk reference' not in str(exc):
            raise
    else:
        raise AssertionError('Missing crosswalk accepted')
    receipt['changed_participant_rejected'] = True
    receipt['missing_crosswalk_rejected'] = True
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain previous comparison audit')
    args.output.write_text(json.dumps(self_test(), indent=2) + '\n')
