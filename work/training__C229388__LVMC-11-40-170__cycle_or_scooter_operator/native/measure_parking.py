"""Saved-source geometry for a parked cycle or scooter; no legal conclusion."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from shapely.geometry import Polygon

AID = 'training__C229388__LVMC-11-40-170__cycle_or_scooter_operator'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def polygon(points, name):
    if not isinstance(points, list) or len(points) < 3 or any(
            not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
            for p in points):
        raise ValueError('Invalid source polygon: ' + name)
    result = Polygon(points)
    if not result.is_valid or result.area <= 0:
        raise ValueError('Invalid source polygon: ' + name)
    return result


def measure(root):
    root = Path(root)
    paths = {n: root / n for n in ('video_frames.jsonl', 'native_parking_trace.jsonl', 'parking_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: ' + name)
    frames, trace = rows(paths['video_frames.jsonl']), rows(paths['native_parking_trace.jsonl'])
    context = json.loads(paths['parking_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original frames')
    kind = context.get('review_kind')
    if context.get('assignment_id') != AID or kind not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    hashes = {}
    for name in CAMERAS:
        path = root / ('camera_' + name + '.mkv')
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing source camera: ' + name)
        run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                              '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(path)],
                             capture_output=True, text=True)
        if run.returncode:
            raise ValueError('Source camera decode failed: ' + name)
        streams = json.loads(run.stdout).get('streams', [])
        wanted = (1920, 1080) if name == 'forward' else (1280, 720)
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: ' + name)
        if kind == 'original_source_review' and (streams[0].get('width'), streams[0].get('height')) != wanted:
            raise ValueError('Original camera resolution mismatch: ' + name)
        hashes[path.name] = sha(path)
    if context.get('camera_sha256') != hashes:
        raise ValueError('Context not bound to source camera bytes')
    for key in ('reviewer', 'device_subtype_source', 'rack_support_source', 'sidewalk_geometry_source',
                'pedestrian_corridor_source', 'operator_join_source', 'parking_state_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed context source: ' + key)
    if context.get('device_subtype') not in ('bicycle', 'electric_bicycle', 'electric_scooter'):
        raise ValueError('Unsupported parked device subtype')
    if type(context.get('rack_support_confirmed')) is not bool:
        raise ValueError('Missing rack support review')
    sidewalk = polygon(context.get('sidewalk_polygon_xy_m'), 'sidewalk')
    rack = polygon(context.get('rack_polygon_xy_m'), 'rack')
    corridor = polygon(context.get('pedestrian_corridor_polygon_xy_m'), 'pedestrian corridor')
    expected = 'synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_pose'
    previous_frame, previous_t = -1, -1.0
    rest, rack_overlap, corridor_overlap, corridor_gap, sidewalk_overlap = [], [], [], [], []
    operator_id = context.get('operator_actor_id')
    device_id = context.get('device_actor_id')
    if type(operator_id) is not int or type(device_id) is not int or operator_id == device_id:
        raise ValueError('Missing distinct source participant IDs')
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= previous_frame:
            raise ValueError('Invalid original frame identity')
        if type(t) not in (int, float) or not math.isfinite(t) or t <= previous_t or (i and abs(t-previous_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if (row.get('video_frame') != i or row.get('native_frame') != native or
                row.get('source_kind') != expected or row.get('device_actor_id') != device_id or
                row.get('operator_actor_id') != operator_id):
            raise ValueError('Parking trace does not join original frame, actors or provenance')
        speed = row.get('device_speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Invalid Native device speed')
        footprint = polygon(row.get('device_footprint_xy_m'), 'device footprint')
        rest.append(speed <= .05)
        rack_overlap.append(footprint.intersection(rack).area)
        corridor_overlap.append(footprint.intersection(corridor).area)
        corridor_gap.append(footprint.distance(corridor))
        sidewalk_overlap.append(footprint.intersection(sidewalk).area)
        previous_frame, previous_t = native, t
    if previous_t - frames[0]['time_s'] < 29.9:
        raise ValueError('Source span less than 30 seconds')
    at_rest = [i for i, value in enumerate(rest) if value]
    if not at_rest:
        raise ValueError('No parked episode')
    return {'format': 'saved-cycle-parking-observation', 'assignment_id': AID, 'review_kind': kind,
            'sources': {**{name: sha(path) for name, path in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': previous_t-frames[0]['time_s'],
            'device_subtype': context['device_subtype'], 'rack_support_confirmed': context['rack_support_confirmed'],
            'rest_frame_count': len(at_rest), 'rack_intersection_frame_count': sum(rack_overlap[i] > 0 for i in at_rest),
            'pedestrian_corridor_intersection_frame_count': sum(corridor_overlap[i] > 0 for i in at_rest),
            'minimum_corridor_gap_m_at_rest': min(corridor_gap[i] for i in at_rest),
            'sidewalk_intersection_frame_count': sum(sidewalk_overlap[i] > 0 for i in at_rest),
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(measure(args.source_dir), indent=2) + '\n')
