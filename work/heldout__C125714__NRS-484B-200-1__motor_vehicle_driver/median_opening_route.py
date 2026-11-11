"""Select a directed route against an authored median-opening map reference.

The reference is an engineering scene declaration.  A matched map and waypoint
sequence do not establish that the median mesh is physically open in CARLA.
"""

from types import SimpleNamespace

from directed_geometry import directed_road_section
from right_half_route import select_two_way_route


def _inside(point, polygon):
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        previous = current
    return inside


def _validate_reference(reference):
    if not isinstance(reference, dict) or not reference.get('source'):
        raise ValueError('Median-opening map source required')
    if not reference.get('map_name') or not isinstance(reference.get('road_id'), int):
        raise ValueError('Median-opening map and road identity required')
    if not isinstance(reference.get('lane_id'), int) or reference['lane_id'] == 0:
        raise ValueError('Median-opening directed lane identity required')
    polygon = reference.get('opening_polygon_xy')
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError('Median-opening polygon requires at least three vertices')
    if any(not isinstance(p, list) or len(p) != 2 or
           any(not isinstance(v, (int, float)) for v in p) for p in polygon):
        raise ValueError('Median-opening polygon requires finite XY vertices')
    from math import isfinite
    if any(not isfinite(v) for p in polygon for v in p):
        raise ValueError('Median-opening polygon requires finite XY vertices')
    area2 = sum(polygon[i][0] * polygon[(i + 1) % len(polygon)][1] -
                polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
                for i in range(len(polygon)))
    if abs(area2) < 1e-6:
        raise ValueError('Median-opening polygon has zero area')
    return polygon


def select_median_opening_route(world_map, reference, *, direction='east',
                                minimum_opening_samples=2):
    polygon = _validate_reference(reference)
    if world_map.name != reference['map_name']:
        raise ValueError('Median-opening source map differs from loaded map')
    if minimum_opening_samples < 2:
        raise ValueError('Median-opening route requires two sampled center points')
    for spawn in world_map.get_spawn_points():
        # Reuse the baseline route continuity and opposing-lane checks for each
        # candidate, then bind its sampled center boundary to the authored opening.
        candidate_map = SimpleNamespace(
            get_spawn_points=lambda spawn=spawn: [spawn],
            get_waypoint=world_map.get_waypoint)
        try:
            route = select_two_way_route(candidate_map, desired_direction=direction)
        except ValueError:
            continue
        if any(w.road_id != reference['road_id'] or
               w.lane_id != reference['lane_id'] for w in route):
            continue
        opening_samples = [
            i for i, waypoint in enumerate(route)
            if _inside(directed_road_section(
                waypoint, waypoint.get_left_lane())['roadway_center_point_xy'], polygon)
        ]
        if len(opening_samples) >= minimum_opening_samples and all(
                b == a + 1 for a, b in zip(opening_samples, opening_samples[1:])):
            return route, opening_samples
    raise ValueError('No directed route crosses the sourced median-opening polygon')
