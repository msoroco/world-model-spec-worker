"""Independent original-source comparison of outside versus entering a red-X lane."""
import argparse
import json
from pathlib import Path

from delivery_audit import ASSIGNMENT, audit_delivery, audit_structure, require, rows, sha, source

CASE_A = ASSIGNMENT + '__probe_1'
CASE_B = ASSIGNMENT + '__probe_2'

def compare_structure(first_attempt, second_attempt, first_hashes, second_hashes):
    first = Path(first_attempt).resolve()
    second = Path(second_attempt).resolve()
    require(first != second, 'Independent original attempts required')
    left = audit_structure(first, CASE_A, first_hashes)
    right = audit_structure(second, CASE_B, second_hashes)
    require(left['target_lane_id'] == -2 and right['target_lane_id'] == -1,
            'Declared outside versus entering contrast absent')
    require(left['governed_lane_id'] == right['governed_lane_id'] == -1,
            'Fixed signal-governed lane changed')
    require(first_hashes['native-map-readback.xodr'] == second_hashes['native-map-readback.xodr'],
            'Fixed original road and signal inventory changed')
    a_rows = rows(source(first, 'native-signal-rows.jsonl'))
    b_rows = rows(source(second, 'native-signal-rows.jsonl'))
    require(all(a['signal'] == b['signal'] for a, b in zip(a_rows, b_rows)),
            'Original red-X state, mount or signal authority changed')
    require(all(a['vehicle']['lane_id'] == b['vehicle']['lane_id'] == -2
                for a, b in zip(a_rows[:200], b_rows[:200])),
            'Fixed initial adjacent-lane approach changed')
    require(left['red_x_facing_frames'] == right['red_x_facing_frames'] == 600,
            'Fixed red-X facing state changed')
    require(left['governed_lane_overlap_frames'] == 0 and
            right['governed_lane_overlap_frames'] > 0 and
            right['first_governed_lane_overlap_frame'] >= 200,
            'Observed red-X governed-lane entry contrast absent')
    a_config = json.loads(source(first, 'config.json').read_text())
    b_config = json.loads(source(second, 'config.json').read_text())
    fixed = ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras')
    require(all(a_config.get(key) == b_config.get(key) for key in fixed),
            'Fixed actor, duration, cameras or scenario context changed')
    return {'format': 'c230247-red-x-source-comparison-v1', 'passed': True,
            'case_ids': [CASE_A, CASE_B],
            'fixed_checks': {'same_original_map': True, 'same_red_x_state': True,
                             'same_initial_approach': True, 'same_actor_duration_and_cameras': True},
            'deliberate_difference': 'red_x_lane_occupancy',
            'governed_lane_overlap_frames': [left['governed_lane_overlap_frames'],
                                             right['governed_lane_overlap_frames']],
            'source_hashes': [first_hashes, second_hashes], 'legal_verdict': None}

def compare_delivery(first_attempt, second_attempt, first_review, second_review):
    left = audit_delivery(first_attempt, CASE_A, first_review)
    right = audit_delivery(second_attempt, CASE_B, second_review)
    result = compare_structure(first_attempt, second_attempt,
                               first_review['source_sha256'], second_review['source_sha256'])
    result.update(format='c230247-red-x-reviewed-original-comparison-v1',
                  delivery_audit_sha256=[sha(Path(first_review['review_path'])),
                                         sha(Path(second_review['review_path']))],
                  reviewed_recording_ids=[left['recording_id'], right['recording_id']])
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition-a', required=True)
    parser.add_argument('--condition-b', required=True)
    parser.add_argument('--review-a', required=True)
    parser.add_argument('--review-b', required=True)
    parser.add_argument('--structure-only', action='store_true')
    args = parser.parse_args()
    left = json.loads(Path(args.review_a).read_text())
    right = json.loads(Path(args.review_b).read_text())
    if args.structure_only:
        report = compare_structure(args.condition_a, args.condition_b,
                                   left['source_sha256'], right['source_sha256'])
    else:
        left['review_path'] = args.review_a
        right['review_path'] = args.review_b
        report = compare_delivery(args.condition_a, args.condition_b, left, right)
    print(json.dumps(report, sort_keys=True))

if __name__ == '__main__':
    main()
