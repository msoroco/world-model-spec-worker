"""CPU-checkable steering along an authored Native crossing route."""
import math
from shapely.geometry import LineString, Point, Polygon


def validate_route(points, approach, entry, label, crossing_polygon=None):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(label + " route needs approach, entry and exit points")
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in point):
            raise ValueError(label + " route needs finite XY points")
    if math.dist(points[0], approach[:2]) > 5 or min(
            math.dist(point, entry[:2]) for point in points[1:-1]) > 5:
        raise ValueError(label + " route differs from reviewed approach or entry")
    if any(math.dist(a, b) < 1 for a, b in zip(points, points[1:])):
        raise ValueError(label + " route has duplicate or near-duplicate points")
    if math.dist(points[-1], entry[:2]) < 3:
        raise ValueError(label + " route has no exit beyond crossing entry")
    if crossing_polygon is not None:
        crossing = Polygon(crossing_polygon)
        if not crossing.is_valid or crossing.area <= 0:
            raise ValueError("Valid crossing polygon required for route")
        if crossing.intersects(Point(points[0])):
            raise ValueError(label + " route starts within crossing")
        if crossing.intersects(Point(points[-1])):
            raise ValueError(label + " route ends within crossing")
        if not LineString(points).intersects(crossing) or not any(
                crossing.contains(Point(point)) for point in points[1:-1]):
            raise ValueError(label + " route does not traverse crossing interior")
    return points


def steering_command(x, y, yaw_deg, points, progress=1, lookahead_m=5.0):
    """Return Native steer (+right) and monotone target index for a route."""
    if any(not math.isfinite(v) for v in (x, y, yaw_deg, lookahead_m)) or lookahead_m <= 0:
        raise ValueError("Finite route controller pose and lookahead required")
    if type(progress) is not int or not 1 <= progress < len(points):
        raise ValueError("Valid route target index required")
    while progress < len(points) - 1 and math.dist((x, y), points[progress]) < lookahead_m:
        progress += 1
    target = points[progress]
    distance = math.dist((x, y), target)
    if distance < 0.01:
        return 0.0, progress
    yaw = math.radians(yaw_deg)
    heading = math.atan2(target[1] - y, target[0] - x)
    error = (heading - yaw + math.pi) % (2 * math.pi) - math.pi
    curvature = 2 * math.sin(error) / max(distance, lookahead_m)
    # CARLA VehicleControl.steer is positive for a right turn.
    steer = -math.atan(2.8 * curvature) / math.radians(35)
    return max(-1.0, min(1.0, steer)), progress
