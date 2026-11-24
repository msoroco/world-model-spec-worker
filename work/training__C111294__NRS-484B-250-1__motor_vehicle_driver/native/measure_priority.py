"""Measure intersection entry order from saved source frames, without a legal verdict."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ASSIGNMENT = 'training__C111294__NRS-484B-250-1__motor_vehicle_driver'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(source):
    source = Path(source)
    paths = {name: source / name for name in ('video_frames.jsonl', 'intersection_trace.jsonl', 'intersection_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: ' + name)
    frames, trace = rows(paths['video_frames.jsonl']), rows(paths['intersection_trace.jsonl'])
    context = json.loads(paths['intersection_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original frames')
    if context.get('assignment_id') != ASSIGNMENT or context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    hashes = {}
    for camera in CAMERAS:
        name = 'camera_' + camera + '.mkv'
        path = source / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing source camera: ' + camera)
        proc = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                               'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(path)],
                              capture_output=True, text=True)
        if proc.returncode:
            raise ValueError('Source camera decode failed: ' + camera)
        stream = json.loads(proc.stdout).get('streams', [])
        if len(stream) != 1 or stream[0].get('nb_read_frames') != str(COUNT) or stream[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera does not contain 600 decoded 20 Hz frames: ' + camera)
        if context['review_kind'] == 'original_source_review' and (stream[0].get('width'), stream[0].get('height')) != (1920, 1080):
            raise ValueError('Original camera resolution mismatch: ' + camera)
        hashes[name] = digest(path)
    if context.get('camera_sha256') != hashes:
        raise ValueError('Context is not bound to source camera bytes')
    for key in ('reviewer', 'intersection_boundary_source', 'route_origin_source', 'device_review_source',
                'turn_intent_review_source', 'control_state_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed context source: ' + key)
    if not context.get('ego_highway_id') or not context.get('priority_highway_id'):
        raise ValueError('Missing sourced highway identities')
    if context['ego_highway_id'] == context['priority_highway_id']:
        raise ValueError('Priority vehicle did not enter from a different highway')
    bounds = context.get('intersection_bounds_xy_m')
    if (not isinstance(bounds, list) or len(bounds) != 4 or not all(number(v) for v in bounds)
            or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise ValueError('Missing measured intersection boundary')
    for key in ('official_device_controls_intersection', 'signal_inoperative', 'opposite_approaches',
                'either_left_turning_or_intending'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing reviewed exclusion fact: ' + key)
    if context['official_device_controls_intersection'] and not context.get('device_type'):
        raise ValueError('Controlled intersection lacks device identity')
    expected_kind = 'synthetic_native_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_native_pose'
    ego_inside, priority_inside, times = [], [], []
    previous_native, previous_t = -1, -1.0
    for i, (frame, sample) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= previous_native:
            raise ValueError('Invalid original frame identity')
        if not number(t) or t <= previous_t or (i and abs(t - previous_t - .05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if sample.get('video_frame') != i or sample.get('native_frame') != native or sample.get('source_kind') != expected_kind:
            raise ValueError('Trace does not join original frame map/provenance')
        if sample.get('ego_highway_id') != context['ego_highway_id'] or sample.get('priority_highway_id') != context['priority_highway_id']:
            raise ValueError('Trace highway origin mismatch')
        for key in ('ego_x_m', 'ego_y_m', 'priority_x_m', 'priority_y_m'):
            if not number(sample.get(key)):
                raise ValueError('Missing original position: ' + key)
        for key in ('ego_speed_mps', 'priority_speed_mps'):
            if not number(sample.get(key)) or sample[key] < 0:
                raise ValueError('Missing finite source speed: ' + key)
        ego_inside.append(bounds[0] <= sample['ego_x_m'] <= bounds[2]
                          and bounds[1] <= sample['ego_y_m'] <= bounds[3])
        priority_inside.append(bounds[0] <= sample['priority_x_m'] <= bounds[2]
                               and bounds[1] <= sample['priority_y_m'] <= bounds[3])
        times.append(t)
        previous_native, previous_t = native, t
    if times[-1] - times[0] < 29.9:
        raise ValueError('Source span is less than 30 seconds')
    ego_entries = [i for i in range(1, COUNT) if not ego_inside[i-1] and ego_inside[i]]
    priority_entries = [i for i in range(1, COUNT) if not priority_inside[i-1] and priority_inside[i]]
    if not ego_entries or not priority_entries or ego_inside[0] or priority_inside[0]:
        raise ValueError('Both vehicles need observed outside-to-inside entry')
    ego_entry, priority_entry = ego_entries[0], priority_entries[0]
    if priority_entry >= ego_entry:
        raise ValueError('Priority vehicle did not enter first')
    overlap = [i for i in range(priority_entry, COUNT) if ego_inside[i] and priority_inside[i]]
    yield_window = range(priority_entry, ego_entry)
    min_ego_speed = min(trace[i]['ego_speed_mps'] for i in yield_window)
    return {
        'format': 'saved-intersection-priority-observation', 'assignment_id': ASSIGNMENT,
        'review_kind': context['review_kind'],
        'sources': {**{name: digest(path) for name, path in paths.items()}, **hashes},
        'sample_count': COUNT, 'sample_span_s': times[-1] - times[0],
        'priority_entry_video_frame': priority_entry, 'ego_entry_video_frame': ego_entry,
        'entry_gap_s': times[ego_entry] - times[priority_entry],
        'priority_present_at_ego_entry': priority_inside[ego_entry],
        'simultaneous_occupancy_frames': len(overlap),
        'ego_min_speed_between_entries_mps': min_ego_speed,
        'official_device_controls_intersection': context['official_device_controls_intersection'],
        'signal_inoperative': context['signal_inoperative'],
        'opposite_approaches': context['opposite_approaches'],
        'either_left_turning_or_intending': context['either_left_turning_or_intending'],
        'device_exclusion_context': context['official_device_controls_intersection'] and not context['signal_inoperative'],
        'opposite_left_turn_exclusion_context': context['opposite_approaches'] and context['either_left_turning_or_intending'],
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    Path(args.output_json).write_text(json.dumps(measure(args.source_dir), indent=2) + '\n')
