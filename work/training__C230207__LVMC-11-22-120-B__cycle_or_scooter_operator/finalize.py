"""Finalize original bicycle and sign survey packets from a saved attempt."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from measure import measure as measure_sources

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED = ('video_frames.jsonl', 'bicycle-poses.jsonl', 'restriction-context.json')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(root):
    return measure_sources(root / 'bicycle-poses.jsonl', root / 'restriction-context.json')


def finalize(attempt, output):
    root, output = Path(attempt), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Fresh saved-only stage required')
    for name in REQUIRED:
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config_path = root / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing required source: config.json')
    cfg = json.loads(config_path.read_text())
    context = json.loads((root / 'restriction-context.json').read_text())
    case_id = cfg['case_id']
    if context.get('case_id') != case_id:
        raise ValueError('Saved bicycle case identity differs')
    frames = rows(root / 'video_frames.jsonl')
    poses = rows(root / 'bicycle-poses.jsonl')
    if len(frames) != 600 or len(poses) != 600:
        raise ValueError('Missing original bicycle frame map or poses')
    for index, (frame, pose) in enumerate(zip(frames, poses)):
        if frame['native_frame'] != pose['native_frame'] or abs(frame['time_s'] - pose['time_s']) > .005:
            raise ValueError('Original bicycle/frame-map join differs')
        if frame.get('video_frame', index) != index or pose['video_frame'] != index:
            raise ValueError('Original video frame identity differs')
        native_cameras = frame.get('camera_native_frames')
        if not isinstance(native_cameras, dict) or set(native_cameras) != set(VIEWS):
            raise ValueError('Original four-view frame identity missing')
        if any(value != frame['native_frame'] for value in native_cameras.values()):
            raise ValueError('Original four-view frame join differs')
    observation = measure(root)
    hashes = {name: digest(root / name) for name in REQUIRED}
    trace = []
    channels = {name: [] for name in ('dev.regulatory_sign', 'dev.governs',
                                     'ru.bicycle', 'st.roadway', 'rel.occupies')}
    for frame, pose in zip(frames, poses):
        x, y = pose['rider_xy_m']
        vx, vy = pose['velocity_xy_mps']
        speed = math.hypot(vx, vy)
        trace.append({'frame': frame['native_frame'], 'time_s': frame['time_s'],
                      'position': {'x': x, 'y': y, 'z': pose['rider_z_m']},
                      'position_m': [x, y, pose['rider_z_m']],
                      'heading_deg': math.degrees(math.atan2(vy, vx)),
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': [vx, vy, 0], 'control': {}})
        values = {
            'dev.regulatory_sign': {'sign_id': context['sign_id'],
                                    'sign_text': context['sign_text'],
                                    'native_sign_survey': context['native_sign_survey'],
                                    'physical_pixels_verified': context['physical_sign_pixels_verified'],
                                    'source': 'restriction-context.json,road.xodr'},
            'dev.governs': {'orientation': context['sign_orientation'],
                            'sign_x_m': context['sign_x_m'],
                            'designation_verified': context['city_traffic_engineer_designation_verified'],
                            'source': 'restriction-context.json,road.xodr'},
            'ru.bicycle': {'blueprint_id': pose['rider_blueprint_id'],
                           'wheel_characteristics_reviewed': context['wheel_characteristics_reviewed'],
                           'source': 'bicycle-poses.jsonl,restriction-context.json'},
            'st.roadway': {'polygon_xy_m': context['roadway_xy_m'],
                           'sign_id': context['sign_id'],
                           'source': 'restriction-context.json,road.xodr'},
            'rel.occupies': {'rider_xy_m': [x, y],
                             'target_surface': context['target_surface'],
                             'source': 'bicycle-poses.jsonl,restriction-context.json'},
        }
        for name, value in values.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    trace_path = root / 'trace.jsonl'
    if trace_path.exists():
        if rows(trace_path) != trace:
            raise ValueError('Existing trace differs from original bicycle samples')
    else:
        trace_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in trace))
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir / (name + '.jsonl')).write_text(
            ''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))
    report = {'format': 'worker-analysis-report-v1', 'case_id': case_id,
              'measurements': {'measure': {'method': 'measure', 'value': observation,
                                           'sources': hashes}},
              'legal_verdict_claimed': False}
    intended = context['target_surface']
    measured = observation['roadway_occupied_after_sign_frames']
    result = {
        'case_id': case_id, 'measured_values': observation,
        'target_checks': [{'target': 'original rider roadway use after sign',
                           'requested': intended, 'measured': measured,
                           'method': 'saved Native rider poses joined to original road polygon and sign survey',
                           'tolerance': 0,
                           'matched': measured == 0 if intended == 'shoulder' else measured > 0,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(hashes)}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'sign face, City designation and bicycle wheel review pending',
        'physical_failure_flags': ['independent physical and authority review pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'],
        'recording_evidence': [
            {'name': name, 'unit': 'structured', 'reference': 'channels/' + name + '.jsonl'}
            for name in channels],
        'realized_observables': {}, 'accepted': False,
        'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
