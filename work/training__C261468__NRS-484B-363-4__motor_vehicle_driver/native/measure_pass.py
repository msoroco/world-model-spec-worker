"""Measure a saved school-zone pass episode from joined source samples.

This reports physical and calendar observations. It makes no legal judgment.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ASSIGNMENT = 'training__C261468__NRS-484B-363-4__motor_vehicle_driver'
CAMERAS = ('forward', 'rear', 'left', 'right')
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def measure(root):
    root = Path(root)
    frame_path = root / 'video_frames.jsonl'
    trace_path = root / 'pass_trace.jsonl'
    context_path = root / 'school_zone_context.json'
    for path in (frame_path, trace_path, context_path):
        if not path.is_file():
            raise ValueError('Missing required saved source: ' + path.name)
    frames, trace = load_lines(frame_path), load_lines(trace_path)
    context = json.loads(context_path.read_text())
    if len(frames) != FRAMES or len(trace) != FRAMES:
        raise ValueError('Requires all 600 original 20 Hz samples')
    video_hashes = {}
    for camera in CAMERAS:
        path = root / ('camera_' + camera + '.mkv')
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing nonempty source camera: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height',
                                '-of', 'json', str(path)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError('Source camera decode failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(FRAMES) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: ' + camera)
        video_hashes[camera] = sha(path)
    if context.get('camera_sha256') != video_hashes:
        raise ValueError('School-zone context is not bound to original camera bytes')
    if context.get('assignment_id') != ASSIGNMENT:
        raise ValueError('School-zone context assignment mismatch')
    if context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Review provenance kind missing')
    if context['review_kind'] == 'original_source_review':
        for camera in CAMERAS:
            out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                  '-show_entries', 'stream=width,height', '-of', 'json',
                                  str(root / ('camera_' + camera + '.mkv'))],
                                 capture_output=True, text=True, check=True)
            dim = json.loads(out.stdout)['streams'][0]
            if (dim['width'], dim['height']) != (1920, 1080):
                raise ValueError('Original source camera must be full resolution: ' + camera)
    for key in ('reviewer', 'zone_sign_source', 'zone_boundary_source', 'route_direction_source', 'school_calendar_source',
                'operation_hours_source', 'civil_time_source', 'beacon_or_sign_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed school-zone context source: ' + key)
    if context.get('zone_kind') not in ('school_zone', 'school_crossing_zone'):
        raise ValueError('Signed school-zone kind missing')
    boundary = context.get('zone_station_m')
    if (not isinstance(boundary, list) or len(boundary) != 2 or
            not all(finite(v) for v in boundary) or boundary[0] >= boundary[1]):
        raise ValueError('Signed zone boundaries invalid')
    for key in ('school_in_session', 'pupils_in_class', 'beacon_operational',
                'beacon_yellow_alternating', 'sign_says_limit_in_effect'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing source-reviewed condition: ' + key)
    for key in ('civil_time_unix_s', 'operation_end_unix_s', 'next_operation_start_unix_s'):
        if not finite(context.get(key)):
            raise ValueError('Missing finite sourced civil time: ' + key)
    if context['operation_end_unix_s'] >= context['next_operation_start_unix_s']:
        raise ValueError('School operation interval invalid')
    if context['beacon_operational'] and context.get('beacon_yellow_lights') is None:
        raise ValueError('Operational beacon needs reviewed yellow-light count')
    if context['beacon_operational'] and (type(context['beacon_yellow_lights']) is not int
                                          or context['beacon_yellow_lights'] < 2):
        raise ValueError('Beacon definition requires at least two yellow lights')
    if context['beacon_operational'] and not context.get('beacon_with_sign'):
        raise ValueError('Beacon definition requires an accompanying sign')
    prev_native, prev_time = -1, -1.0
    diffs, inside, times = [], [], []
    route = context.get('route_direction_id')
    if not route:
        raise ValueError('Sourced route direction missing')
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= prev_native:
            raise ValueError('Original frame identity invalid')
        if not finite(t) or t <= prev_time or (i and abs(t - prev_time - .05) > .005):
            raise ValueError('Original 20 Hz cadence invalid')
        if row.get('video_frame') != i or row.get('native_frame') != native:
            raise ValueError('Pass trace does not join original frame map')
        if row.get('source_kind') != ('synthetic_native_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_native_pose'):
            raise ValueError('Pass trace source kind does not match review kind')
        if row.get('ego_route_direction_id') != route or row.get('other_route_direction_id') != route:
            raise ValueError('Overtaken vehicle is not on sourced same-direction route')
        ego, other = row.get('ego_station_m'), row.get('other_station_m')
        if not finite(ego) or not finite(other):
            raise ValueError('Missing finite original longitudinal stations')
        if i and (ego < trace[i-1]['ego_station_m'] or other < trace[i-1]['other_station_m']):
            raise ValueError('Route stations do not advance in the same direction')
        diffs.append(ego - other)
        inside.append(boundary[0] <= ego <= boundary[1] and boundary[0] <= other <= boundary[1])
        times.append(t)
        prev_native, prev_time = native, t
    if times[-1] - times[0] < 29.9:
        raise ValueError('Original sample span is less than 30 seconds')
    crossing = [i for i in range(1, FRAMES) if diffs[i-1] < 0 <= diffs[i]]
    if not crossing or diffs[0] >= 0 or diffs[-1] <= 0:
        raise ValueError('No complete behind-to-ahead pass episode')
    cross = crossing[0]
    if not inside[cross]:
        raise ValueError('Pass crossing is outside the signed school zone')
    civil_at_cross = context['civil_time_unix_s'] + times[cross] - times[0]
    return {
        'format': 'saved-school-zone-pass-observation', 'assignment_id': ASSIGNMENT,
        'source_kind': context['review_kind'],
        'sources': {'video_frames.jsonl': sha(frame_path), 'pass_trace.jsonl': sha(trace_path),
                    'school_zone_context.json': sha(context_path),
                    **{'camera_' + k + '.mkv': v for k, v in video_hashes.items()}},
        'sample_count': FRAMES, 'sample_span_s': times[-1] - times[0],
        'pass_crossing_video_frame': cross, 'pass_crossing_time_s': times[cross],
        'pass_crossing_in_signed_zone': inside[cross],
        'same_direction_route_source': context['route_direction_source'],
        'civil_time_at_cross_unix_s': civil_at_cross,
        'school_in_session': context['school_in_session'],
        'pupils_in_class': context['pupils_in_class'],
        'minutes_after_operation_end_at_cross': (civil_at_cross - context['operation_end_unix_s']) / 60,
        'minutes_before_next_operation_at_cross': (context['next_operation_start_unix_s'] - civil_at_cross) / 60,
        'beacon_operational': context['beacon_operational'],
        'beacon_yellow_lights': context.get('beacon_yellow_lights'),
        'beacon_yellow_alternating': context['beacon_yellow_alternating'],
        'sign_says_limit_in_effect': context['sign_says_limit_in_effect'],
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    result = measure(args.source_dir)
    Path(args.output_json).write_text(json.dumps(result, indent=2) + '\n')
