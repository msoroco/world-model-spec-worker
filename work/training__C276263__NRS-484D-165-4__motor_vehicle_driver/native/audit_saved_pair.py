"""Join two saved parked-lamp cases and independently test their fixed context."""
import argparse
import json
from pathlib import Path

from comparison_audit import audit as compare
from delivery_audit import audit as delivery

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
VIEWS = ['overview', 'approach', 'reference_corner', 'driver_reference']


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def summary(case, attempt, saved, fixture, reject_beam_contrast=False):
    proof = delivery(case, attempt, saved, fixture=fixture)
    if proof['joined_frames'] != 600:
        raise ValueError('Independent source join incomplete')
    native = rows(attempt / 'native-rows.jsonl')
    reviewed = rows(attempt / 'lamp-review.jsonl')
    config = json.loads((attempt / 'config.json').read_text())
    saved_receipt = json.loads(saved.read_text())
    observed = sorted(set(row['observed_beam_state'] for row in native))
    if reject_beam_contrast:
        observed = ['low_beam']
    aim = [row['aim_elevation_deg'] for row in reviewed]
    intensity = [row['relative_intensity'] for row in reviewed]
    return {'case_id': case, 'frames': len(native),
            'fixed_context': {'road_sha256': saved_receipt['original_source_hashes']['road.xodr'],
                              'ego_blueprint_id': native[0]['ego_blueprint_id'],
                              'curb_lane_id': native[0]['observed_curb_lane_id'],
                              'duration_s': config['duration_s'], 'rate_hz': config['rate_hz'],
                              'source_cameras': VIEWS,
                              'camera_config': config['cameras'],
                              'parked_pose': native[0]['ego_center_xyz_m']},
            'requested_beam_state': config['requested_beam_state'],
            'observed_beam_states': observed,
            'parked_activity_frames': sum(r['parking_activity'] == 'parked' for r in reviewed),
            'beam_pixel_reviewed_frames': len(reviewed),
            'source_sha256': saved_receipt['original_source_hashes'],
            'beam_aim_elevation_deg_range': [min(aim), max(aim)],
            'relative_intensity_range': [min(intensity), max(intensity)],
            'original_native_observed': not fixture,
            'legal_verdict': None}


def audit_pair(attempt_a, saved_a, attempt_b, saved_b, fixture=False,
               reject_beam_contrast=False):
    a = summary(AID + '__probe_a', attempt_a, saved_a, fixture)
    b = summary(AID + '__probe_b', attempt_b, saved_b, fixture, reject_beam_contrast)
    proof = compare(a, b)
    proof['source_bound'] = True
    proof['diagnostic_only'] = fixture
    proof['actual_pixels_verified'] = False
    proof['physical_completion_verified'] = False
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('attempt-a', 'saved-a', 'attempt-b', 'saved-b'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--reject-beam-contrast', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.attempt_a, args.saved_a, args.attempt_b,
                                args.saved_b, args.fixture, args.reject_beam_contrast)))
