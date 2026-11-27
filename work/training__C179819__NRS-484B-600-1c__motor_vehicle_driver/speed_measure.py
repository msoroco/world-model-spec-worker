"""Measure posted-zone speed from joined saved sources; never issue a verdict."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID = 'training__C179819__NRS-484B-600-1c__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = {AID + '__' + s for s in ('below_posted', 'at_posted', 'above_posted')}
REQUIRED = ('road_context.json', 'road.xodr', 'native_motion.jsonl',
            'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(source):
    root = Path(source)
    for name in (*REQUIRED, *(view + '.mkv' for view in CAMERAS)):
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((root / 'road_context.json').read_text())
    kind = context.get('review_kind')
    if context.get('assignment_id') != AID or context.get('case_id') not in CASES or kind not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Exact posted-zone source identity missing')
    keys = ('sign_id', 'authority_source', 'highway_source', 'governed_direction',
            'reviewer', 'sign_position_x_m', 'zone_start_m', 'zone_end_m')
    if any(context.get(key) is None or context.get(key) == '' for key in keys):
        raise ValueError('Public-authority posting or governed portion source missing')
    if not finite(context.get('posted_mph')) or context['posted_mph'] <= 0:
        raise ValueError('Original posted speed missing')
    if (not all(finite(context.get(key)) for key in ('sign_position_x_m', 'zone_start_m', 'zone_end_m')) or
            not context['zone_start_m'] <= context['sign_position_x_m'] < context['zone_end_m']):
        raise ValueError('Sign passage and governed highway extent missing')
    if context.get('road_xodr_sha256') != sha(root / 'road.xodr'):
        raise ValueError('Posting review not bound to original road')
    camera_hashes = {}
    for view in CAMERAS:
        path = root / (view + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height',
                                '-of', 'json', str(path)], capture_output=True, text=True)
        streams = json.loads(probe.stdout).get('streams', []) if probe.returncode == 0 else []
        size = (1920, 1080) if view == 'overview' else (1280, 720)
        if (len(streams) != 1 or streams[0].get('nb_read_frames') != '600' or
                streams[0].get('r_frame_rate') != '20/1' or
                (streams[0].get('width'), streams[0].get('height')) != size):
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: ' + view)
        camera_hashes[path.name] = sha(path)
    if kind == 'original_source_review' and context.get('camera_sha256') != camera_hashes:
        raise ValueError('Original posting review not bound to camera bytes')
    frames, motion, trace = (rows(root / name) for name in
                             ('video_frames.jsonl', 'native_motion.jsonl', 'trace.jsonl'))
    if any(len(stream) != 600 for stream in (frames, motion, trace)):
        raise ValueError('Requires 600 joined original frames')
    observed, sign_passage = [], []
    previous_native, previous_time = -1, -1.0
    expected = 'synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_velocity'
    for i, (frame, row, core) in enumerate(zip(frames, motion, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if (frame.get('video_frame') != i or type(native) is not int or native <= previous_native or
                not finite(t) or t <= previous_time or (i and abs(t - previous_time - .05) > .005) or
                row.get('native_frame') != native or row.get('video_frame') != i or row.get('source_kind') != expected or
                core.get('frame') != native or abs(core.get('time_s', -10) - t) > .005 or
                set(frame.get('camera_native_frames', {})) != set(CAMERAS) or
                any(value != native for value in frame['camera_native_frames'].values())):
            raise ValueError('Original motion, Core or camera frame join differs')
        pos = row.get('position_xyz_m')
        if (row.get('ego_actor_id') != context.get('ego_actor_id') or
                not isinstance(pos, list) or len(pos) != 3 or not all(finite(v) for v in pos) or
                row.get('road_id') != context.get('road_id') or row.get('lane_id') != context.get('lane_id')):
            raise ValueError('Original vehicle and highway position source differs')
        velocity = [row.get(key) for key in ('velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps')]
        if not all(finite(value) for value in velocity) or type(row.get('driving_state')) is not bool:
            raise ValueError('Measured Native velocity or driving state missing')
        if row.get('sign_id') != context['sign_id'] or row.get('sign_passed') != (pos[0] >= context['sign_position_x_m']):
            raise ValueError('Original sign passage source differs')
        if row['sign_passed']:
            sign_passage.append(i)
        if (row['driving_state'] and context['zone_start_m'] <= pos[0] <= context['zone_end_m'] and
                row.get('direction') == context['governed_direction']):
            observed.append((i, math.sqrt(sum(value * value for value in velocity)) * 2.2369362921))
        previous_native, previous_time = native, t
    if not sign_passage or not observed or frames[-1]['time_s'] - frames[0]['time_s'] < 29.9:
        raise ValueError('No source-observed sign passage or governed-zone driving')
    speeds = [value for _, value in observed]
    return {'format': 'saved-posted-speed-observation', 'assignment_id': AID,
            'case_id': context['case_id'], 'review_kind': kind,
            'sources': {name: sha(root / name) for name in REQUIRED} | camera_hashes,
            'sample_count': 600, 'governed_frame_count': len(observed),
            'posted_mph': context['posted_mph'], 'sign_passage_frame': sign_passage[0],
            'min_measured_mph': min(speeds), 'max_measured_mph': max(speeds),
            'frames_above_posted': [i for i, value in observed if value > context['posted_mph']],
            'authority_source': context['authority_source'], 'highway_source': context['highway_source'],
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
