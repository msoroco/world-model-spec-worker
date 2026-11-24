"""Saved-source route topology and enroute-purpose observation; no legal verdict."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID = 'training__C394566__LVMC-11-48-060__motor_vehicle_driver'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(root):
    root = Path(root)
    paths = {name: root/name for name in ('video_frames.jsonl', 'native_route_trace.jsonl', 'route_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: '+name)
    frames, trace = rows(paths['video_frames.jsonl']), rows(paths['native_route_trace.jsonl'])
    context = json.loads(paths['route_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original frames')
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
    for key in ('reviewer', 'truck_blueprint_source', 'truck_route_designation_source',
                'nontruck_street_designation_source', 'route_connectivity_source',
                'enroute_purpose_source', 'served_premises_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed route source: '+key)
    ids = [context.get(key) for key in ('entry_truck_route_id', 'intervening_street_id', 'exit_truck_route_id')]
    if any(type(value) is not int for value in ids) or len(set(ids)) != 3:
        raise ValueError('Invalid distinct reviewed route IDs')
    if context.get('enroute_purpose') not in ('none', 'pickup', 'delivery', 'essential'):
        raise ValueError('Unreviewed enroute purpose')
    if type(context.get('vehicle_is_truck')) is not bool:
        raise ValueError('Unreviewed truck class')
    expected = 'synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_pose'
    previous_frame, previous_t = -1, -1.0
    road_sequence, path_length, stationary_frames = [], 0.0, 0
    previous_xy = None
    vehicle_id = context.get('ego_actor_id')
    if type(vehicle_id) is not int:
        raise ValueError('Missing source vehicle identity')
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= previous_frame:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= previous_t or (i and abs(t-previous_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if (row.get('video_frame') != i or row.get('native_frame') != native or
                row.get('source_kind') != expected or row.get('ego_actor_id') != vehicle_id):
            raise ValueError('Route trace does not join original frame, vehicle or provenance')
        for key in ('ego_x_m', 'ego_y_m', 'ego_speed_mps'):
            if not finite(row.get(key)):
                raise ValueError('Missing finite Native route measurement: '+key)
        if row['ego_speed_mps'] < 0 or type(row.get('road_id')) is not int:
            raise ValueError('Invalid Native road or speed')
        xy = (row['ego_x_m'], row['ego_y_m'])
        if previous_xy is not None:
            step = math.dist(previous_xy, xy)
            if step > 5.0:
                raise ValueError('Implausible interframe route jump')
            path_length += step
        previous_xy = xy
        if not road_sequence or road_sequence[-1] != row['road_id']:
            road_sequence.append(row['road_id'])
        stationary_frames += row['ego_speed_mps'] <= .05
        previous_frame, previous_t = native, t
    if previous_t-frames[0]['time_s'] < 29.9:
        raise ValueError('Source span less than 30 seconds')
    complete = road_sequence == ids
    return {'format': 'saved-truck-through-route-observation', 'assignment_id': AID,
            'review_kind': kind, 'sources': {**{name: sha(path) for name, path in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': previous_t-frames[0]['time_s'],
            'observed_road_sequence': road_sequence, 'reviewed_route_ids': ids,
            'complete_truck_to_truck_passage': complete, 'observed_path_length_m': path_length,
            'stationary_frame_count': stationary_frames, 'vehicle_is_truck_reviewed': context['vehicle_is_truck'],
            'enroute_purpose_reviewed': context['enroute_purpose'],
            'purpose_inferred_from_stop': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(measure(args.source_dir), indent=2)+'\n')
