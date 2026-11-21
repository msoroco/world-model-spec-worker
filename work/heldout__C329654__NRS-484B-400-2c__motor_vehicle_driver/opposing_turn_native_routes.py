"""Survey connected Native waypoint paths for an opposing left-turn pair.

This module can be imported without CARLA. The caller supplies the live Native
map; returned paths retain its waypoint objects for the eventual runner.
"""

import math
from xml.etree import ElementTree

from opposing_turn_routes import select_opposing_left_pair


def driving_lanes(opendrive):
    root = ElementTree.fromstring(opendrive)
    inventory = {}
    for road in root.findall('road'):
        lanes = set()
        for lane in road.findall('./lanes/laneSection/left/lane') + road.findall('./lanes/laneSection/right/lane'):
            if lane.get('type') == 'driving':
                lanes.add(int(lane.get('id')))
        inventory[int(road.get('id'))] = sorted(lanes)
    return inventory


def heading(waypoint):
    yaw = math.radians(float(waypoint.transform.rotation.yaw))
    return [math.cos(yaw), math.sin(yaw)]


def _key(waypoint):
    return (int(waypoint.road_id), int(waypoint.lane_id),
            round(float(waypoint.s), 2), bool(waypoint.is_junction))


def discover_routes(world_map, *, step_m=2.0, max_steps=80):
    """Follow actual successors from each spawn to an exterior left-turn exit."""
    if not 1.0 <= step_m <= 3.0 or not 10 <= max_steps <= 200:
        raise ValueError('unsupported Native waypoint survey bounds')
    inventory = driving_lanes(world_map.to_opendrive())
    routes = []
    for spawn in world_map.get_spawn_points():
        approach = world_map.get_waypoint(spawn.location)
        if approach is None or approach.is_junction:
            continue
        if not ({-1, 1} <= {1 if n > 0 else -1 for n in inventory.get(approach.road_id, [])}):
            continue
        queue = [(approach, [approach], None)]
        seen = set()
        while queue:
            waypoint, path, junction_id = queue.pop(0)
            key = (_key(waypoint), junction_id)
            if key in seen:
                continue
            seen.add(key)
            if len(path) > max_steps:
                continue
            if waypoint.is_junction:
                junction = waypoint.get_junction()
                if junction is None:
                    continue
                if junction_id is not None and junction_id != junction.id:
                    continue
                junction_id = junction.id
            elif junction_id is not None:
                start, end = heading(approach), heading(waypoint)
                cross = start[0]*end[1] - start[1]*end[0]
                dot = start[0]*end[0] + start[1]*end[1]
                exit_lanes = inventory.get(waypoint.road_id, [])
                if (cross > 0.5 and abs(dot) < 0.8 and
                        any(n < 0 for n in exit_lanes) and any(n > 0 for n in exit_lanes)):
                    routes.append({
                        'path': path, 'junction_id': junction_id,
                        'approach_axis': approach.road_id,
                        'approach_heading_xy': start, 'exit_heading_xy': end,
                        'approach_road_id': approach.road_id,
                        'approach_lane_id': approach.lane_id,
                        'exit_road_id': waypoint.road_id,
                        'exit_lane_id': waypoint.lane_id,
                    })
                continue
            for successor in waypoint.next(step_m):
                if junction_id is None and not successor.is_junction and successor.road_id != approach.road_id:
                    continue
                if _key(successor) in {_key(item) for item in path}:
                    continue
                queue.append((successor, path + [successor], junction_id))
    return routes, inventory


def choose_native_pair(world_map, *, step_m=2.0, max_steps=80, route_accept=None):
    routes, inventory = discover_routes(world_map, step_m=step_m, max_steps=max_steps)
    return select_opposing_left_pair(routes, inventory, route_accept=route_accept)
