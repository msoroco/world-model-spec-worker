"""Saved Native velocity observation for the absolute 80 mph clause."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID = 'training__C329610__NRS-484B-600-1e__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600
MPS_PER_MPH = .44704
CAP_MPH = 80.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(root):
    root = Path(root)
    paths = {name: root/name for name in ('video_frames.jsonl', 'native_motion.jsonl', 'road_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: '+name)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_motion.jsonl'])
    context = json.loads(paths['road_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original 20 Hz frames')
    kind = context.get('review_kind')
    if context.get('assignment_id') != AID or kind not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    if kind == 'original_source_review' and context.get('case_id') not in {AID+'__'+suffix for suffix in ('probe_a', 'probe_at', 'probe_b')}:
        raise ValueError('Original speed source has no exact case identity')
    hashes = {}
    for name in CAMERAS:
        path = root/(name+'.mkv')
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing source camera: '+name)
        run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                              '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(path)],
                             capture_output=True, text=True)
        if run.returncode:
            raise ValueError('Source camera decode failed: '+name)
        streams = json.loads(run.stdout).get('streams', [])
        wanted = (1920, 1080) if name == 'overview' else (1280, 720)
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: '+name)
        if kind == 'original_source_review' and (streams[0].get('width'), streams[0].get('height')) != wanted:
            raise ValueError('Original camera resolution mismatch: '+name)
        hashes[path.name] = sha(path)
    if (kind == 'original_source_review' or 'camera_sha256' in context) and context.get('camera_sha256') != hashes:
        raise ValueError('Context not bound to source camera bytes')
    for key in ('reviewer', 'vehicle_identity_source', 'route_source', 'driving_state_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed context source: '+key)
    vehicle_id = context.get('ego_actor_id')
    if type(vehicle_id) is not int:
        raise ValueError('Missing source vehicle identity')
    previous_frame, previous_t = -1, -1.0
    speeds, route = [], []
    expected = 'synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_velocity'
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= previous_frame:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= previous_t or (i and abs(t-previous_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if (row.get('video_frame') != i or row.get('native_frame') != native or
                row.get('source_kind') != expected or row.get('ego_actor_id') != vehicle_id):
            raise ValueError('Motion source does not join original frame, vehicle or provenance')
        if kind == 'original_source_review':
            if not row.get('ego_blueprint'):
                raise ValueError('Vehicle source identity does not join frame')
            for key in ('position_xyz_m',):
                if not isinstance(row.get(key), list) or len(row[key]) != 3 or not all(finite(v) for v in row[key]):
                    raise ValueError('Missing finite source vehicle position: '+key)
        for key in ('velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps'):
            if not finite(row.get(key)):
                raise ValueError('Missing finite Native velocity: '+key)
        if type(row.get('driving_state')) is not bool:
            raise ValueError('Missing Native driving state')
        if row.get('road_id') not in (1, 13, 4) or row.get('lane_id') != -1:
            raise ValueError('Saved left-turn road or lane identity differs')
        route.append(row['road_id'])
        if row['driving_state']:
            speeds.append((i, math.sqrt(sum(row[k]**2 for k in
                                             ('velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps')))/MPS_PER_MPH))
        previous_frame, previous_t = native, t
    if previous_t-frames[0]['time_s'] < 29.9 or not speeds or list(dict.fromkeys(route)) != [1, 13, 4]:
        raise ValueError('No 30-second driving observation')
    return {'format': 'saved-absolute-speed-observation', 'assignment_id': AID, 'review_kind': kind,
            'sources': {**{name: sha(path) for name, path in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': previous_t-frames[0]['time_s'],
            'driving_frame_count': len(speeds), 'statutory_cap_mph': CAP_MPH,
            'left_turn_road_ids': list(dict.fromkeys(route)),
            'maximum_observed_mph_while_driving': max(value for _, value in speeds),
            'frames_above_80_mph': [i for i, value in speeds if value > CAP_MPH],
            'posted_limit_required': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(measure(args.source_dir), indent=2)+'\n')
