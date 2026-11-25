"""Independent CPU comparison of the marked-line and no-line requests."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent
CASE1 = NATIVE / 'request-controlled_1.jsonl'
CASE3 = HERE / 'request-controlled_3.jsonl'
FIXED = ('frame', 'time_s', 'other_center_xy_m', 'requested_signal_state',
         'requested_near_side_crosswalk_present', 'intersection_entry_front_x_m',
         'source_kind', 'native_observed', 'legal_verdict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(no_line, marked_line):
    if len(no_line) != 600 or len(marked_line) != 600:
        raise ValueError('Both exact requests need 600 frames')
    if no_line[0]['ego_center_xy_m'] != marked_line[0]['ego_center_xy_m'] or \
            no_line[-1]['ego_center_xy_m'] != marked_line[-1]['ego_center_xy_m']:
        raise ValueError('Initial or terminal ego route differs')
    for index, (left, right) in enumerate(zip(no_line, marked_line)):
        if left.get('frame') != index or right.get('frame') != index:
            raise ValueError('Original frame order differs')
        if any(left.get(key) != right.get(key) for key in FIXED):
            raise ValueError('Fixed signal, cell, participant or time differs')
        if left['ego_center_xy_m'][1] != right['ego_center_xy_m'][1] or \
                abs(left['ego_front_x_m'] - left['ego_center_xy_m'][0] - 2) > 1e-5 or \
                abs(right['ego_front_x_m'] - right['ego_center_xy_m'][0] - 2) > 1e-5:
            raise ValueError('Ego lane or front-body reference differs')
        if left.get('requested_stop_line_present') is not False or \
                right.get('requested_stop_line_present') is not True or \
                left.get('requested_view_reference_center_x_m') != -9.0 or \
                right.get('requested_stop_line_front_x_m') != -9.0:
            raise ValueError('Declared stop-reference priority differs')
    no_line_stops = [r['frame'] for r in no_line if r['frame'] and
                     r['ego_center_xy_m'] == no_line[r['frame'] - 1]['ego_center_xy_m']]
    marked_stops = [r['frame'] for r in marked_line if r['frame'] and
                    r['ego_center_xy_m'] == marked_line[r['frame'] - 1]['ego_center_xy_m']]
    if not no_line_stops or not marked_stops or \
            no_line[no_line_stops[0]]['ego_center_xy_m'][0] != -9.0 or \
            marked_line[marked_stops[0]]['ego_front_x_m'] != -9.0:
        raise ValueError('Contrasting requested stop positions absent')
    if no_line[-1]['ego_front_x_m'] <= -6 or marked_line[-1]['ego_front_x_m'] <= -6:
        raise ValueError('Requested intersection entry absent')
    return {'format': 'c154537-requested-stop-priority-audit-v1', 'passed': True,
            'no_line_request_sha256': sha(CASE1), 'marked_line_request_sha256': sha(CASE3),
            'frame_count': 600, 'fixed_context_checked': list(FIXED),
            'deliberate_difference': 'marked stop line versus no line/crosswalk surveyed view',
            'native_or_physical_result_claimed': False, 'legal_verdict_claimed': False}


def self_test():
    left, right = rows(CASE1), rows(CASE3)
    receipt = audit(left, right)
    negative = json.loads(json.dumps(right))
    negative[120]['other_center_xy_m'][1] += 1
    try:
        audit(left, negative)
    except ValueError as exc:
        if 'Fixed signal' not in str(exc):
            raise
    else:
        raise AssertionError('Changed participant history accepted')
    negative = json.loads(json.dumps(right))
    negative[120]['requested_stop_line_present'] = False
    try:
        audit(left, negative)
    except ValueError as exc:
        if 'stop-reference' not in str(exc):
            raise
    else:
        raise AssertionError('Missing marked-line request accepted')
    receipt['negative_changed_participant_rejected'] = True
    receipt['negative_missing_line_rejected'] = True
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain previous audit')
    args.output.write_text(json.dumps(self_test(), indent=2) + '\n')
