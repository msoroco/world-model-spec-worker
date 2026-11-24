"""Saved-source school-zone speed and independently reviewed activation facts."""
import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

AID = 'training__C262666__NRS-484B-363-1__heavy_vehicle_driver'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600
MPS_PER_MPH = .44704


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(root):
    root = Path(root)
    paths = {name: root/name for name in ('video_frames.jsonl', 'native_motion.jsonl', 'school_zone_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: '+name)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_motion.jsonl'])
    context = json.loads(paths['school_zone_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original 20 Hz frames')
    kind = context.get('review_kind')
    if context.get('assignment_id') != AID or kind not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    hashes = {}
    for name in CAMERAS:
        path = root/('camera_'+name+'.mkv')
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing source camera: '+name)
        run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                              '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(path)],
                             capture_output=True, text=True)
        if run.returncode:
            raise ValueError('Source camera decode failed: '+name)
        streams = json.loads(run.stdout).get('streams', [])
        wanted = (1920, 1080) if name == 'forward' else (1280, 720)
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: '+name)
        if kind == 'original_source_review' and (streams[0].get('width'), streams[0].get('height')) != wanted:
            raise ValueError('Original camera resolution mismatch: '+name)
        hashes[path.name] = sha(path)
    if context.get('camera_sha256') != hashes:
        raise ValueError('Context not bound to source camera bytes')
    for key in ('reviewer', 'zone_designation_source', 'zone_sign_source', 'calendar_source',
                'school_hours_source', 'half_hour_window_source', 'beacon_source',
                'beacon_phase_source', 'nonbeacon_sign_schedule_source', 'vehicle_class_source',
                'civil_time_source', 'road_axis_source', 'condition_stability_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed school-zone source: '+key)
    for key in ('zone_designated', 'school_session_day', 'half_hour_window_exception',
                'beacon_operational', 'pupils_in_class', 'beacon_flashing',
                'nonbeacon_sign_in_effect', 'ego_is_motor_vehicle', 'condition_stable_30s'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing reviewed school-zone fact: '+key)
    if not context['condition_stable_30s']:
        raise ValueError('School-zone condition changes during capture; per-frame review required')
    if not isinstance(context.get('road_id'), int) or not isinstance(context.get('ego_actor_id'), int):
        raise ValueError('Missing source road or vehicle identity')
    bounds, axis = context.get('zone_station_bounds_m'), context.get('road_axis_xy')
    if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite(v) for v in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('Invalid reviewed school-zone boundaries')
    if not isinstance(axis, list) or len(axis) != 2 or not all(finite(v) for v in axis) or abs(math.hypot(*axis)-1) > .01:
        raise ValueError('Invalid reviewed road axis')
    try:
        civil_start = datetime.fromisoformat(context['civil_start_iso'])
        if civil_start.tzinfo is None or civil_start.utcoffset() is None:
            raise ValueError('Civil time must include timezone')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Invalid source-reviewed civil start time') from exc
    expected = 'synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_velocity'
    prev_frame, prev_t = -1, -1.0
    inside, speeds = [], []
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= prev_frame:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= prev_t or (i and abs(t-prev_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if (row.get('video_frame') != i or row.get('native_frame') != native or
                row.get('source_kind') != expected or row.get('ego_actor_id') != context['ego_actor_id'] or
                row.get('road_id') != context['road_id']):
            raise ValueError('Motion source does not join original frame, road, vehicle or provenance')
        for key in ('ego_x_m', 'ego_y_m', 'velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps'):
            if not finite(row.get(key)):
                raise ValueError('Missing finite Native measurement: '+key)
        station = row['ego_x_m']*axis[0]+row['ego_y_m']*axis[1]
        inside.append(bounds[0] <= station <= bounds[1])
        speeds.append(math.sqrt(sum(row[k]**2 for k in
                                    ('velocity_x_mps', 'velocity_y_mps', 'velocity_z_mps')))/MPS_PER_MPH)
        prev_frame, prev_t = native, t
    if prev_t-frames[0]['time_s'] < 29.9:
        raise ValueError('Source span less than 30 seconds')
    zone_frames = [i for i, hit in enumerate(inside) if hit]
    if not zone_frames or inside[0] or inside[-1]:
        raise ValueError('No complete school-zone traversal')
    beacon_exception = (context['beacon_operational'] and context['pupils_in_class'] and
                        not context['beacon_flashing'])
    sign_exception = (not context['beacon_operational'] and not context['nonbeacon_sign_in_effect'])
    active = (context['zone_designated'] and context['ego_is_motor_vehicle'] and
              context['school_session_day'] and not context['half_hour_window_exception'] and
              not beacon_exception and not sign_exception)
    return {'format': 'saved-heavy-school-zone-observation', 'assignment_id': AID,
            'review_kind': kind, 'sources': {**{name: sha(path) for name, path in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': prev_t-frames[0]['time_s'],
            'civil_start_iso': civil_start.isoformat(),
            'civil_end_iso': (civil_start+timedelta(seconds=prev_t-frames[0]['time_s'])).isoformat(),
            'zone_frame_count': len(zone_frames), 'first_zone_frame': zone_frames[0],
            'last_zone_frame': zone_frames[-1], 'maximum_observed_mph_in_zone': max(speeds[i] for i in zone_frames),
            'frames_above_15_mph_in_zone': [i for i in zone_frames if speeds[i] > 15.0],
            'reviewed_activation_complete': active,
            'reviewed_exception_facts': {'school_not_in_session': not context['school_session_day'],
                                         'half_hour_window': context['half_hour_window_exception'],
                                         'operational_beacon_nonflashing_class_hours': beacon_exception,
                                         'nonbeacon_sign_off': sign_exception},
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(measure(args.source_dir), indent=2)+'\n')
