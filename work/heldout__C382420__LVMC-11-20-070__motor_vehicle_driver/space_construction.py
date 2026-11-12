"""Native map selection for the fixed marked-crosswalk/intersection cell.

Crosswalk vertices are split at CARLA's repeated first vertex.  Geometry must
be on a connected driving route; a config flag alone cannot create a marking.
"""
from __future__ import annotations

from shapely.geometry import LineString, Polygon


def xy(location):
    return (float(location.x), float(location.y))


def crosswalk_polygons(locations):
    polygons, current = [], []
    for location in locations:
        point = xy(location)
        if not current:
            current = [point]
        else:
            current.append(point)
            if point == current[0]:
                if len(current) < 4:
                    raise ValueError('Crosswalk has fewer than three corners')
                shape = Polygon(current)
                if not shape.is_valid or shape.area <= 0:
                    raise ValueError('Invalid Native crosswalk polygon')
                polygons.append(shape)
                current = []
    if current:
        raise ValueError('Unclosed Native crosswalk polygon')
    return polygons


def connected_entry_route(world_map, *, step_m=2.0, max_steps=55):
    """Find a driving route from approach through junction to receiving road."""
    for spawn in world_map.get_spawn_points():
        first = world_map.get_waypoint(spawn.location)
        if first is None or first.is_junction or first.lane_type != first.lane_type.Driving:
            continue
        queue = [(first, [first], False)]
        seen = set()
        while queue:
            current, path, entered = queue.pop(0)
            key = (current.road_id, current.lane_id, round(float(current.s), 1), entered)
            if key in seen or len(path) > max_steps:
                continue
            seen.add(key)
            if entered and not current.is_junction and len(path) >= 5:
                return path
            for nxt in current.next(step_m):
                if nxt.lane_type != nxt.lane_type.Driving:
                    continue
                if not entered and not nxt.is_junction and nxt.road_id != first.road_id:
                    continue
                queue.append((nxt, path + [nxt], entered or nxt.is_junction))
    raise ValueError('No connected Native approach, junction and receiving lane')


def choose_region(world_map, route, kind):
    points = [xy(item.transform.location) for item in route]
    line = LineString(points)
    if kind == 'marked_crosswalk':
        candidates = [polygon for polygon in crosswalk_polygons(world_map.get_crosswalks())
                      if polygon.intersects(line)]
        if len(candidates) != 1:
            raise ValueError('Connected route needs one unambiguous Native marked crosswalk')
        return list(candidates[0].exterior.coords)[:-1]
    if kind == 'intersection':
        junctions = [item.get_junction() for item in route if item.is_junction]
        if not junctions or any(item is None or item.id != junctions[0].id for item in junctions):
            raise ValueError('Connected route lacks one Native intersection')
        box = junctions[0].bounding_box
        center, extent = box.location, box.extent
        corners = [[center.x - extent.x, center.y - extent.y],
                   [center.x + extent.x, center.y - extent.y],
                   [center.x + extent.x, center.y + extent.y],
                   [center.x - extent.x, center.y + extent.y]]
        if not Polygon(corners).intersects(line):
            raise ValueError('Native intersection boundary misses selected route')
        return corners
    raise ValueError('Unknown entry alternative')
