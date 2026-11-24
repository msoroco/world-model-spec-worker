"""Saved-source speed-zone observation; never equates a fixture with legal proof."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID = 'training__C179819__NRS-484B-620-2__motor_vehicle_driver'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600
MPS_PER_MPH = 0.44704


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def measure(root):
    root = Path(root)
    paths = {n: root / n for n in ('video_frames.jsonl', 'native_motion.jsonl', 'speed_zone_context.json')}
    for n, p in paths.items():
        if not p.is_file():
            raise ValueError('Missing saved source: ' + n)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_motion.jsonl'])
    context = json.loads(paths['speed_zone_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original 20 Hz frames')
    if context.get('assignment_id') != AID or context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    hashes = {}
    for camera in CAMERAS:
        n = 'camera_' + camera + '.mkv'
        p = root / n
        if not p.is_file() or not p.stat().st_size:
            raise ValueError('Missing source camera: ' + camera)
        proc = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                               'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(p)],
                              capture_output=True, text=True)
        if proc.returncode:
            raise ValueError('Source camera decode failed: ' + camera)
        streams = json.loads(proc.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera not 600 decoded 20 Hz frames: ' + camera)
        if context['review_kind'] == 'original_source_review' and (streams[0].get('width'), streams[0].get('height')) != (1920, 1080):
            raise ValueError('Original source camera resolution mismatch: ' + camera)
        hashes[n] = sha(p)
    if context.get('camera_sha256') != hashes:
        raise ValueError('Zone review not bound to camera bytes')
    for key in ('reviewer', 'zone_establishment_source', 'installed_sign_source', 'authorized_value_source',
                'zone_boundary_source', 'governing_road_direction_source', 'vehicle_class_source',
                'road_id', 'travel_direction_id'):
        if not context.get(key):
            raise ValueError('Missing reviewed zone source: ' + key)
    for key in ('zone_established', 'appropriate_sign_installed', 'sign_governs_road_direction', 'ego_is_motor_vehicle'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing source-reviewed activation fact: ' + key)
    speed_limit = context.get('authorized_mph')
    if not finite(speed_limit) or speed_limit <= 0:
        raise ValueError('Missing positive signed authorized speed')
    bounds = context.get('zone_station_bounds_m')
    axis = context.get('road_axis_xy')
    if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite(v) for v in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('Invalid reviewed zone boundaries')
    if not isinstance(axis, list) or len(axis) != 2 or not all(finite(v) for v in axis) or abs(math.hypot(*axis)-1) > .01:
        raise ValueError('Invalid reviewed road axis')
    inside, speeds, prev_native, prev_t = [], [], -1, -1.0
    expected_kind = 'synthetic_native_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_native_velocity'
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= prev_native:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= prev_t or (i and abs(t-prev_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if row.get('video_frame') != i or row.get('native_frame') != native or row.get('source_kind') != expected_kind:
            raise ValueError('Motion source does not join original frame/provenance')
        if row.get('road_id') != context['road_id'] or row.get('travel_direction_id') != context['travel_direction_id']:
            raise ValueError('Motion road/direction differs from reviewed sign governance')
        for key in ('ego_x_m', 'ego_y_m', 'velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps'):
            if not finite(row.get(key)):
                raise ValueError('Missing finite original pose/velocity: ' + key)
        station = row['ego_x_m']*axis[0] + row['ego_y_m']*axis[1]
        inside.append(bounds[0] <= station <= bounds[1])
        speeds.append(math.sqrt(row['velocity_x_mps']**2+row['velocity_y_mps']**2+row['velocity_z_mps']**2)/MPS_PER_MPH)
        prev_native, prev_t = native, t
    if prev_t - frames[0]['time_s'] < 29.9:
        raise ValueError('Source span less than 30 seconds')
    indices = [i for i, v in enumerate(inside) if v]
    if not indices or inside[0] or inside[-1]:
        raise ValueError('No complete signed-zone traversal')
    activation = all(context[k] for k in ('zone_established', 'appropriate_sign_installed',
                                           'sign_governs_road_direction', 'ego_is_motor_vehicle'))
    return {'format': 'saved-speed-zone-observation', 'assignment_id': AID,
            'review_kind': context['review_kind'],
            'sources': {**{n: sha(p) for n, p in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': prev_t-frames[0]['time_s'],
            'first_zone_frame': indices[0], 'last_zone_frame': indices[-1],
            'zone_frame_count': len(indices), 'authorized_mph': speed_limit,
            'maximum_observed_mph_in_zone': max(speeds[i] for i in indices),
            'frames_above_authorized_in_zone': [i for i in indices if speeds[i] > speed_limit],
            'source_reviewed_activation_complete': activation,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    Path(args.output_json).write_text(json.dumps(measure(args.source_dir), indent=2)+'\n')
