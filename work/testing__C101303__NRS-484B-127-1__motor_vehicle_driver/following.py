"""Geometry and source-bound measurements for following before a lane change.

These measurements describe observed spacing and context. They never decide what
distance is reasonable and prudent under NRS 484B.127(1).
"""
import hashlib
import json
import math
from pathlib import Path


HISTORY = 'following-history.jsonl'
CONTEXT = 'following-context.json'


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return float(value)


def route_station(point, polyline):
    """Return nearest station and lateral error on a Native connected route."""
    if not isinstance(polyline, list) or len(polyline) < 2:
        raise ValueError('connected route needs at least two points')
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        raise ValueError('body point needs x/y')
    px, py = (_finite(v, 'body point') for v in point[:2])
    best = None
    station = 0.0
    for a, b in zip(polyline, polyline[1:]):
        ax, ay = (_finite(v, 'route point') for v in a[:2])
        bx, by = (_finite(v, 'route point') for v in b[:2])
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            raise ValueError('route has zero-length segment')
        fraction = max(0., min(1., ((px - ax)*dx + (py - ay)*dy)/(length*length)))
        lateral = math.hypot(px - ax - fraction*dx, py - ay - fraction*dy)
        candidate = (lateral, station + fraction*length)
        if best is None or candidate < best:
            best = candidate
        station += length
    return {'station_m': best[1], 'lateral_error_m': best[0]}


def body_interval(vertices, route):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError('original body vertices missing')
    projected = [route_station(v, route) for v in vertices]
    if max(v['lateral_error_m'] for v in projected) > 5.0:
        raise ValueError('body is outside common following route')
    return min(v['station_m'] for v in projected), max(v['station_m'] for v in projected)


def body_gap(ego_vertices, lead_vertices, route):
    ego_back, ego_front = body_interval(ego_vertices, route)
    lead_back, lead_front = body_interval(lead_vertices, route)
    if lead_front <= ego_front:
        raise ValueError('leader is not ahead on common route')
    return lead_back - ego_front


def _source(attempt, acquisition, name):
    record = acquisition.get(name, {})
    path = attempt / name
    if not path.is_file() or record.get('kind') != 'original_native':
        raise ValueError(f'missing original Native source: {name}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record.get('sha256'):
        raise ValueError(f'stale original Native source: {name}')
    return path, digest


def measure(attempt, case_id, *, diagnostic=False):
    """Verify an original frame history and derive unlabelled following observables."""
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    history_path, history_sha = _source(attempt, acquisition, HISTORY)
    context_path, context_sha = _source(attempt, acquisition, CONTEXT)
    context = json.loads(context_path.read_text())
    if context.get('case_id') != case_id:
        raise ValueError('original context has wrong exact case')
    if context.get('route_source') != 'Native CARLA connected waypoints':
        raise ValueError('connected Native route source missing')
    route = context.get('common_following_route_xy_m')
    if not isinstance(route, list) or len(route) < 2:
        raise ValueError('common following route missing')
    if context.get('condition_source') != 'original weather and road context':
        raise ValueError('highway condition source missing')
    road_id = context.get('road_id')
    following_lane = context.get('following_lane_id')
    target_lane = context.get('target_lane_id')
    if (type(road_id) is not int or type(following_lane) is not int or
            type(target_lane) is not int or following_lane == target_lane):
        raise ValueError('original following and target lane identities missing')
    crest = context.get('hill_crest')
    if (not isinstance(crest, dict) or
            crest.get('source_ref') != 'Native CARLA map waypoint elevation'):
        raise ValueError('original hill crest source missing')
    crest_station = _finite(crest.get('crest_station_m'), 'crest station')
    rows = [json.loads(line) for line in history_path.read_text().splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError('original following history too short')
    rate = _finite(context.get('rate_hz'), 'rate')
    duration = _finite(context.get('duration_s'), 'duration')
    if rate != 20 or duration <= 20:
        raise ValueError('20 Hz and steady-following window required')
    if not diagnostic and len(rows) != round(rate*duration):
        raise ValueError('original following history does not cover capture duration')
    prev = None
    measured = []
    for row in rows:
        frame = row.get('frame')
        time_s = _finite(row.get('time_s'), 'original time')
        if type(frame) is not int or (prev and (frame <= prev[0] or time_s <= prev[1])):
            raise ValueError('original frame/time order invalid')
        prev = frame, time_s
        ego, lead = row.get('ego'), row.get('leader')
        if not isinstance(ego, dict) or not isinstance(lead, dict):
            raise ValueError('original ego and leader participants required')
        if (ego.get('source_ref') != 'Native CARLA actor transform and bounding box' or
                lead.get('source_ref') != 'Native CARLA actor transform and bounding box'):
            raise ValueError('original actor-body source missing')
        if ego.get('actor_id') == lead.get('actor_id') or not ego.get('actor_id') or not lead.get('actor_id'):
            raise ValueError('distinct original actor identities required')
        ego_speed = _finite(ego.get('speed_mps'), 'ego speed')
        lead_speed = _finite(lead.get('speed_mps'), 'leader speed')
        if min(ego_speed, lead_speed) < 0:
            raise ValueError('negative original speed')
        count = row.get('surrounding_vehicle_count')
        if type(count) is not int or count < 1 or not row.get('traffic_source'):
            raise ValueError('original traffic inventory missing')
        condition = row.get('highway_condition')
        if not isinstance(condition, dict) or not condition.get('source_ref'):
            raise ValueError('original highway condition missing')
        for key in ('native_fog_density', 'native_precipitation_strength'):
            value = _finite(condition.get(key), key)
            if not 0 <= value <= 100:
                raise ValueError('weather outside CARLA percent domain')
        friction = _finite(condition.get('observed_tire_friction'), 'wheel friction')
        if friction <= 0:
            raise ValueError('original wheel friction invalid')
        lane = row.get('lane_change')
        if not isinstance(lane, dict) or not lane.get('source_ref'):
            raise ValueError('original lane-change status missing')
        if lane.get('ego_road_id') != road_id or lane.get('leader_road_id') != road_id:
            raise ValueError('original road identity changed')
        if lane.get('leader_lane_id') != following_lane:
            raise ValueError('moving leader left original following lane')
        observed_lane = lane.get('ego_lane_id')
        if observed_lane not in (following_lane, target_lane):
            raise ValueError('ego observed outside planned lane-change pair')
        if (time_s <= 20 and observed_lane != following_lane or
                lane.get('started') is not (observed_lane != following_lane)):
            raise ValueError('lane change occurred during steady following or flag differs from Native lane')
        gap = body_gap(ego['body_vertices_m'], lead['body_vertices_m'], route)
        ego_station = sum(body_interval(ego['body_vertices_m'], route))/2
        measured.append({'frame': frame, 'time_s': time_s, 'along_route_body_gap_m': gap,
                         'ego_station_m': ego_station,
                         'ego_speed_mps': ego_speed, 'leader_speed_mps': lead_speed,
                         'relative_speed_mps': ego_speed - lead_speed,
                         'surrounding_vehicle_count': count,
                         'lane_change_started': lane.get('started') is True,
                         'highway_condition': condition})
    steady = [r for r in measured if 14 <= r['time_s'] <= 20 and not r['lane_change_started']]
    if len(steady) < 3:
        raise ValueError('original 14..20s steady following window missing')
    if min(r['leader_speed_mps'] for r in steady) <= .5 or min(r['ego_speed_mps'] for r in steady) <= .5:
        raise ValueError('both vehicles must move during steady following')
    if not min(r['ego_station_m'] for r in steady) <= crest_station <= max(r['ego_station_m'] for r in steady):
        raise ValueError('measured hill crest not traversed during steady following')
    if not any(r['lane_change_started'] for r in measured if r['time_s'] > 20):
        raise ValueError('following-before-lane-change transition missing')
    def mean(key):
        return sum(r[key] for r in steady)/len(steady)
    def condition_mean(key):
        return sum(r['highway_condition'][key] for r in steady)/len(steady)
    return {'format': 'worker-following-measurements', 'case_id': case_id,
            'frame_count': len(rows), 'steady_window_s': [14, 20],
            'steady_frame_count': len(steady),
            'mean_along_route_body_gap_m': mean('along_route_body_gap_m'),
            'mean_ego_speed_mps': mean('ego_speed_mps'),
            'mean_leader_speed_mps': mean('leader_speed_mps'),
            'mean_relative_speed_mps': mean('relative_speed_mps'),
            'hill_crest_station_m': crest_station,
            'steady_ego_station_range_m': [min(r['ego_station_m'] for r in steady),
                                           max(r['ego_station_m'] for r in steady)],
            'mean_surrounding_vehicle_count': mean('surrounding_vehicle_count'),
            'mean_native_precipitation_strength': condition_mean('native_precipitation_strength'),
            'mean_native_fog_density': condition_mean('native_fog_density'),
            'mean_observed_tire_friction': condition_mean('observed_tire_friction'),
            'minimum_body_gap_m': min(r['along_route_body_gap_m'] for r in steady),
            'lane_change_first_frame': next(r['frame'] for r in measured if r['lane_change_started']),
            'raw_history': measured,
            'sources': {HISTORY: history_sha, CONTEXT: context_sha},
            'legal_reasonableness_verdict': 'unresolved'}
