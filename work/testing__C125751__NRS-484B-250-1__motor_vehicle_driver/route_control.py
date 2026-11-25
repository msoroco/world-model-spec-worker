"""Reviewed median-crossing route validation and lazy Native steering."""
import math

from shapely.geometry import LineString, Point, Polygon


def validate_route(points, approach_xy, entry_xy, crossing_polygon, label):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(label + ' needs approach, crossing and exit route points')
    for point in points:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in point)):
            raise ValueError(label + ' needs finite XY route points')
    if (math.dist(points[0], approach_xy) > 5 or
            min(math.dist(point, entry_xy) for point in points[1:-1]) > 5):
        raise ValueError(label + ' route differs from reviewed approach or entry')
    if any(math.dist(a, b) < 1 for a, b in zip(points, points[1:])):
        raise ValueError(label + ' route has duplicate points')
    polygon = Polygon(crossing_polygon)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Valid reviewed crossing polygon required')
    if polygon.intersects(Point(points[0])) or polygon.intersects(Point(points[-1])):
        raise ValueError(label + ' route must start and exit outside crossing')
    if (not LineString(points).intersects(polygon) or
            not any(polygon.contains(Point(point)) for point in points[1:-1])):
        raise ValueError(label + ' route misses crossing interior')
    return points


def validate_pair_routes(plan, routes):
    if not isinstance(routes, dict) or set(routes) != {'ego', 'other'}:
        raise ValueError('Reviewed ego and other routes required')
    for role in ('ego', 'other'):
        approach = plan['approaches'][role]
        validate_route(routes[role], approach['start_xy_m'], approach['entry_xy_m'],
                       plan['crossing_polygon_xy_m'], role)
    return routes


def steering_command(x, y, yaw_deg, points, progress=1, lookahead_m=5.0):
    if (any(not math.isfinite(value) for value in (x, y, yaw_deg, lookahead_m)) or
            lookahead_m <= 0 or type(progress) is not int or
            not 1 <= progress < len(points)):
        raise ValueError('Finite Native pose and valid route progress required')
    while progress < len(points) - 1 and math.dist((x, y), points[progress]) < lookahead_m:
        progress += 1
    target = points[progress]
    distance = math.dist((x, y), target)
    if distance < .01:
        return 0.0, progress
    heading = math.atan2(target[1] - y, target[0] - x)
    error = (heading - math.radians(yaw_deg) + math.pi) % (2 * math.pi) - math.pi
    curvature = 2 * math.sin(error) / max(distance, lookahead_m)
    # Native VehicleControl.steer is positive for a right turn.
    steer = -math.atan(2.8 * curvature) / math.radians(35)
    return max(-1.0, min(1.0, steer)), progress
