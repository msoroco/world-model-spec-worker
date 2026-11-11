"""Original-source entrance, approach and driveway observations for C111706.

The surveyed polygons and source-hashed asset are engineering references. This
module makes no legal finding about "in front", turning purpose or station status.
"""

import hashlib
import json
from math import hypot, isfinite, pi
from pathlib import Path
from types import SimpleNamespace

from fire_station_geometry import _overlap, classify_path, validate_entrance


SOURCES = ('station_survey.json', 'subject_original.jsonl',
           'other_original.jsonl', 'video_frames.jsonl', 'trace.jsonl')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _waypoint(row):
    xy = row.get('xy')
    if not isinstance(xy, list) or len(xy) != 2 or not all(
            isinstance(x, (int, float)) and isfinite(x) for x in xy):
        raise ValueError('survey waypoint needs finite original XY')
    return SimpleNamespace(road_id=row['road_id'], lane_id=row['lane_id'],
                           lane_width=row['lane_width'],
                           transform=SimpleNamespace(location=SimpleNamespace(
                               x=xy[0], y=xy[1])))


def _rows(path, name):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError('Original ' + name + ' needs at least three frames')
    return rows


def _corners(row):
    value = row.get('body_corners_xy')
    if not isinstance(value, list) or len(value) < 4 or any(
            not isinstance(point, list) or len(point) != 2 or
            not all(isinstance(x, (int, float)) and isfinite(x) for x in point)
            for point in value):
        raise ValueError('Original body corners missing or nonfinite')
    return value


def _segment_distance(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length2 = dx*dx+dy*dy
    if length2 == 0:
        return hypot(point[0]-a[0], point[1]-a[1])
    t = max(0., min(1., ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2))
    return hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy)


def _clearance(a, b):
    if _overlap(a, b):
        return 0.
    a_edges = list(zip(a, a[1:]+a[:1]))
    b_edges = list(zip(b, b[1:]+b[:1]))
    return min([_segment_distance(point, x, y) for point in a for x, y in b_edges] +
               [_segment_distance(point, x, y) for point in b for x, y in a_edges])


def measure(root):
    root = Path(root)
    paths = [root / name for name in SOURCES]
    if not paths[0].is_file():
        raise ValueError('Missing required source: station_survey.json')
    survey = json.loads(paths[0].read_text())
    geometry = validate_entrance(*(_waypoint(survey[name]) for name in
                                   ('public_before', 'public_at', 'public_after',
                                    'driveway_at')), source=survey.get('station_source'))
    subject, other, mapping, trace = (_rows(path, name) for path, name in
                                      zip(paths[1:], SOURCES[1:]))
    if not len(subject) == len(other) == len(mapping) == len(trace):
        raise ValueError('Original station participant/frame counts differ')
    frames = []
    subject_path = []
    clearances = []
    subject_id = other_id = None
    previous_frame = previous_time = None
    for index, (a, b, mapped, state) in enumerate(zip(subject, other, mapping, trace)):
        frame, time = a.get('frame'), a.get('time_s')
        if (type(frame) is not int or not isinstance(time, (int, float)) or
                not isfinite(time) or mapped.get('video_frame') != index or
                mapped.get('carla_frame') != frame or b.get('frame') != frame or
                state.get('frame') != frame or
                any(not isinstance(row.get('time_s'), (int, float)) or
                    abs(row['time_s']-time) > 1e-6 for row in (b, mapped, state))):
            raise ValueError('Original station participant/frame/time join differs')
        if previous_frame is not None and (frame != previous_frame+1 or
                                           abs(time-previous_time-.05) > 1e-4):
            raise ValueError('Original station capture is not consecutive 20 Hz')
        previous_frame, previous_time = frame, time
        if subject_id is None:
            subject_id, other_id = a.get('native_actor_id'), b.get('native_actor_id')
            if subject_id is None or other_id is None or subject_id == other_id:
                raise ValueError('Distinct original Native participants required')
        if a.get('native_actor_id') != subject_id or b.get('native_actor_id') != other_id:
            raise ValueError('Original station participant identity changed')
        center = a.get('center_xy')
        if not isinstance(center, list) or len(center) != 2 or not all(
                isinstance(x, (int, float)) and isfinite(x) for x in center):
            raise ValueError('Original subject center missing')
        heading = a.get('heading_deg')
        if not isinstance(heading, (int, float)) or not isfinite(heading):
            raise ValueError('Original subject heading missing')
        corners_a, corners_b = _corners(a), _corners(b)
        frames.append(frame)
        subject_path.append({'frame': frame, 'x_m': center[0], 'y_m': center[1],
                             'heading_rad': heading*pi/180,
                             'lane_id': (a.get('road_id'), a.get('lane_id')),
                             'body_vertices_xy': corners_a})
        clearances.append({'frame': frame, 'time_s': time,
                           'ground_body_clearance_m': _clearance(corners_a, corners_b)})
    observed = classify_path(subject_path, geometry)
    distance = sum(hypot(b['x_m']-a['x_m'], b['y_m']-a['y_m'])
                   for a, b in zip(subject_path, subject_path[1:]))
    return {
        'format': 'fire-station-original-measurement-v1',
        'law_id': 'LVMC-11-12-060', 'cell_id': 'C111706',
        'geometry': geometry, 'path': observed,
        'subject_path_length_m': distance,
        'other_vehicle_min_ground_body_clearance_m': min(
            row['ground_body_clearance_m'] for row in clearances),
        'clearance_samples': clearances,
        'first_frame': frames[0], 'last_frame': frames[-1],
        'last_time_s': previous_time,
        'subject_actor_id': subject_id, 'other_actor_id': other_id,
        'station_identity': 'unreviewed', 'turning_purpose': 'unreviewed',
        'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False,
        'source_refs': [{'path': name, 'sha256': _sha(path)}
                        for name, path in zip(SOURCES, paths)],
    }
