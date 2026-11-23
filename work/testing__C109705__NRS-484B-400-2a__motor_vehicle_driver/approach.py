"""Source-bound approach geometry for NRS 484B.400(2)(a).

Distances describe observed body position; no distance is a legal cutoff.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def _finite_pair(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError('missing finite ' + label)
    return value


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = math.hypot(dx, dy)
    if norm < 1:
        raise ValueError('degenerate approach centerline')
    return dx / norm, dy / norm


def validate_context(context):
    """Require two opposed lanes on each intersecting road, with a left-turn route."""
    if context.get('law_id') != 'NRS-484B-400-2a' or context.get('cell_id') != 'C109705':
        raise ValueError('wrong frozen law/cell')
    if context.get('maneuver') != 'left_turn' or context.get('control') != 'centerline':
        raise ValueError('wrong fixed maneuver/control')
    if context.get('public_highway_source') is None:
        raise ValueError('public-highway source missing')
    roads = context.get('intersecting_roads')
    if not isinstance(roads, list) or len(roads) != 2:
        raise ValueError('both intersecting highways required')
    for road in roads:
        if not road.get('road_id') or road.get('alley') is not False:
            raise ValueError('road identity or non-alley source missing')
        lanes = road.get('lanes')
        if not isinstance(lanes, list) or len(lanes) < 2:
            raise ValueError('two-directional lane inventory missing')
        directions = []
        for lane in lanes:
            directions.append(_unit(_finite_pair(lane.get('from_xy_m'), 'lane start'),
                                    _finite_pair(lane.get('to_xy_m'), 'lane end')))
        if not any(a[0] * b[0] + a[1] * b[1] < -.95
                   for a in directions for b in directions):
            raise ValueError('opposing permitted directions missing')
    if context.get('approach_road_id') == context.get('departure_road_id'):
        raise ValueError('left turn must enter intersecting road')
    ids = {road['road_id'] for road in roads}
    if {context.get('approach_road_id'), context.get('departure_road_id')} != ids:
        raise ValueError('approach/departure road mismatch')
    line = context.get('approach_centerline_xy_m')
    if not isinstance(line, list) or len(line) != 2:
        raise ValueError('approach centerline source missing')
    a, b = (_finite_pair(point, 'centerline point') for point in line)
    direction = _unit(a, b)
    if type(context.get('approach_half_width_m')) not in (int, float) or context['approach_half_width_m'] <= 2:
        raise ValueError('approach right-half edge missing')
    if context.get('centerline_kind') not in ('marked', 'imaginary_equidistant'):
        raise ValueError('marked or imaginary centerline source missing')
    return a, direction


def body_position(context, vertices):
    """Right-normal signed body offsets from an oriented approach centerline."""
    a, direction = validate_context(context)
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError('original full-body footprint missing')
    offsets = []
    for vertex in vertices:
        x, y = _finite_pair(vertex, 'body vertex')
        offsets.append(direction[1] * (x - a[0]) - direction[0] * (y - a[1]))
    half = context['approach_half_width_m']
    return {'nearest_body_edge_to_centerline_m': min(offsets),
            'farthest_body_edge_from_centerline_m': max(offsets),
            'all_body_in_right_half': min(offsets) >= 0 and max(offsets) <= half}


def _verified(attempt, name, acquisition):
    path = attempt / name
    declared = acquisition.get(name, {})
    if not path.is_file() or declared.get('kind') != 'original_native':
        raise ValueError('missing original Native source: ' + name)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != declared.get('sha256'):
        raise ValueError('stale original Native source: ' + name)
    return path, actual


def measure(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    context_path, context_hash = _verified(attempt, 'intersection-context.json', acquisition)
    history_path, history_hash = _verified(attempt, 'approach-history.jsonl', acquisition)
    context = json.loads(context_path.read_text())
    validate_context(context)
    rows = [json.loads(line) for line in history_path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError('original approach history too short')
    previous = None
    approach = []
    for row in rows:
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError('invalid original frame/time')
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > .005):
            raise ValueError('missing or non-20-Hz original approach frame')
        previous = (frame, time_s)
        if row.get('road_id') == context['approach_road_id'] and row.get('phase') == 'approach':
            position = body_position(context, row.get('ego_body_vertices_xy_m'))
            approach.append({'frame': frame, 'time_s': time_s, **position})
    if len(approach) < 2:
        raise ValueError('pre-entry approach body samples missing')
    return {'format': 'worker-400-2a-approach-measurement',
            'approach_frames': [row['frame'] for row in approach],
            'nearest_body_edge_range_m': [min(row['nearest_body_edge_to_centerline_m'] for row in approach),
                                          max(row['nearest_body_edge_to_centerline_m'] for row in approach)],
            'all_sampled_body_in_right_half': all(row['all_body_in_right_half'] for row in approach),
            'body_history': approach,
            'centerline_kind': context['centerline_kind'],
            'source_sha256': {'intersection-context.json': context_hash,
                              'approach-history.jsonl': history_hash},
            'legal_nearest_portion_verdict': 'unresolved'}


def compare(left, right):
    """Reject changed fixed context and report only measured lateral difference."""
    a, b = (json.loads(Path(path).read_text()) for path in (left, right))
    fixed = ('law_id', 'cell_id', 'maneuver', 'control', 'public_highway_source',
             'intersecting_roads', 'approach_road_id', 'departure_road_id',
             'approach_centerline_xy_m', 'approach_half_width_m', 'centerline_kind',
             'camera_plan', 'duration_s', 'controller_policy')
    validate_context(a['context']); validate_context(b['context'])
    for key in fixed:
        if a['context'].get(key) != b['context'].get(key):
            raise ValueError('comparison fixed condition changed: ' + key)
    x, y = a['measurement'], b['measurement']
    if x['source_sha256'] == y['source_sha256']:
        raise ValueError('comparison reuses same original sources')
    return {'near_min_m': x['nearest_body_edge_range_m'][0],
            'far_min_m': y['nearest_body_edge_range_m'][0],
            'signed_difference_m': y['nearest_body_edge_range_m'][0] - x['nearest_body_edge_range_m'][0],
            'legal_verdict': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(measure(args.attempt), indent=2) + '\n')


if __name__ == '__main__':
    main()
