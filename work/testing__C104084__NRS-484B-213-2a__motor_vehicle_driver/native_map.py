"""Lazy CARLA map binding for an original two-way hill crest.

The caller supplies a world and a CARLA Location at the intended approach.
No CARLA import or GPU work occurs when this module is imported or CPU-tested.
"""
from __future__ import annotations

import math
from crest_geometry import crest_occlusion, validate_lanes


def _xy(waypoint):
    location = waypoint.transform.location
    return location.x, location.y, location.z


def _heading_opposes(first, second):
    delta = math.radians(first.transform.rotation.yaw - second.transform.rotation.yaw)
    return math.cos(delta) < -0.8


def _heading_agrees(first, second):
    delta = math.radians(first.transform.rotation.yaw - second.transform.rotation.yaw)
    return math.cos(delta) > 0.8


def follow_approach(start_waypoint, *, interval_m=10, count=11):
    if type(count) is not int or count < 3 or type(interval_m) not in (int, float) or interval_m <= 0:
        raise ValueError('invalid original map sampling contract')
    route = [start_waypoint]
    for _ in range(count - 1):
        successors = route[-1].next(interval_m)
        if len(successors) != 1:
            raise ValueError('original approach branches or terminates before crest')
        following = successors[0]
        if following.road_id != start_waypoint.road_id or following.lane_id != start_waypoint.lane_id:
            raise ValueError('original approach changes road or lane')
        route.append(following)
    return route


def bind_two_way_crest(world, anchor_location, *, observer_index=1, target_index=9,
                       interval_m=10, count=11, require_blocked=True):
    """Return source-shaped grade samples or reject an unsuitable Native road.

    This does not claim actual driver visibility; final capture must raycast to
    actual opposing vehicle corners and retain the four camera sources.
    """
    mapping = world.get_map()
    start = mapping.get_waypoint(anchor_location)
    if start is None:
        raise ValueError('original map has no ego driving waypoint at anchor')
    route = follow_approach(start, interval_m=interval_m, count=count)
    opposite = [waypoint.get_left_lane() for waypoint in route]
    if any(w is None for w in opposite):
        raise ValueError('original map has no adjacent opposing lane along crest')
    if any(not _heading_opposes(a, b) for a, b in zip(route, opposite)):
        raise ValueError('adjacent Native lane is not opposite direction')
    if not (0 <= observer_index < target_index < count):
        raise ValueError('observer and target indices outside original route')
    source = getattr(mapping, 'name', None)
    if not source:
        raise ValueError('original map name/source missing')
    ego = []
    other = []
    for index, (forward, reverse) in enumerate(zip(route, opposite)):
        station = index * interval_m
        for waypoint, direction, collection in ((forward, 'increasing_s', ego),
                                                 (reverse, 'decreasing_s', other)):
            x, y, z = _xy(waypoint)
            collection.append({'s_m': station, 'x_m': x, 'y_m': y,
                               'road_z_m': z, 'road_id': waypoint.road_id,
                               'lane_id': waypoint.lane_id,
                               'travel_direction': direction,
                               'source_ref': f'Native map {source} road {waypoint.road_id} lane {waypoint.lane_id} station {station:g}m'})
    validate_lanes(ego, other)
    measured = crest_occlusion(ego, other, observer_s_m=observer_index * interval_m,
                               target_s_m=target_index * interval_m)
    if require_blocked and not measured['sampled_grade_blocks_proxy_ray']:
        raise ValueError('original map grade does not obstruct declared crest proxy ray')
    if not require_blocked and measured['sampled_grade_blocks_proxy_ray']:
        raise ValueError('original map grade is not clear for declared crest proxy ray')
    return {'map_source': source, 'ego_lane': ego, 'opposing_lane': other,
            'grade_proxy': measured, 'capture_requirements': [
                'actual opposing vehicle body corner rays', 'left-side ego body history',
                'four synchronized original camera streams', 'road and highway context']}


def bind_one_way_crest(world, anchor_location, *, observer_index=1, target_index=9,
                       interval_m=10, count=11):
    """Select same-direction Native lanes; authority is a separate source.

    The map topology alone cannot establish public highway status or legal
    one-way designation. The caller must bind those original context sources.
    """
    mapping = world.get_map()
    start = mapping.get_waypoint(anchor_location)
    if start is None:
        raise ValueError('original map has no ego driving waypoint at anchor')
    route = follow_approach(start, interval_m=interval_m, count=count)
    adjacent = [waypoint.get_left_lane() for waypoint in route]
    if any(w is None for w in adjacent):
        raise ValueError('original map has no adjacent lane along crest')
    if any(w.road_id != start.road_id or w.lane_id == start.lane_id for w in adjacent):
        raise ValueError('adjacent lane is not a distinct lane on the original road')
    if len({w.lane_id for w in adjacent}) != 1:
        raise ValueError('adjacent lane changes identity along original crest')
    if any(not _heading_agrees(a, b) for a, b in zip(route, adjacent)):
        raise ValueError('adjacent Native lane is not same direction')
    if not (0 <= observer_index < target_index < count):
        raise ValueError('observer and target indices outside original route')
    source = getattr(mapping, 'name', None)
    if not source:
        raise ValueError('original map name/source missing')
    ego, other = [], []
    for index, (forward, companion) in enumerate(zip(route, adjacent)):
        station = index * interval_m
        for waypoint, collection in ((forward, ego), (companion, other)):
            x, y, z = _xy(waypoint)
            collection.append({'s_m': station, 'x_m': x, 'y_m': y,
                               'road_z_m': z, 'road_id': waypoint.road_id,
                               'lane_id': waypoint.lane_id,
                               'travel_direction': 'increasing_s',
                               'source_ref': f'Native map {source} road {waypoint.road_id} lane {waypoint.lane_id} station {station:g}m'})
    eye = ego[observer_index]['road_z_m'] + 1.4
    target = ego[target_index]['road_z_m'] + 1.4
    start_s = observer_index * interval_m
    end_s = target_index * interval_m
    blockers = []
    for point in ego[observer_index + 1:target_index]:
        ray_z = eye + (target - eye) * (point['s_m'] - start_s) / (end_s - start_s)
        if point['road_z_m'] > ray_z:
            blockers.append({'s_m': point['s_m'],
                             'excess_height_m': point['road_z_m'] - ray_z,
                             'source_ref': point['source_ref']})
    if not blockers:
        raise ValueError('original one-way map grade does not obstruct declared crest proxy ray')
    return {'map_source': source, 'ego_lane': ego, 'same_direction_lane': other,
            'grade_proxy': {'sampled_grade_blocks_proxy_ray': True,
                            'blockers': blockers, 'observer_s_m': start_s,
                            'target_s_m': end_s},
            'context_requirements': ['original public highway source',
                                     'original one-way authority source'],
            'capture_requirements': ['left-side ego body history',
                                     'actual other vehicle route and body',
                                     'four synchronized original camera streams']}
