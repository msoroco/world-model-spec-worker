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
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def decoded_rgb_sha(path):
    """Bind generated diagnostics to pixels, independent of encoder metadata."""
    process = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                '-i', str(path), '-vsync', '0', '-f', 'rawvideo',
                                '-pix_fmt', 'rgb24', 'pipe:1'], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    while True:
        data = process.stdout.read(1024 * 1024)
        if not data:
            break
        digest.update(data)
    if process.wait() != 0:
        raise ValueError('Source camera RGB decode failed')
    return digest.hexdigest()


def measure(root):
    root = Path(root)
    frame_path = root / 'video_frames.jsonl'
    trace_path = root / 'pass_trace.jsonl'
    context_path = root / 'school_zone_context.json'
    for path in (frame_path, trace_path, context_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    frames, trace = load_lines(frame_path), load_lines(trace_path)
    context = json.loads(context_path.read_text())
    if len(frames) != FRAMES or len(trace) != FRAMES:
        raise ValueError('Requires all 600 original 20 Hz samples')
    video_hashes = {}
    for camera in CAMERAS:
        path = root / (camera + '.mkv')
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
    if context.get('review_kind') == 'synthetic_diagnostic':
        decoded = {camera: decoded_rgb_sha(root / (camera + '.mkv'))
                   for camera in CAMERAS}
        if context.get('camera_rgb_sequence_sha256') != decoded:
            raise ValueError('Synthetic school-zone context is not bound to decoded camera pixels')
    elif context.get('camera_sha256') != video_hashes:
        raise ValueError('School-zone context is not bound to original camera bytes')
    if context.get('assignment_id') != ASSIGNMENT:
        raise ValueError('School-zone context assignment mismatch')
    if context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Review provenance kind missing')
    if context['review_kind'] == 'original_source_review':
        for camera in CAMERAS:
            out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                  '-show_entries', 'stream=width,height', '-of', 'json',
                                  str(root / (camera + '.mkv'))],
                                 capture_output=True, text=True, check=True)
            dim = json.loads(out.stdout)['streams'][0]
            expected = (1920, 1080) if camera == 'overview' else (1280, 720)
            if (dim['width'], dim['height']) != expected:
                raise ValueError('Original source camera resolution differs: ' + camera)
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
                'sign_says_limit_in_effect'):
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
    lamp_states = None
    if context['beacon_operational']:
        lamp_path = root / 'beacon_lamps.jsonl'
        if not lamp_path.is_file():
            raise ValueError('Missing required source: beacon_lamps.jsonl')
        if context.get('beacon_lamps_sha256') != sha(lamp_path):
            raise ValueError('Beacon lamp source hash differs')
        lamp_states = load_lines(lamp_path)
        if len(lamp_states) != FRAMES:
            raise ValueError('Beacon lamp source needs 600 joined frames')
        ids = context.get('beacon_lamp_actor_ids')
        if (not isinstance(ids, list) or len(ids) < 2 or
                any(type(x) is not int for x in ids) or len(set(ids)) != len(ids) or
                len(ids) != context['beacon_yellow_lights']):
            raise ValueError('Two distinct source-identified beacon lamp actors required')
    prev_native, prev_time = -1, -1.0
    diffs, inside, times, lateral_offsets = [], [], [], []
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
        if lamp_states is not None:
            lamp = lamp_states[i]
            if (lamp.get('video_frame') != i or lamp.get('native_frame') != native or
                    lamp.get('source_kind') != ('synthetic_lamp_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_lamp_state') or
                    lamp.get('lamp_actor_ids') != context['beacon_lamp_actor_ids'] or
                    not isinstance(lamp.get('yellow_lit'), list) or
                    len(lamp['yellow_lit']) != len(context['beacon_lamp_actor_ids']) or
                    any(type(v) is not bool for v in lamp['yellow_lit'])):
                raise ValueError('Beacon lamps do not join original frame and actor sources')
        if row.get('source_kind') != ('synthetic_native_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_native_pose'):
            raise ValueError('Pass trace source kind does not match review kind')
        if row.get('ego_route_direction_id') != route or row.get('other_route_direction_id') != route:
            raise ValueError('Overtaken vehicle is not on sourced same-direction route')
        ego, other = row.get('ego_station_m'), row.get('other_station_m')
        if not finite(ego) or not finite(other):
            raise ValueError('Missing finite original longitudinal stations')
        ego_lateral = row.get('ego_lateral_m')
        other_lateral = row.get('other_lateral_m')
        if not finite(ego_lateral) or not finite(other_lateral):
            raise ValueError('Missing sourced lateral lane positions')
        if i and (ego < trace[i-1]['ego_station_m'] or other < trace[i-1]['other_station_m']):
            raise ValueError('Route stations do not advance in the same direction')
        diffs.append(ego - other)
        lateral_offsets.append(ego_lateral - other_lateral)
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
    origin = lateral_offsets[0]
    if abs(origin) > .75 or abs(lateral_offsets[-1]) > .75:
        raise ValueError('Pass must begin and end in the original route lane')
    departures = [i for i in range(1, cross) if abs(lateral_offsets[i] - origin) > .75]
    if not departures:
        raise ValueError('No observed lane departure before passing')
    start = departures[0]
    if abs(lateral_offsets[cross] - origin) < 1.8:
        raise ValueError('No adjacent-lane separation at abreast crossing')
    returns = [i for i in range(cross + 1, FRAMES)
               if abs(lateral_offsets[i] - origin) <= .75 and diffs[i] >= 7]
    if not returns:
        raise ValueError('No observed lane return after passing')
    end = returns[0]
    if not all(inside[start:end + 1]):
        raise ValueError('Whole pass and lane return must remain in signed school zone')
    alternating = False
    if lamp_states is not None:
        states = [tuple(x['yellow_lit']) for x in lamp_states[start:end + 1]]
        exclusive = [x.index(True) for x in states if sum(x) == 1]
        alternating = (not any(sum(x) > 1 for x in states) and
                       len(set(exclusive)) >= 2)
    civil_at_cross = context['civil_time_unix_s'] + times[cross] - times[0]
    seconds_after_end = civil_at_cross - context['operation_end_unix_s']
    seconds_before_next = context['next_operation_start_unix_s'] - civil_at_cross
    return {
        'format': 'saved-school-zone-pass-observation', 'assignment_id': ASSIGNMENT,
        'source_kind': context['review_kind'],
        'sources': {'video_frames.jsonl': sha(frame_path), 'pass_trace.jsonl': sha(trace_path),
                    'school_zone_context.json': sha(context_path),
                    **({'beacon_lamps.jsonl': sha(root / 'beacon_lamps.jsonl')} if lamp_states is not None else {}),
                    **{k + '.mkv': v for k, v in video_hashes.items()}},
        'sample_count': FRAMES, 'sample_span_s': times[-1] - times[0],
        'pass_crossing_video_frame': cross, 'pass_crossing_time_s': times[cross],
        'pass_crossing_in_signed_zone': inside[cross],
        'lane_departure_video_frame': start, 'lane_return_video_frame': end,
        'whole_pass_in_signed_zone': True,
        'same_direction_route_source': context['route_direction_source'],
        'civil_time_at_cross_unix_s': civil_at_cross,
        'school_in_session': context['school_in_session'],
        'pupils_in_class': context['pupils_in_class'],
        'minutes_after_operation_end_at_cross': seconds_after_end / 60,
        'minutes_before_next_operation_at_cross': seconds_before_next / 60,
        'at_least_half_hour_after_end_observed': seconds_after_end >= 1800,
        'at_least_half_hour_before_next_observed': seconds_before_next >= 1800,
        'within_half_hour_window_observed': seconds_after_end >= 1800 and seconds_before_next >= 1800,
        'beacon_operational': context['beacon_operational'],
        'beacon_yellow_lights': context.get('beacon_yellow_lights'),
        'beacon_yellow_alternating': alternating,
        'beacon_lamp_state_source': 'joined_saved_lamp_states' if lamp_states is not None else None,
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
