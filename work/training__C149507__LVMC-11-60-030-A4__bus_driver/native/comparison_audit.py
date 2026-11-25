"""Independent source comparison of bus wheel gap with fixed loading context."""
import argparse
import hashlib
import json
from pathlib import Path

AID = 'training__C149507__LVMC-11-60-030-A4__bus_driver'
FIXED = ('vehicle_class', 'location_kind', 'public_street', 'curb_face_y_m',
         'curb_heading_deg', 'other_vehicle_baseline_mps',
         'loading_activity_frames', 'native_map_sha256',
         'curb_calibration_sha256', 'bus_classification_sha256',
         'wheel_geometry_sha256', 'loading_zone_sha256')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root, suffix):
    root = Path(root)
    context = json.loads((root / 'bus-zone-review.json').read_text())
    if context.get('case_id') != AID + '__' + suffix:
        raise ValueError('Exact bus comparison case differs')
    frame_map = rows(root / 'video_frames.jsonl')
    poses = rows(root / 'bus-traffic-poses.jsonl')
    if len(frame_map) != len(poses) or len(poses) != 600:
        raise ValueError('Full 600-frame bus comparison missing')
    loading = set(context['loading_activity_frames'])
    active = []
    for index, (frame, pose) in enumerate(zip(frame_map, poses)):
        if frame.get('video_frame') != pose.get('video_frame') or frame.get(
                'native_frame') != pose.get('native_frame') or abs(
                frame['time_s'] - pose['time_s']) > 1e-4:
            raise ValueError('Original bus comparison frame join differs')
        if index in loading and pose['bus_observed_speed_mps'] <= .10:
            active.append(abs(pose['right_front_wheel_contact_y_m'] -
                              context['curb_face_y_m']))
    if len(active) < 100:
        raise ValueError('Stopped loading comparison interval missing')
    return context, {'frame_count': 600, 'active_loading_frames': len(active),
                     'gap_m_range': [min(active), max(active)]}


def compare(left, right, middle, diagnostic=False, negative_selftest=False):
    a, first = check(left, 'probe_1')
    b, second = check(right, 'probe_2')
    c, boundary = check(middle, 'probe_3')
    if negative_selftest:
        b['location_kind'] = 'passenger_loading_zone'
    if any(a.get(name) != b.get(name) or a.get(name) != c.get(name) for name in FIXED):
        raise ValueError('Fixed bus loading context differs')
    if not (first['gap_m_range'][1] < .4572 and
            all(abs(value - .4572) <= .005 for value in boundary['gap_m_range']) and
            second['gap_m_range'][0] > .4572):
        raise ValueError('Source-measured below/at/above front-wheel gap contrast absent')
    return {'format': 'worker-bus-loading-comparison-v1',
        'comparison_id': AID + '__wheel_gap_comparison',
        'case_ids': [AID + '__probe_1', AID + '__probe_2', AID + '__probe_3'],
        'passed': True, 'diagnostic_fixture': diagnostic,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'fixed_conditions_checked': list(FIXED),
        'deliberate_difference': 'source-measured right-front-wheel curb gap during stopped loading',
        'source_sha256': {'probe_1': {name: sha(Path(left) / name) for name in
            ('video_frames.jsonl', 'bus-traffic-poses.jsonl', 'bus-zone-review.json')},
            'probe_2': {name: sha(Path(right) / name) for name in
            ('video_frames.jsonl', 'bus-traffic-poses.jsonl', 'bus-zone-review.json')},
            'probe_3': {name: sha(Path(middle) / name) for name in
            ('video_frames.jsonl', 'bus-traffic-poses.jsonl', 'bus-zone-review.json')}},
        'measurements': {'probe_1': first, 'probe_2': second, 'probe_3': boundary},
        'boundary_measurement_uncertainty_m': .005}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--middle', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(compare(args.left, args.right, args.middle, args.diagnostic,
                             args.negative_selftest), sort_keys=True))
