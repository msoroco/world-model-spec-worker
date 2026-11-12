"""Lazy Native two-approach construction for the median-opening cases.

This checks selected map geometry before spawning the other vehicle. The caller
owns the ego actor and the signal Off/restore context separately.
"""
from contextlib import contextmanager
import math

from shapely.geometry import Point, Polygon


def _xy(transform):
    return float(transform.location.x), float(transform.location.y)


def _bearing(transform):
    yaw = math.radians(float(transform.rotation.yaw))
    return math.cos(yaw), math.sin(yaw)


def _waypoint(world_map, transform, label):
    waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
    if waypoint is None:
        raise ValueError('No Native driving waypoint for ' + label)
    if getattr(waypoint, 'lane_type', None) is not None and 'Driving' not in str(waypoint.lane_type):
        raise ValueError('Non-driving Native waypoint for ' + label)
    return waypoint


def plan_pair(world_map, site, transforms, side):
    required = ('native_map_name', 'crossing_id', 'ego_highway_id',
                'other_highway_id', 'crossing_polygon_source',
                'approach_geometry_source', 'median_spacing_source',
                'all_entrances_source')
    if any(site.get(key) in (None, '') for key in required):
        raise ValueError('Source-reviewed median crossing and entrance inventory required')
    if site['ego_highway_id'] != site['other_highway_id']:
        raise ValueError('Opposite approaches must use one sourced highway')
    if site.get('same_statutory_crossing') is not True:
        raise ValueError('One statutory median crossing must be sourced')
    if side != 'opposite':
        raise ValueError('Declared approach side required')
    polygon = Polygon(site.get('crossing_polygon_xy_m', []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Valid crossing polygon required')
    approaches = {}
    for role in ('ego', 'other'):
        start = transforms[role + '_approach']
        entry = transforms[role + '_entry']
        start_point, entry_point = Point(_xy(start)), Point(_xy(entry))
        if polygon.intersects(start_point) or not polygon.intersects(entry_point):
            raise ValueError(role + ' approach/entry misses selected crossing')
        dx, dy = entry_point.x - start_point.x, entry_point.y - start_point.y
        distance = math.hypot(dx, dy)
        fx, fy = _bearing(start)
        if distance < 3 or (fx * dx + fy * dy) / distance < .8:
            raise ValueError(role + ' heading does not approach crossing entry')
        start_wp = _waypoint(world_map, start, role + ' approach')
        entry_wp = _waypoint(world_map, entry, role + ' entry')
        if (start_wp.is_junction or not entry_wp.is_junction or
                entry_wp.get_junction().id != site['crossing_id']):
            raise ValueError(role + ' Native entry is not in selected junction')
        approaches[role] = {'start_xy_m': list(_xy(start)),
                            'entry_xy_m': list(_xy(entry)),
                            'heading_deg': float(start.rotation.yaw),
                            'road_id': start_wp.road_id,
                            'lane_id': start_wp.lane_id,
                            'entry_road_id': entry_wp.road_id,
                            'entry_lane_id': entry_wp.lane_id}
    if (approaches['ego']['road_id'] != approaches['other']['road_id'] or
        approaches['ego']['lane_id'] == approaches['other']['lane_id']):
        raise ValueError('Opposite approaches need one Native road and distinct lanes')
    ego_forward = _bearing(transforms['ego_approach'])
    other_forward = _bearing(transforms['other_approach'])
    ego_xy, other_xy = _xy(transforms['ego_approach']), _xy(transforms['other_approach'])
    lateral = ego_forward[0] * (other_xy[1] - ego_xy[1]) - ego_forward[1] * (other_xy[0] - ego_xy[0])
    reciprocal = other_forward[0] * (ego_xy[1] - other_xy[1]) - other_forward[1] * (ego_xy[0] - other_xy[0])
    if side == 'right' and not (lateral < -1 and reciprocal > 1):
        raise ValueError('Other approach is not reciprocally on ego right')
    if side == 'left' and not (lateral > 1 and reciprocal < -1):
        raise ValueError('Other approach is not reciprocally on ego left')
    if side == 'opposite' and ego_forward[0] * other_forward[0] + ego_forward[1] * other_forward[1] > -.8:
        raise ValueError('Approaches do not face opposite directions')
    return {'native_map_name': site['native_map_name'],
            'native_junction_id': site['crossing_id'],
            'crossing_polygon_xy_m': site['crossing_polygon_xy_m'],
            'crossing_polygon_source': site['crossing_polygon_source'],
            'median_spacing_source': site['median_spacing_source'],
            'all_entrances_source': site['all_entrances_source'],
            'ego_highway_id': site['ego_highway_id'],
            'other_highway_id': site['other_highway_id'],
            'declared_approach_side': side,
            'other_lateral_to_ego_m': lateral,
            'approaches': approaches,
            'physical_acceptance_claimed': False,
            'legal_priority_judgment': 'unresolved'}


@contextmanager
def construct_pair(world, site, transforms, other_blueprint, side):
    world_map = world.get_map()
    if world_map.name != site.get('native_map_name'):
        raise ValueError('Native map differs from reviewed median site')
    plan = plan_pair(world_map, site, transforms, side)
    other = world.try_spawn_actor(other_blueprint, transforms['other_approach'])
    if other is None:
        raise ValueError('Other Native spawn failed')
    try:
        yield plan, other
    finally:
        other.destroy()
