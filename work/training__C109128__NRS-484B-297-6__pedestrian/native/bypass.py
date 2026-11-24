"""Synthetic sidewalk-obstruction source and source-only measurements; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CONTEXT_ID = 'c109128-sidewalk-obstruction-v1'
PATH_Y = {'condition_a': 1.55, 'condition_b': 1.15}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _clip(x):
    return max(0.0, min(1.0, x))


def requested(condition):
    if condition not in PATH_Y:
        raise ValueError('Unknown bypass condition')
    rows = []
    for frame in range(FRAMES):
        x = round(5.0 + 1.5 * frame / RATE_HZ, 6)
        # Both conditions enter before x=20 and return after x=30.
        if frame < 170:
            y = 3.2
        elif frame < 200:
            y = 3.2 + (PATH_Y[condition] - 3.2) * _clip((frame - 170) / 30)
        elif frame < 370:
            y = PATH_Y[condition]
        elif frame < 400:
            y = PATH_Y[condition] + (3.2 - PATH_Y[condition]) * _clip((frame - 370) / 30)
        else:
            y = 3.2
        y = round(y, 6)
        footprint = [[round(x + dx, 6), round(y + dy, 6)]
                     for dx, dy in ((-.16, -.16), (-.16, .16), (.16, -.16), (.16, .16))]
        rows.append({'frame': frame, 'time_s': frame / RATE_HZ,
                     'pedestrian_xy_m': [x, y], 'footprint_xy_m': footprint,
                     'context_id': CONTEXT_ID, 'requested_bypass_path': condition,
                     'sidewalk_id': 'sidewalk_north', 'adjacent_highway_id': 'highway_south',
                     'obstruction_id': 'blocked_sidewalk_20_30',
                     'source_kind': 'synthetic_scene_request',
                     'original_native_observed': False, 'legal_verdict': None})
    return rows


def measure(source, context):
    source, context = Path(source), Path(context)
    if not source.is_file() or not context.is_file():
        raise ValueError('Source or context missing')
    scene = json.loads(context.read_text())
    if (scene.get('context_id') != CONTEXT_ID or
            scene.get('sidewalk_y_min_m') != 2.0 or
            scene.get('roadway_y_range_m') != [0.0, 2.0] or
            scene.get('obstruction_x_range_m') != [20.0, 30.0] or
            scene.get('obstruction_y_range_m') != [2.0, 4.0] or
            scene.get('physical_obstruction_verified') is not False or
            scene.get('bicycle_lane_designation_verified') is not False or
            scene.get('first_practicable_return_verified') is not False):
        raise ValueError('Scene geometry or authority changed')
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Exact 600-frame source required')
    paths = set()
    road_frames = []
    post_obstruction_sidewalk = []
    path_length = 0.0
    previous = None
    for index, row in enumerate(rows):
        center, footprint = row.get('pedestrian_xy_m'), row.get('footprint_xy_m')
        if (row.get('frame') != index or row.get('time_s') != index / RATE_HZ or
                row.get('context_id') != CONTEXT_ID or
                row.get('sidewalk_id') != 'sidewalk_north' or
                row.get('adjacent_highway_id') != 'highway_south' or
                row.get('obstruction_id') != 'blocked_sidewalk_20_30' or
                row.get('source_kind') != 'synthetic_scene_request' or
                row.get('original_native_observed') is not False or
                row.get('legal_verdict') is not None or
                row.get('requested_bypass_path') not in PATH_Y):
            raise ValueError('Frame or scene identity changed')
        if (not isinstance(center, list) or len(center) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in center) or
                not isinstance(footprint, list) or len(footprint) != 4 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                    for point in footprint)):
            raise ValueError('Center or footprint missing')
        expected = [[round(center[0] + dx, 6), round(center[1] + dy, 6)]
                    for dx, dy in ((-.16, -.16), (-.16, .16), (.16, -.16), (.16, .16))]
        if footprint != expected:
            raise ValueError('Center and footprint disagree')
        if previous is not None:
            step = math.dist(previous, center)
            if step > 0.12:
                raise ValueError('Pedestrian motion discontinuity')
            path_length += step
        previous = center
        paths.add(row['requested_bypass_path'])
        if 0.0 <= center[1] < 2.0:
            road_frames.append(index)
        if center[0] > 30.16 and center[1] >= 2.16:
            post_obstruction_sidewalk.append(index)
        if 19.84 <= center[0] <= 30.16 and center[1] >= 2.0:
            raise ValueError('Footprint center crosses authored sidewalk obstruction')
    if len(paths) != 1 or rows != requested(next(iter(paths))):
        raise ValueError('Authored bypass path changed or mixed')
    if not road_frames or not post_obstruction_sidewalk:
        raise ValueError('No road entry or sidewalk return')
    path = next(iter(paths))
    return {'format': 'c109128-bypass-source-measurement-v1',
            'frames': FRAMES, 'rate_hz': RATE_HZ, 'duration_s': 30,
            'requested_bypass_path': path,
            'first_road_center_frame': min(road_frames),
            'last_road_center_frame': max(road_frames),
            'first_post_obstruction_sidewalk_center_frame': min(post_obstruction_sidewalk),
            'road_center_frames': len(road_frames),
            'bypass_y_center_m': PATH_Y[path],
            'distance_to_road_edge_at_bypass_center_m': round(2.0 - PATH_Y[path], 6),
            'path_length_m': round(path_length, 6),
            'source_sha256': {source.name: sha(source), context.name: sha(context)},
            'physical_obstruction_verified': False,
            'first_practicable_return_verified': False,
            'due_care_verified': False,
            'legal_verdict_claimed': False}
