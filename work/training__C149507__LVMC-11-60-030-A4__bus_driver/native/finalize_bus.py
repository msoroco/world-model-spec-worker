"""Finalize source-reviewed bus loading observations without a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from measure_bus import measure

AID = 'training__C149507__LVMC-11-60-030-A4__bus_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('video_frames.jsonl', 'bus-traffic-poses.jsonl', 'bus-zone-review.json',
           'road.xodr', 'curb-calibration.json', 'bus-classification.json',
           'wheel-geometry.json', 'loading-location.json')
REVIEW_HASHES = {'native_map_sha256': 'road.xodr',
    'curb_calibration_sha256': 'curb-calibration.json',
    'bus_classification_sha256': 'bus-classification.json',
    'wheel_geometry_sha256': 'wheel-geometry.json',
    'loading_zone_sha256': 'loading-location.json'}


def require(value, message):
    if not value:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewed_measure(root, config):
    for source in SOURCES:
        require((root / source).is_file(), 'Missing required source: ' + source)
    frames = rows(root / SOURCES[0])
    poses = rows(root / SOURCES[1])
    review = json.loads((root / SOURCES[2]).read_text())
    require(review.get('assignment_id') == AID and
            review.get('case_id') == config['case_id'], 'Bus review identity differs')
    require(review.get('review_kind') in ('original_source_review', 'synthetic_diagnostic'),
            'Independent bus source review required')
    for field, source in REVIEW_HASHES.items():
        require(review.get(field) == sha(root / source),
                'Reviewed bus source hash differs: ' + source)
    require(len(frames) == len(poses) == 600, 'Full 600-frame bus source required')
    if review['review_kind'] == 'original_source_review':
        for name in ('road.xodr',) + tuple(view + '.mkv' for view in VIEWS):
            require((root / name).is_file(), 'Missing required source: ' + name)
            require(review.get('source_sha256', {}).get(name) == sha(root / name),
                    'Reviewed original source hash differs: ' + name)
    loading = set(review.get('loading_activity_frames', []))
    require(all(type(i) is int and 0 <= i < 600 for i in loading),
            'Reviewed loading frame set invalid')
    curb_y = review.get('curb_face_y_m')
    curb_heading = review.get('curb_heading_deg')
    baseline = review.get('other_vehicle_baseline_mps')
    require(all(type(x) in (int, float) and math.isfinite(x) for x in
                (curb_y, curb_heading, baseline)) and baseline > 0,
            'Reviewed curb and traffic calibration missing')
    normalized = []
    for i, (frame, pose) in enumerate(zip(frames, poses)):
        native = frame.get('native_frame')
        require(frame.get('video_frame') == pose.get('video_frame') == i and
                pose.get('native_frame') == native and
                abs(frame['time_s'] - pose['time_s']) < 1e-4,
                'Original bus frame/time join differs')
        camera_frames = pose.get('camera_native_frames')
        require(isinstance(camera_frames, dict) and set(camera_frames) == set(VIEWS) and
                all(camera_frames[name] == native for name in VIEWS),
                'Four original bus camera joins differ')
        speed = pose.get('other_vehicle_observed_speed_mps')
        require(type(speed) in (int, float) and math.isfinite(speed) and speed >= 0,
                'Other traffic speed missing')
        normalized.append({'video_frame': i, 'native_frame': native,
            'time_s': i / 20, 'source_cameras': {name: i for name in VIEWS},
            'bus_observed_speed_mps': pose['bus_observed_speed_mps'],
            'other_vehicle_observed_speed_mps': speed,
            'other_vehicle_delay_s': max(0, (baseline - speed) / baseline * .05),
            'right_front_wheel_contact_y_m': pose['right_front_wheel_contact_y_m'],
            'bus_curb_heading_difference_deg': abs((pose['bus_yaw_deg'] - curb_heading +
                180) % 360 - 180), 'loading_activity_observed': i in loading})
    context = dict(review)
    context['source_kind'] = 'native_bus_wheel_curb_and_traffic_readback'
    observation = measure(context, normalized)
    return frames, poses, review, observation


def finalize(attempt, output):
    root, output = Path(attempt), Path(output)
    require(not output.exists() and not (root / 'result.json').exists(),
            'Fresh saved-only finalization required')
    config = json.loads((root / 'config.json').read_text())
    require(config.get('assignment_id') == AID and
            config.get('case_id') in config.get('supported_case_ids', []),
            'Exact bus assignment configuration differs')
    frames, poses, review, observation = reviewed_measure(root, config)
    hashes = {name: sha(root / name) for name in SOURCES}
    trace_path = root / 'trace.jsonl'
    trace = []
    for frame, pose in zip(frames, poses):
        xyz = pose['bus_xyz_m']
        speed = pose['bus_observed_speed_mps']
        trace.append({'frame': frame['native_frame'], 'time_s': frame['time_s'],
            'position': {'x': xyz[0], 'y': xyz[1], 'z': xyz[2]},
            'position_m': xyz, 'heading_deg': pose['bus_yaw_deg'],
            'speed_mps': speed, 'speed_mph': speed / .44704,
            'velocity_mps': [speed, 0, 0], 'control': pose.get('requested_control', {})})
    if trace_path.exists():
        original = rows(trace_path)
        require(len(original) == len(trace), 'Original bus trace frame count differs')
        for left, right in zip(original, trace):
            require(left.get('frame') == right['frame'] and
                    abs(left.get('time_s', -1) - right['time_s']) < 1e-4 and
                    len(left.get('position_m', [])) >= 2 and
                    all(abs(a - b) < 1e-3 for a, b in
                        zip(left['position_m'][:2], right['position_m'][:2])) and
                    abs(left.get('speed_mps', -1) - right['speed_mps']) < 1e-3,
                    'Original bus trace differs from Native bus source')
    else:
        trace_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                      for row in trace))
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for spec in config['recording_description']['channels']:
        name = spec['name']
        values = [{'time_s': frame['time_s'], 'value':
            {'bus_xyz_m': pose['bus_xyz_m'], 'wheel_contact_y_m':
             pose['right_front_wheel_contact_y_m'], 'loading_observed':
             frame['video_frame'] in set(review['loading_activity_frames'])}}
            for frame, pose in zip(frames, poses)]
        (channel_dir / (name + '.jsonl')).write_text(''.join(
            json.dumps(item, allow_nan=False) + '\n' for item in values))
    report = {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
        'measurements': {'bus_loading_measurement': {'method': 'reviewed_measure',
            'value': observation, 'sources': hashes}}, 'legal_verdict_claimed': False}
    target = config['bus_case']
    observed_gap = observation['wheel_to_curb_gap_m_range']
    result = {'case_id': config['case_id'], 'measured_values': observation,
        'target_checks': [{'target': 'right-front-wheel curb gap while stopped loading',
            'requested': target, 'measured': observed_gap,
            'method': 'Native wheel contact and independently reviewed curb/loading source',
            'tolerance': 0.005 if target == 'at' else None,
            'matched': (all(abs(value - 0.4572) <= 0.005 for value in observed_gap)
                if target == 'at' else observation['all_loading_frames_within_18_inches']
                if target == 'near' else not observation['all_loading_frames_within_18_inches']),
            'physical_cause_confirmed': False, 'cause_evidence': list(hashes)}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'original loading/location/traffic and pixel review pending',
        'physical_failure_flags': ['independent original-source review pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': spec['name'], 'unit': spec['unit'],
            'reference': 'channels/' + spec['name'] + '.jsonl'}
            for spec in config['recording_description']['channels']] +
            [{'name': 'bus_zone_review', 'unit': 'structured',
              'reference': 'bus-zone-review.json'}],
        'realized_observables': {},
        'provenance_kind': 'synthetic_fixture' if
            review['review_kind'] == 'synthetic_diagnostic' else 'native_saved_sample',
        'diagnostic_fixture': review['review_kind'] == 'synthetic_diagnostic',
        'accepted': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
