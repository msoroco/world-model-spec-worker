"""Survey an original Native two-way crest without importing CARLA.

The caller supplies CARLA waypoints from the selected map. This is a construction
preflight, not evidence that a later vehicle followed the route or saw its peer.
"""
from __future__ import annotations

import hashlib
import math

from crest_speed import crest_station


def _position(waypoint):
    location = waypoint.transform.location
    values = (location.x, location.y, location.z)
    if not all(type(value) in (int, float) and math.isfinite(value) for value in values):
        raise ValueError('finite original waypoint location required')
    return tuple(float(value) for value in values)


def survey_lane(start, *, map_name, map_sha256, step_m=5.0, count=9):
    """Follow one unbranched driving lane and return source-bound grade samples."""
    if not map_name or not isinstance(map_sha256, str) or len(map_sha256) != 64:
        raise ValueError('source-bound original map identity required')
    if type(step_m) not in (int, float) or not math.isfinite(step_m) or step_m <= 0:
        raise ValueError('positive finite waypoint step required')
    if type(count) is not int or count < 5:
        raise ValueError('five or more original route waypoints required')
    road_id, lane_id = start.road_id, start.lane_id
    if lane_id == 0 or not str(start.lane_type).lower().endswith('driving'):
        raise ValueError('original driving lane required')
    waypoints = [start]
    for _ in range(count - 1):
        choices = waypoints[-1].next(float(step_m))
        if len(choices) != 1:
            raise ValueError('original route must have one connected continuation')
        next_waypoint = choices[0]
        if next_waypoint.road_id != road_id or next_waypoint.lane_id != lane_id:
            raise ValueError('route changed original road or lane')
        waypoints.append(next_waypoint)
    points = [_position(waypoint) for waypoint in waypoints]
    grades = []
    station = 0.0
    for index, (waypoint, point) in enumerate(zip(waypoints, points)):
        if index:
            previous = points[index - 1]
            segment = math.dist(point, previous)
            if segment <= 0 or segment > 2 * step_m:
                raise ValueError('original route has a gap or duplicate waypoint')
            station += segment
        grades.append({'s_m': station, 'z_m': point[2],
                       'source_ref': f'{map_name}:{map_sha256}:{road_id}:{lane_id}:{waypoint.s}',
                       'x_m': point[0], 'y_m': point[1]})
    peak = crest_station(grades)
    peak_point = min(grades, key=lambda point: abs(point['s_m'] - peak))
    return {'map_name': map_name, 'map_sha256': map_sha256,
            'road_id': road_id, 'lane_id': lane_id,
            'waypoints': grades, 'crest_station_m': peak,
            'crest_world_xyz_m': [peak_point['x_m'], peak_point['y_m'], peak_point['z_m']]}


def bind_opposing_routes(forward, opposing, *, max_crest_separation_m=20.0):
    """Require two original directions of one road with colocated grade crests."""
    if forward['map_sha256'] != opposing['map_sha256'] or forward['map_name'] != opposing['map_name']:
        raise ValueError('opposing routes use different original maps')
    if forward['road_id'] != opposing['road_id'] or forward['lane_id'] * opposing['lane_id'] >= 0:
        raise ValueError('opposing routes must use opposite driving lanes of one road')
    distance = math.dist(forward['crest_world_xyz_m'], opposing['crest_world_xyz_m'])
    if distance > max_crest_separation_m:
        raise ValueError('opposing original grade crests are not colocated')
    return {'map_sha256': forward['map_sha256'], 'road_id': forward['road_id'],
            'forward_lane_id': forward['lane_id'], 'opposing_lane_id': opposing['lane_id'],
            'crest_separation_m': distance,
            'limitation': 'Waypoints establish route geometry only; sight lines and actual motion need capture.'}


def survey_map_pair(carla_map, forward_start, opposing_start, *, expected_map_sha256,
                    step_m=5.0, count=9):
    """Hash the actual Native OpenDRIVE text before binding either direction."""
    source = carla_map.to_opendrive()
    if not isinstance(source, str) or not source.strip():
        raise ValueError('original Native OpenDRIVE source required')
    actual_sha256 = hashlib.sha256(source.encode('utf-8')).hexdigest()
    if actual_sha256 != expected_map_sha256:
        raise ValueError('original Native map source hash differs')
    map_name = carla_map.name
    forward = survey_lane(forward_start, map_name=map_name,
                          map_sha256=actual_sha256, step_m=step_m, count=count)
    opposing = survey_lane(opposing_start, map_name=map_name,
                           map_sha256=actual_sha256, step_m=step_m, count=count)
    binding = bind_opposing_routes(forward, opposing)
    return {'forward': forward, 'opposing': opposing, 'binding': binding}
