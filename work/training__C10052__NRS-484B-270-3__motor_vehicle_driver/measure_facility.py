"""Source-bound stopped-body occupancy; does not infer statutory exceptions."""
import hashlib
import json
import math
from pathlib import Path

RATE_HZ = 20
MIN_STOP_FRAMES = 40
EXCEPTIONS = ('entering_or_exiting_alley_or_driveway', 'disabled_vehicle',
              'avoiding_traffic_conflict', 'official_duties',
              'police_direction', 'emergency')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rectangle(value, name):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Missing ' + name)
    box = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in box) or not (box[0] < box[2] and box[1] < box[3]):
        raise ValueError('Invalid ' + name)
    return box


def _clip(vertices, axis, limit, keep_greater):
    if not vertices:
        return []
    result = []
    before = vertices[-1]
    def inside(point):
        return point[axis] >= limit-1e-9 if keep_greater else point[axis] <= limit+1e-9
    for current in vertices:
        if inside(current) != inside(before):
            delta = current[axis]-before[axis]
            factor = (limit-before[axis])/delta
            result.append((before[0]+factor*(current[0]-before[0]),
                           before[1]+factor*(current[1]-before[1])))
        if inside(current):
            result.append(current)
        before = current
    return result


def overlap_area(body, box):
    if not isinstance(body, list) or len(body) != 4:
        raise ValueError('Missing original full body')
    points = []
    for vertex in body:
        if not isinstance(vertex, list) or len(vertex) != 2:
            raise ValueError('Invalid original body vertex')
        p = tuple(float(v) for v in vertex)
        if not all(math.isfinite(v) for v in p):
            raise ValueError('Nonfinite original body vertex')
        points.append(p)
    if len({(round(x, 8), round(y, 8)) for x, y in points}) != 4:
        raise ValueError('Degenerate original body')
    cross = [(points[(i+1)%4][0]-points[i][0]) *
             (points[(i+2)%4][1]-points[(i+1)%4][1]) -
             (points[(i+1)%4][1]-points[i][1]) *
             (points[(i+2)%4][0]-points[(i+1)%4][0]) for i in range(4)]
    if not (all(v > 1e-8 for v in cross) or all(v < -1e-8 for v in cross)):
        raise ValueError('Invalid original body winding')
    clipped = points
    for axis, limit, keep_greater in ((0, box[0], True), (0, box[2], False),
                                      (1, box[1], True), (1, box[3], False)):
        clipped = _clip(clipped, axis, limit, keep_greater)
    if len(clipped) < 3:
        return 0.0
    return abs(sum(a[0]*b[1]-b[0]*a[1]
                   for a, b in zip(clipped, clipped[1:]+clipped[:1])))/2


def measure(samples_path, geometry_path, exception_path):
    paths = [Path(samples_path), Path(geometry_path), Path(exception_path)]
    for path in paths:
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    geometry = json.loads(paths[1].read_text())
    facility = rectangle(geometry.get('bicycle_facility_native_xy_bounds_m'), 'bicycle facility bounds')
    alley = rectangle(geometry.get('alley_entrance_native_xy_bounds_m'), 'alley entrance bounds')
    if type(geometry.get('road_id')) is not int or type(geometry.get('driving_lane_id')) is not int:
        raise ValueError('Missing Native road/lane identity')
    if type(geometry.get('bicycle_lane_id')) is not int:
        raise ValueError('Missing Native bicycle lane identity')
    context = json.loads(paths[2].read_text())
    if set(context.get('exceptions', {})) != set(EXCEPTIONS):
        raise ValueError('Incomplete statutory exception fields')
    if context.get('source_kind') != 'synthetic_scene_request':
        raise ValueError('Unrecognized exception source kind')
    if any(type(context['exceptions'][key]) is not bool for key in EXCEPTIONS):
        raise ValueError('Invalid statutory exception value')
    rows = [json.loads(s) for s in paths[0].read_text().splitlines() if s.strip()]
    if len(rows) < MIN_STOP_FRAMES:
        raise ValueError('Too few original Native samples')
    stopped = []
    areas = []
    frames = []
    times = []
    for row in rows:
        frame, time, speed = row.get('native_frame'), row.get('time_s'), row.get('speed_mps')
        if type(frame) is not int or frame < 0 or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Invalid original frame/time')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Invalid original speed')
        if frames and (frame <= frames[-1] or time <= times[-1] or abs(time-times[-1]-1/RATE_HZ) > .002):
            raise ValueError('Original frame/time order or rate invalid')
        if row.get('native_road_id') != geometry['road_id']:
            raise ValueError('Wrong original road identity')
        if row.get('native_lane_id') not in (geometry['driving_lane_id'], geometry['bicycle_lane_id']):
            raise ValueError('Wrong original lane identity')
        forward = row.get('native_forward_xy')
        if not isinstance(forward, list) or len(forward) != 2 or not all(
                type(v) in (int, float) and math.isfinite(v) for v in forward) or abs(
                    math.hypot(*forward)-1) > .01:
            raise ValueError('Invalid original heading')
        frames.append(frame)
        times.append(time)
        stopped.append(speed <= .1)
        areas.append(overlap_area(row.get('native_body_xy_m'), facility))
    intervals = []
    start = None
    for i, flag in enumerate(stopped + [False]):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            if i-start >= MIN_STOP_FRAMES:
                intervals.append((start, i))
            start = None
    if not intervals:
        raise ValueError('No observed stationary interval')
    a, b = max(intervals, key=lambda pair: pair[1]-pair[0])
    max_area = max(areas[a:b])
    return {'format': 'c10052-facility-occupancy-observation-v1',
            'source_sha256': {path.name: sha(path) for path in paths},
            'original_frames': len(rows), 'stop_first_frame': frames[a],
            'stop_last_frame': frames[b-1], 'stop_duration_s': round((b-a)/RATE_HZ, 5),
            'max_stopped_overlap_m2': round(max_area, 6),
            'mean_stopped_overlap_m2': round(sum(areas[a:b])/(b-a), 6),
            'requested_exceptions': context['exceptions'],
            'observed_exception_status': 'unresolved',
            'native_facility_design_verified': geometry.get('native_facility_design_verified') is True,
            'yield_duty_measured': False, 'legal_verdict_claimed': False,
            'alley_entrance_bounds_m': alley}
