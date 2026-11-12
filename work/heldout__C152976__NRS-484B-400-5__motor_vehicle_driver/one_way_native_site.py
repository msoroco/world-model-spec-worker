"""CARLA-lazy survey of a source-bound one-way to one-way left-turn site.

The site file is a proposed map inventory. The runtime readback checks identity,
lane connectivity and actual direction; a declared sign alone proves nothing.
"""
import hashlib
import json
from math import atan2, degrees, radians, sin, cos
from pathlib import Path


def _heading_delta(a, b):
    d = radians(float(b.transform.rotation.yaw) - float(a.transform.rotation.yaw))
    return degrees(atan2(sin(d), cos(d)))


def _identity(wp):
    return (int(wp.road_id), int(wp.lane_id))


def _read_waypoint(world_map, selector):
    road = int(selector['road_id'])
    lane = int(selector['lane_id'])
    s = float(selector['s_m'])
    wp = world_map.get_waypoint_xodr(road, lane, s)
    if wp is None or _identity(wp) != (road, lane):
        raise ValueError('surveyed OpenDRIVE lane not present in Native map')
    if str(wp.lane_type).split('.')[-1].lower() != 'driving':
        raise ValueError('surveyed lane is not a Native driving lane')
    return wp


def _no_opposing_driving_lane(wp):
    """Reject a driving lane with the opposite OpenDRIVE lane sign on this road."""
    seen = set()
    queue = [wp]
    while queue:
        current = queue.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if int(current.road_id) == int(wp.road_id) and str(current.lane_type).split('.')[-1].lower() == 'driving':
            if int(current.lane_id) * int(wp.lane_id) < 0:
                raise ValueError('opposing driving lane on proposed one-way road')
        if len(seen) > 24:
            raise ValueError('lane cross-section survey exceeded bound')
        queue.extend([current.get_left_lane(), current.get_right_lane()])


def survey(world_map, site_path):
    path = Path(site_path)
    site = json.loads(path.read_text())
    od = world_map.to_opendrive()
    digest = hashlib.sha256(od.encode()).hexdigest()
    if digest != site.get('opendrive_sha256'):
        raise ValueError('Native OpenDRIVE hash differs from site survey')
    if not site.get('source_id') or not site.get('direction_sign_source'):
        raise ValueError('site or direction sign source absent')
    approach = _read_waypoint(world_map, site['approach'])
    departure = _read_waypoint(world_map, site['departure'])
    if _identity(approach)[0] == _identity(departure)[0]:
        raise ValueError('two intersecting one-way roads required')
    _no_opposing_driving_lane(approach)
    _no_opposing_driving_lane(departure)
    delta = _heading_delta(approach, departure)
    if not 55 <= delta <= 125:
        raise ValueError('Native departure is not a left turn')
    # The map graph must connect the actual approach to the selected exit.
    frontier = [(approach, 0, [approach])]
    visited = set()
    connected_route = None
    while frontier:
        wp, depth, route = frontier.pop(0)
        key = (int(wp.road_id), int(wp.lane_id), round(float(wp.s), 1))
        if key in visited:
            continue
        visited.add(key)
        if _identity(wp) == _identity(departure) and abs(float(wp.s)-float(departure.s)) <= 8:
            connected_route = route
            break
        if depth < 80:
            frontier.extend((nxt, depth+1, route+[nxt]) for nxt in wp.next(2.0))
    if connected_route is None:
        raise ValueError('approach does not connect to selected left-turn exit')
    return {'approach': approach, 'departure': departure,
            'opendrive_sha256': digest, 'site_source_id': site['source_id'],
            'direction_sign_source': site['direction_sign_source'],
            'left_turn_heading_delta_deg': delta,
            'connected_route': connected_route}
