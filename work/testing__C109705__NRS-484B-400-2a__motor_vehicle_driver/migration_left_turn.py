"""Saved C109705 physical motion evidence, distinct from legal acceptance.

The predicates describe this authored connected route. They do not define
statutory entry, centerline proximity, safety, or legal compliance.
"""
import hashlib
import json
import math
from pathlib import Path

LT_REQUIRED = ('road_geometry.json', 'body_history.jsonl', 'video_frames.jsonl')

def lt_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def lt_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def assess_left_turn(attempt):
    """Return a source-bound physical maneuver assessment and realized observations."""
    root = Path(attempt)
    paths = {name: root / name for name in LT_REQUIRED}
    sources = {name: lt_sha(path) for name, path in paths.items() if path.is_file()}
    if (root / 'config.json').is_file():
        sources['config.json'] = lt_sha(root / 'config.json')
    method = 'c109705_ordered_approach_connector_departure_full_body_clearance'
    available_intervals = []
    try:
        available_map = lt_rows(paths['video_frames.jsonl'])
        if available_map:
            available_intervals = [{'start_frame': available_map[0]['carla_frame'],
                                    'end_frame': available_map[-1]['carla_frame'],
                                    'start_time_s': available_map[0]['time_s'],
                                    'end_time_s': available_map[-1]['time_s']}]
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    def outcome(status, detail, intervals=(), observed=None):
        return {'status': status, 'method': method, 'intervals': list(intervals) or list(available_intervals),
                'sources': dict(sources), 'observed': observed or {}, 'missing': [],
                'detail': detail, 'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        result = outcome('unverified', 'Missing required original evidence: ' + ', '.join(missing))
        result['missing'] = missing
        return result
    try:
        from shapely.geometry import MultiPoint, Polygon
        geometry = json.loads(paths['road_geometry.json'].read_text())
        rows, mapping = lt_rows(paths['body_history.jsonl']), lt_rows(paths['video_frames.jsonl'])
        if not rows or not mapping:
            raise ValueError('Empty original body history or frame map')
        if len(rows) != len(mapping):
            raise ValueError('Body history does not cover every original frame')
        polygon = Polygon(geometry['intersection_xy_m'])
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError('Invalid authored intersection polygon')
        road_ids = [geometry[k] for k in ('approach_road_id', 'connector_road_id', 'departure_road_id')]
        if len(set(road_ids)) != 3 or geometry.get('two_way') is not True:
            raise ValueError('Connected two-directional road identity missing')
        direction = geometry['departure_direction_xy']
        if len(direction) != 2 or not all(math.isfinite(v) for v in direction) or math.hypot(*direction) == 0:
            raise ValueError('Departure roadway direction missing')
        for i, (row, frame) in enumerate(zip(rows, mapping)):
            if row['frame'] != frame['carla_frame'] or frame['video_frame'] != i:
                raise ValueError('Original frame identity join differs')
            if not math.isfinite(row['time_s']) or abs(row['time_s'] - frame['time_s']) > .0001:
                raise ValueError('Original timestamp join differs')
            if i and (row['frame'] <= rows[i - 1]['frame'] or row['time_s'] <= rows[i - 1]['time_s']):
                raise ValueError('Original chronology is not strictly increasing')
            if len(row['body_vertices_m']) < 4 or any(len(v) < 3 or not all(math.isfinite(n) for n in v) for v in row['body_vertices_m']):
                raise ValueError('Incomplete full-body vertices')
            if row.get('road_id') is None:
                raise ValueError('Native roadway identity unavailable')
        intervals = [{'start_frame': rows[0]['frame'], 'end_frame': rows[-1]['frame'],
                      'start_time_s': rows[0]['time_s'], 'end_time_s': rows[-1]['time_s']}]
        hulls = [MultiPoint([v[:2] for v in r['body_vertices_m']]).convex_hull for r in rows]
        centers = [[sum(v[d] for v in r['body_vertices_m']) / len(r['body_vertices_m']) for d in (0, 1)] for r in rows]
        approach = [i for i, r in enumerate(rows) if r['road_id'] == road_ids[0]]
        connectors = [i for i, r in enumerate(rows) if r['road_id'] == road_ids[1] and hulls[i].intersects(polygon)]
        clear_departures = [i for i, r in enumerate(rows) if r['road_id'] == road_ids[2] and not hulls[i].intersects(polygon)]
        ordered = bool(approach and clear_departures) and any(approach[0] < c < clear_departures[-1] for c in connectors)
        # Positive downstream movement must be observed after entering the
        # connector; no duration/position epsilon is used as a legal threshold.
        downstream_progress = max((sum((centers[d][k] - centers[c][k]) * direction[k] for k in (0, 1))
                                   for c in connectors for d in clear_departures if c < d), default=0)
        complete = bool(ordered) and downstream_progress > 0
        observed = {'native_road_id_history': [{'frame': r['frame'], 'time_s': r['time_s'], 'road_id': r['road_id']} for r in rows],
                    'body_junction_overlap': [{'frame': r['frame'], 'intersects': hulls[i].intersects(polygon)} for i, r in enumerate(rows)],
                    'clear_departure_frames': [rows[i]['frame'] for i in clear_departures],
                    'downstream_progress_projection_m': downstream_progress,
                    'observed_motion': any(centers[i] != centers[i - 1] for i in range(1, len(centers)))}
        result = outcome('met' if complete else 'not_met',
                         'Ordered approach, connector interaction and full-body downstream clearance observed.' if complete else
                         'Valid original history does not establish the complete ordered route and downstream clearance.', intervals, observed)
        return result
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        return outcome('unverified', str(error))
