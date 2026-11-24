"""Source-bound speed and path measurement; no automatic legal verdict."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID = 'training__C230224__NRS-484B-785-1a__cycle_or_scooter_operator'
COUNT = 600
CAP_MPS = 15 * 0.44704


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def inside(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def measure(root):
    root = Path(root)
    paths = {key: root / key for key in ('video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json')}
    if any(not p.is_file() for p in paths.values()):
        raise ValueError('Missing original frame, trace, or reviewed context')
    frames, trace = records(paths['video_frames.jsonl']), records(paths['native_rider_trace.jsonl'])
    context = json.loads(paths['scooter_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT or context.get('assignment_id') != AID:
        raise ValueError('Exact assignment and 600 joined frames required')
    if context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Unspecified source kind')
    camera_hashes = {}
    if context['review_kind'] == 'original_source_review':
        for name in ('forward', 'rear', 'left', 'right'):
            camera = root / ('camera_' + name + '.mkv')
            if not camera.is_file():
                raise ValueError('Missing original source camera: ' + name)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                '-show_entries', 'stream=nb_read_frames,r_frame_rate', '-of', 'json', str(camera)],
                capture_output=True, text=True)
            if probe.returncode:
                raise ValueError('Source camera decode failed: ' + name)
            streams = json.loads(probe.stdout).get('streams', [])
            if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
                raise ValueError('Source camera does not contain 600 20 Hz frames: ' + name)
            camera_hashes[camera.name] = sha(camera)
        if context.get('camera_sha256') != camera_hashes:
            raise ValueError('Reviewed context not bound to original cameras')
    if context.get('device_subtype') != 'electric_scooter':
        raise ValueError('A bicycle or unspecified device is not an electric scooter')
    for key in ('scooter_classification_source', 'scooter_mass_source', 'scooter_motor_max_speed_source',
                'path_surface_source', 'path_continuity_source', 'path_access_source',
                'roadway_boundary_source', 'ordinance_applicability_source', 'ordinance_review_source'):
        if not context.get(key):
            raise ValueError('Missing source-bound context: ' + key)
    mass = context.get('scooter_rider_excluded_mass_lb')
    maximum = context.get('scooter_motor_only_max_mph')
    if type(mass) not in (int, float) or type(maximum) not in (int, float) or not 0 < mass <= 100 or not 0 < maximum <= 20:
        raise ValueError('Electric-scooter classification bounds unproved')
    if context.get('ordinance_exception_reviewed') is not True or context.get('path_access_reviewed') is not True:
        raise ValueError('Path access and ordinance exception not reviewed')
    box = context.get('path_box_xyxy_m')
    if not isinstance(box, list) or len(box) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in box) or box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError('Missing measured path geometry')
    if type(context.get('device_actor_id')) is not int or type(context.get('rider_actor_id')) is not int or context['device_actor_id'] == context['rider_actor_id']:
        raise ValueError('Distinct scooter and rider source IDs required')
    prev_native = -1
    prev_time = -1.0
    speeds = []
    on_path = 0
    above_cap = 0
    for i, (f, row) in enumerate(zip(frames, trace)):
        n, t = f.get('native_frame'), f.get('time_s')
        if f.get('video_frame') != i or type(n) is not int or n <= prev_native or type(t) not in (int, float) or not math.isfinite(t) or t <= prev_time or (i and abs(t-prev_time-.05) > .005):
            raise ValueError('Original frame/time join failed')
        if row.get('video_frame') != i or row.get('native_frame') != n or row.get('device_actor_id') != context['device_actor_id'] or row.get('rider_actor_id') != context['rider_actor_id']:
            raise ValueError('Scooter/rider identity join failed')
        if row.get('source_kind') != ('synthetic_native_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_native_pose'):
            raise ValueError('Original Native provenance missing')
        speed = row.get('device_speed_mps')
        point = row.get('device_center_xy_m')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0 or not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
            raise ValueError('Native scooter speed or pose missing')
        speeds.append(speed)
        on_path += inside(point, box)
        above_cap += speed > CAP_MPS
        prev_native, prev_time = n, t
    if frames[-1]['time_s'] - frames[0]['time_s'] < 29.9:
        raise ValueError('Full 30-second original observation required')
    return {'format': 'source-bound-scooter-path-speed-v1', 'assignment_id': AID,
            'source_sha256': {**{key: sha(path) for key, path in paths.items()}, **camera_hashes},
            'review_kind': context['review_kind'], 'samples': COUNT,
            'path_center_frames': on_path, 'above_15_mph_frames': above_cap,
            'min_speed_mph': min(speeds) / .44704, 'max_speed_mph': max(speeds) / .44704,
            'motor_classification_max_mph': maximum, 'rider_excluded_mass_lb': mass,
            'legal_result': None, 'physical_acceptance_claimed': False}
