"""Independent source audit for the C109705 destination exit CPU fixtures.

This audits diagnostic consistency only. Native motion, visibility, and legal
acceptance require the original local recording and a human source review.
"""
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

REQUIRED = ('config.json', 'site_packet.json', 'road_context.json',
            'road_geometry.json', 'turn_history.jsonl', 'body_history.jsonl',
            'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
            'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
            'driver_reference.mkv')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FIXED = ('native_map_id', 'intersection_id', 'approach_road_id',
         'outgoing_road_id', 'both_highways_two_directional', 'intended_turn',
         'destination_centerline_xy_m', 'destination_right_half_polygon_xy_m',
         'junction_polygon_xy_m', 'opposing_lane_source',
         'destination_centerline_source', 'destination_right_half_source',
         'junction_source', 'left_turn_route_source')


def read(path):
    return json.loads(path.read_text())


def rows(path):
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError('Missing original rows: ' + path.name)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_delivery(attempt, decode=False):
    attempt = Path(attempt)
    missing = [name for name in (*REQUIRED, 'result.json') if not (attempt / name).is_file()]
    if missing:
        raise ValueError('Missing original evidence: ' + ', '.join(missing))
    result, config = read(attempt / 'result.json'), read(attempt / 'config.json')
    context, packet = read(attempt / 'road_context.json'), read(attempt / 'site_packet.json')
    geometry = read(attempt / 'road_geometry.json')
    case = config.get('selected_case_id')
    if result.get('case_id') != case or not case.startswith('testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__source_verified_'):
        raise ValueError('Exact case identity differs')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != ('NRS-484B-400-2b', 'C109705', 'motor_vehicle_driver'):
        raise ValueError('Exact law/cell/actor differs')
    hashes = result.get('source_evidence_hashes', {})
    for name in REQUIRED:
        if hashes.get(name) != digest(attempt / name):
            raise ValueError('Missing or stale original source hash: ' + name)
    kind = 'imaginary' if 'imaginary_' in case else 'marked'
    if (context.get('site_source_review', {}).get('centerline_kind') != kind or
            packet.get('centerline_kind') != kind):
        raise ValueError('Centerline authority differs')
    if context.get('both_highways_two_directional') is not True or context.get('intended_turn') != 'left':
        raise ValueError('Two-directional left-turn activation absent')
    for key in ('native_map_id', 'intersection_id', 'approach_road_id',
                'outgoing_road_id', 'destination_centerline_xy_m',
                'destination_right_half_polygon_xy_m', 'junction_polygon_xy_m'):
        if context.get(key) != packet.get(key):
            raise ValueError('Original context/packet mismatch: ' + key)
    if (geometry.get('departure_road_id') != context['outgoing_road_id'] or
            geometry.get('approach_road_id') != context['approach_road_id'] or
            geometry.get('intersection_xy_m') != context['junction_polygon_xy_m'] or
            geometry.get('connector_road_id') != packet.get('connector_road_id') or
            geometry.get('departure_direction_xy') != packet.get('departure_direction_xy') or
            geometry.get('two_way') is not True):
        raise ValueError('Original road geometry differs')
    line = LineString(context['destination_centerline_xy_m'])
    right = Polygon(context['destination_right_half_polygon_xy_m'])
    junction = Polygon(context['junction_polygon_xy_m'])
    if line.length <= 0 or not right.is_valid or right.area <= 0 or not junction.is_valid or junction.area <= 0:
        raise ValueError('Invalid sourced geometry')
    turn, body, frames, trace = (rows(attempt / name) for name in
                                 ('turn_history.jsonl', 'body_history.jsonl',
                                  'video_frames.jsonl', 'trace.jsonl'))
    if len(turn) < 3 or len({len(turn), len(body), len(frames), len(trace)}) != 1:
        raise ValueError('Incomplete original frame history')
    previous = (-1, -math.inf)
    entered = False
    exit_sample = None
    for index, (t, b, f, r) in enumerate(zip(turn, body, frames, trace)):
        fid, time = t.get('frame'), t.get('time_s')
        if type(fid) is not int or type(time) not in (int, float) or not math.isfinite(time) or fid <= previous[0] or time <= previous[1]:
            raise ValueError('Nonmonotone original history')
        previous = fid, time
        if (f.get('video_frame') != index or f.get('native_frame') != fid or
                f.get('carla_frame') != fid or f.get('time_s') != time or
                b.get('frame') != fid or b.get('time_s') != time or
                r.get('frame') != fid or r.get('time_s') != time or
                b.get('road_id') != t.get('road_id') or
                [v[:2] for v in b.get('body_vertices_m', [])] != t.get('ego_body_vertices_xy_m')):
            raise ValueError('Original frame/body/trace join differs')
        shape = Polygon(t['ego_body_vertices_xy_m']).convex_hull
        if not shape.is_valid or shape.area <= 0:
            raise ValueError('Degenerate original body')
        intersects = shape.intersects(junction)
        entered |= intersects
        if entered and not intersects and exit_sample is None:
            if t.get('road_id') != context['outgoing_road_id']:
                raise ValueError('Exit on wrong destination road')
            exit_sample = {'frame': fid, 'time_s': time,
                           'centroid_distance_m': line.distance(shape.centroid),
                           'minimum_vertex_distance_m': min(line.distance(Point(v)) for v in t['ego_body_vertices_xy_m']),
                           'right': right.covers(shape) and not shape.intersects(line)}
    if exit_sample is None or not exit_sample['right']:
        raise ValueError('No complete-body right-side destination exit')
    measured = result.get('measured_values', {})
    for key, expected in (('exit_frame', exit_sample['frame']),
                          ('exit_time_s', exit_sample['time_s']),
                          ('body_centroid_distance_to_centerline_m', exit_sample['centroid_distance_m']),
                          ('minimum_vertex_distance_to_centerline_m', exit_sample['minimum_vertex_distance_m'])):
        actual = measured.get(key)
        if type(actual) not in (int, float) or not math.isclose(actual, expected, abs_tol=1e-6):
            raise ValueError('Reported measurement differs from original body: ' + key)
    if measured.get('destination_centerline_kind') != kind or measured.get('complete_body_right_of_destination_centerline') is not True:
        raise ValueError('Reported destination result differs')
    decoded = {}
    if decode:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '..' / 'runtime/scenario_pipeline'))
        from worker_exchange.media import audit, check_four_view_sources
        sources = {name: attempt / (name + '.mkv') for name in CAMERAS}
        check_four_view_sources(sources)
        mapping = digest(attempt / 'video_frames.jsonl')
        decoded = {name: audit(video, len(frames), mapping_sha256=mapping)['rgb_sequence_sha256']
                   for name, video in sources.items()}
    return {'case_id': case, 'kind': kind,
            'fixed': {key: context.get(key) for key in FIXED},
            'cameras': config['cameras'], 'rate_hz': config['rate_hz'],
            'duration_s': config['duration_s'], 'frame_map': digest(attempt / 'video_frames.jsonl'),
            'decoded': decoded, 'exit': exit_sample,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def audit_comparison(near_attempt, far_attempt, kind, decode=False):
    near, far = audit_delivery(near_attempt, decode), audit_delivery(far_attempt, decode)
    if near['kind'] != kind or far['kind'] != kind:
        raise ValueError('Wrong comparison centerline kind')
    for key in ('fixed', 'cameras', 'rate_hz', 'duration_s', 'frame_map'):
        if near[key] != far[key]:
            raise ValueError('Fixed comparison condition differs: ' + key)
    if decode and near['decoded'] != far['decoded']:
        raise ValueError('Fixed comparison camera pixels differ')
    if not near['exit']['centroid_distance_m'] < far['exit']['centroid_distance_m']:
        raise ValueError('Near/far exit offset not observed')
    return {'kind': kind, 'near_case_id': near['case_id'], 'far_case_id': far['case_id'],
            'near_exit': near['exit'], 'far_exit': far['exit'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def cli():
    import argparse
    import os
    from tempfile import TemporaryDirectory
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if read(args.attempt / 'config.json').get('selected_case_id') != args.case:
        raise ValueError('CLI selected another exact case')
    if args.negative:
        with TemporaryDirectory(dir='.runtime-work', prefix='c109705-2b-delivery-negative-') as tmp:
            target = Path(tmp)
            for name in (*REQUIRED, 'result.json'):
                if name == 'turn_history.jsonl':
                    continue
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.link(args.attempt / name, dest)
            audit_delivery(target, decode=True)
        raise AssertionError('Missing original turn history passed')
    result = audit_delivery(args.attempt, decode=True)
    if result['case_id'] != args.case:
        raise ValueError('Delivery audit selected another exact case')
    print(json.dumps({'case_id': args.case, 'passed': True,
                      'source_bound': True, 'full_video_decode': result['decoded'],
                      'fixture_scope': 'synthetic diagnostic; actor visibility unverified',
                      'physical_acceptance_claimed': False,
                      'legal_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    cli()
