"""Saved-source school-crossing-zone speed and independently reviewed activation facts."""
import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

AID = 'training__C255451__NRS-484B-363-2__bus_driver'
CASE = AID + '__selected_d08892c9__condition_b'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600
MPS_PER_MPH = .44704


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(root, expected_case=CASE):
    root = Path(root)
    paths = {name: root/name for name in ('video_frames.jsonl', 'native_motion.jsonl',
                                         'children_context.jsonl', 'school_zone_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: '+name)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_motion.jsonl'])
    children = lines(paths['children_context.jsonl'])
    context = json.loads(paths['school_zone_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT or len(children) != COUNT:
        raise ValueError('Requires 600 joined original 20 Hz frames')
    kind = context.get('review_kind')
    if (context.get('assignment_id') != AID or context.get('case_id') != expected_case or
            kind not in ('synthetic_diagnostic', 'original_source_review')):
        raise ValueError('Exact case or source provenance mismatch')
    if kind == 'original_source_review':
        survey_path = root/'native_survey.json'
        if not survey_path.is_file() or context.get('native_survey_sha256') != sha(survey_path):
            raise ValueError('Original survey bytes missing or changed')
        survey = json.loads(survey_path.read_text())
        for source_key, context_key in (
                ('zone_establishment_source', 'zone_designation_source'),
                ('installed_sign_source', 'zone_sign_source'),
                ('calendar_source', 'calendar_source'),
                ('school_hours_source', 'school_hours_source'),
                ('half_hour_window_source', 'half_hour_window_source'),
                ('beacon_source', 'beacon_source'),
                ('beacon_phase_source', 'beacon_phase_source'),
                ('nonbeacon_sign_schedule_source', 'nonbeacon_sign_schedule_source'),
                ('motor_bus_class_source', 'vehicle_class_source'),
                ('children_source', 'children_source'),
                ('beacon_lights_source', 'beacon_lights_source'),
                ('civil_time_source', 'civil_time_source'),
                ('governing_road_direction_source', 'road_axis_source'),
                ('zone_station_bounds_m', 'zone_station_bounds_m'),
                ('road_axis_xy', 'road_axis_xy'),
                ('road_id', 'road_id'),
                ('travel_direction_id', 'travel_direction_id'),
                ('authorized_mph', 'authorized_mph'),
                ('civil_start_iso', 'civil_start_iso')):
            if survey.get(source_key) != context.get(context_key):
                raise ValueError('Original survey and reviewed context disagree: '+context_key)
        if survey.get('reviewed_plan_case_id') != expected_case or not survey.get('planned_context_source'):
            raise ValueError('Original survey lacks exact school-crossing-zone plan source')
        if survey.get('planned_context') != context.get('planned_context') or survey.get('planned_context_source') != context.get('planned_context_source'):
            raise ValueError('Original planned school-crossing-zone condition changed')
        paths['native_survey.json'] = survey_path
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
    if context.get('camera_sha256') != hashes:
        raise ValueError('Context not bound to source camera bytes')
    for key in ('reviewer', 'zone_designation_source', 'zone_sign_source', 'calendar_source',
                'school_hours_source', 'half_hour_window_source', 'beacon_source',
                'beacon_phase_source', 'nonbeacon_sign_schedule_source', 'vehicle_class_source',
                'civil_time_source', 'road_axis_source', 'condition_stability_source',
                'children_source', 'beacon_lights_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed school-crossing-zone source: '+key)
    for key in ('zone_designated', 'school_session_day', 'half_hour_window_exception',
                'beacon_operational', 'pupils_in_class', 'beacon_flashing',
                'nonbeacon_sign_in_effect', 'ego_is_motor_bus', 'condition_stable_30s',
                'beacon_sign_present', 'beacon_alternating_yellow'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing reviewed school-crossing-zone fact: '+key)
    if not context['condition_stable_30s']:
        raise ValueError('School-zone condition changes during capture; per-frame review required')
    if context['beacon_operational']:
        if (not context['beacon_sign_present'] or
                type(context.get('beacon_yellow_light_count')) is not int or
                context['beacon_yellow_light_count'] < 2):
            raise ValueError('Operational beacon lacks source-reviewed sign and two yellow lights')
        if context['beacon_flashing'] and not context['beacon_alternating_yellow']:
            raise ValueError('Beacon flashing claim lacks alternating yellow evidence')
    if (type(context.get('road_id')) is not int or type(context.get('ego_actor_id')) is not int or
            not isinstance(context.get('travel_direction_id'), str) or not context['travel_direction_id']):
        raise ValueError('Missing source road, direction or vehicle identity')
    if context.get('authorized_mph') != 25:
        raise ValueError('Reviewed school-crossing-zone speed limit differs from statute')
    bounds, axis = context.get('zone_station_bounds_m'), context.get('road_axis_xy')
    if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite(v) for v in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('Invalid reviewed school-crossing-zone boundaries')
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
    for i, (frame, row, child_row) in enumerate(zip(frames, trace, children)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= prev_frame:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= prev_t or (i and abs(t-prev_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if (row.get('video_frame') != i or row.get('native_frame') != native or
                row.get('source_kind') != expected or row.get('ego_actor_id') != context['ego_actor_id'] or
                row.get('road_id') != context['road_id'] or
                row.get('travel_direction_id') != context['travel_direction_id']):
            raise ValueError('Motion source does not join original frame, road, direction, vehicle or provenance')
        if (child_row.get('video_frame') != i or child_row.get('native_frame') != native or
                child_row.get('source_kind') != expected or
                {child.get('id') for child in child_row.get('children', [])} !=
                {'child_left', 'child_right'}):
            raise ValueError('Child actor source does not join original frame')
        for child in child_row['children']:
            if not finite(child.get('x_m')) or not finite(child.get('y_m')):
                raise ValueError('Missing finite original child position')
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
        raise ValueError('No complete school-crossing-zone traversal')
    beacon_exception = (context['beacon_operational'] and context['pupils_in_class'] and
                        not context['beacon_flashing'])
    sign_exception = (not context['beacon_operational'] and not context['nonbeacon_sign_in_effect'])
    active = (context['zone_designated'] and context['ego_is_motor_bus'] and
              context['school_session_day'] and not context['half_hour_window_exception'] and
              not beacon_exception and not sign_exception)
    return {'format': 'saved-bus-school-crossing-zone-observation', 'assignment_id': AID, 'case_id': expected_case,
            'review_kind': kind, 'sources': {**{name: sha(path) for name, path in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': prev_t-frames[0]['time_s'],
            'civil_start_iso': civil_start.isoformat(),
            'civil_end_iso': (civil_start+timedelta(seconds=prev_t-frames[0]['time_s'])).isoformat(),
            'zone_frame_count': len(zone_frames), 'first_zone_frame': zone_frames[0],
            'last_zone_frame': zone_frames[-1], 'maximum_observed_mph_in_zone': max(speeds[i] for i in zone_frames),
            'frames_above_25_mph_in_zone': [i for i in zone_frames if speeds[i] > 25.0],
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
