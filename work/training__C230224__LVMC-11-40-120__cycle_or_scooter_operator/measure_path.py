"""Measure rider/device occupancy from saved Native trace and reviewed path geometry."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from shapely.geometry import Polygon

AID = 'training__C230224__LVMC-11-40-120__cycle_or_scooter_operator'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def polygon(points, name):
    if not isinstance(points, list) or len(points) < 3 or any(
            not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
            for p in points):
        raise ValueError('Invalid reviewed polygon: ' + name)
    shape = Polygon(points)
    if not shape.is_valid or shape.area <= 0:
        raise ValueError('Invalid reviewed polygon: ' + name)
    return shape


def measure(root):
    root = Path(root)
    paths = {name: root/name for name in ('video_frames.jsonl', 'native_rider_trace.jsonl', 'path_context.json')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing saved source: ' + name)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_rider_trace.jsonl'])
    context = json.loads(paths['path_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original frames')
    kind = context.get('review_kind')
    if context.get('assignment_id') != AID or kind not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    hashes = {}
    for name in CAMERAS:
        path = root/(name+'.mkv')
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing source camera: ' + name)
        run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                              '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(path)],
                             capture_output=True, text=True)
        if run.returncode:
            raise ValueError('Source camera decode failed: ' + name)
        streams = json.loads(run.stdout).get('streams', [])
        wanted = (1920, 1080) if name == 'overview' else (1280, 720)
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: ' + name)
        if kind == 'original_source_review' and (streams[0].get('width'), streams[0].get('height')) != wanted:
            raise ValueError('Original camera resolution mismatch: ' + name)
        hashes[path.name] = sha(path)
    if context.get('camera_sha256') != hashes:
        raise ValueError('Context not bound to source camera bytes')
    for key in ('reviewer', 'device_subtype_source', 'rider_identity_source', 'path_surface_source',
                'path_continuity_source', 'path_adjacency_source', 'path_obstruction_source',
                'path_usability_review_source', 'roadway_boundary_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed context source: ' + key)
    if context.get('device_subtype') not in ('bicycle', 'electric_bicycle', 'electric_scooter'):
        raise ValueError('Unsupported rider device subtype')
    for key in ('path_continuous', 'path_adjacent', 'path_usable_reviewed'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing reviewed path fact: ' + key)
    authored = context.get('path_context')
    if not isinstance(authored, dict) or any(authored.get(key) != context[key]
            for key in ('path_continuous', 'path_adjacent', 'path_usable_reviewed')):
        raise ValueError('Authored path context differs from reviewed source facts')
    path_poly = polygon(context.get('path_polygon_xy_m'), 'adjacent path')
    road_poly = polygon(context.get('roadway_polygon_xy_m'), 'roadway')
    obstruction = polygon(context.get('path_obstruction_polygon_xy_m'), 'path obstruction')
    if path_poly.intersection(road_poly).area > 1e-6:
        raise ValueError('Path and roadway reviewed geometry overlap')
    expected = 'synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_pose'
    rider_id, device_id = context.get('rider_actor_id'), context.get('device_actor_id')
    if type(rider_id) is not int or type(device_id) is not int or rider_id == device_id:
        raise ValueError('Missing distinct source participant IDs')
    prev_frame, prev_t = -1, -1.0
    path_frames = road_frames = outside_frames = moving_frames = 0
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= prev_frame:
            raise ValueError('Invalid original frame identity')
        if type(t) not in (int, float) or not math.isfinite(t) or t <= prev_t or (i and abs(t-prev_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if (row.get('video_frame') != i or row.get('native_frame') != native or row.get('source_kind') != expected or
                row.get('rider_actor_id') != rider_id or row.get('device_actor_id') != device_id):
            raise ValueError('Rider trace does not join original frame, actors or provenance')
        speed = row.get('device_speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Invalid Native rider speed')
        footprint = polygon(row.get('device_footprint_xy_m'), 'device footprint')
        path_hit = footprint.intersection(path_poly).area > 1e-6
        road_hit = footprint.intersection(road_poly).area > 1e-6
        if speed > .1:
            moving_frames += 1
            path_frames += path_hit
            road_frames += road_hit
            outside_frames += not (path_hit or road_hit)
        prev_frame, prev_t = native, t
    if prev_t-frames[0]['time_s'] < 29.9 or moving_frames == 0:
        raise ValueError('No 30-second moving rider observation')
    return {'format': 'saved-adjacent-path-observation', 'assignment_id': AID, 'review_kind': kind,
            'sources': {**{name: sha(p) for name, p in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': prev_t-frames[0]['time_s'],
            'device_subtype': context['device_subtype'], 'moving_frame_count': moving_frames,
            'path_occupancy_moving_frames': path_frames, 'roadway_occupancy_moving_frames': road_frames,
            'outside_both_moving_frames': outside_frames,
            'path_obstruction_intersection_area_m2': path_poly.intersection(obstruction).area,
            'path_continuous_reviewed': context['path_continuous'],
            'path_adjacent_reviewed': context['path_adjacent'],
            'path_usable_reviewed': context['path_usable_reviewed'],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(measure(args.source_dir), indent=2)+'\n')
