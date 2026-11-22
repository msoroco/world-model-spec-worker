"""Lazy Native map route discovery for the fixed hill-crest/change-lane cell."""
import math

from construction import validate_hill_route


def _lane_type(waypoint):
    return str(getattr(waypoint, 'lane_type', '')).split('.')[-1]


def _forward_dot(first, second):
    a = first.transform.get_forward_vector()
    b = second.transform.get_forward_vector()
    norm = math.hypot(a.x, a.y)*math.hypot(b.x, b.y)
    return (a.x*b.x+a.y*b.y)/norm if norm else -1.


def _adjacent(waypoint):
    for method in ('get_left_lane', 'get_right_lane'):
        candidate = getattr(waypoint, method)()
        if candidate is None or _lane_type(candidate) != 'Driving':
            continue
        if candidate.road_id == waypoint.road_id and candidate.lane_id != waypoint.lane_id:
            dot = _forward_dot(waypoint, candidate)
            if dot >= .8:
                return {'road_id': candidate.road_id, 'lane_id': candidate.lane_id,
                        'lane_type': 'Driving', 'forward_dot': dot}, candidate
    return None, None


def discover_hill_route(native_map, *, step_m=4., points=120,
                        crest_station_range_m=None, change_station_m=None,
                        seed_strategy='spawn'):
    """Choose connected original waypoints with crest and forward adjacent lane.

    Selection is geometric. A missing map feature is an explicit Native failure,
    never replaced by an authored label or a flat route.
    """
    if step_m <= 0 or points < 9:
        raise ValueError('invalid Native route search resolution')
    if seed_strategy == 'spawn':
        firsts = [native_map.get_waypoint(spawn.location)
                  for spawn in native_map.get_spawn_points()]
    elif seed_strategy == 'topology':
        firsts = native_map.generate_waypoints(20.0)
    else:
        raise ValueError('unknown Native route seed strategy')
    for first in firsts:
        if first is None or _lane_type(first) != 'Driving':
            continue
        waypoints = [first]
        while len(waypoints) < points:
            options = [p for p in waypoints[-1].next(step_m)
                       if p.road_id == first.road_id and p.lane_id == first.lane_id
                       and _lane_type(p) == 'Driving']
            if len(options) != 1:
                break
            point = options[0]
            if math.hypot(point.transform.location.x-waypoints[-1].transform.location.x,
                          point.transform.location.y-waypoints[-1].transform.location.y) > 1.5*step_m:
                break
            waypoints.append(point)
        if len(waypoints) != points:
            continue
        adjacent, target = _adjacent(waypoints[-2])
        if adjacent is None:
            continue
        samples = []
        station = 0.
        for i, wp in enumerate(waypoints):
            if i:
                previous = waypoints[i-1].transform.location
                here = wp.transform.location
                station += math.hypot(here.x-previous.x, here.y-previous.y)
            samples.append({'road_id': wp.road_id, 'lane_id': wp.lane_id,
                            'lane_type': _lane_type(wp), 'station_m': station,
                            'z_m': wp.transform.location.z,
                            'adjacent_lane': adjacent})
        try:
            geometry = validate_hill_route(samples)
        except ValueError:
            continue
        if crest_station_range_m is not None:
            low, high = crest_station_range_m
            if not low <= geometry['crest_station_m'] <= high:
                continue
        if change_station_m is not None:
            change_index = min(range(len(samples)),
                               key=lambda index: abs(samples[index]['station_m']-change_station_m))
            change_neighbor, _ = _adjacent(waypoints[change_index])
            if not change_neighbor or change_neighbor['lane_id'] != geometry['target_lane_id']:
                continue
        return {'map_source': native_map.name, 'route_source': 'Native CARLA connected waypoints',
                'waypoints': waypoints, 'target_waypoint': target,
                'sampled_geometry': samples, 'geometry': geometry}
    raise ValueError('original Native map lacks connected hill crest and forward adjacent lane')
