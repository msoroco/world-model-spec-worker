"""Pure CPU checks and control decisions for a sourced median-opening scene.

The site coordinates, lane identities and sign are inputs from Native review. This
module never chooses a map site or concludes that a stop sign is official.
"""
import math
from shapely.geometry import LineString, Point, Polygon


def _xy(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ):
        raise ValueError(label + " needs finite XY coordinates")
    return tuple(float(v) for v in value)


def validate_scene(scene):
    """Require two surveyed approaches to one crossing and a sign on ego's lane."""
    polygon = Polygon(scene["crossing_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("A valid surveyed median crossing is required")
    if scene.get("same_statutory_crossing") is not True:
        raise ValueError("One statutory median crossing must be source reviewed")
    approaches = scene["approaches"]
    if set(approaches) != {"ego", "other"}:
        raise ValueError("Ego and other approach required")
    relation = scene["approach_relation"]
    ego, other = approaches["ego"], approaches["other"]
    if relation == "different_highways":
        if ego["highway_id"] == other["highway_id"]:
            raise ValueError("Different-highway case has one highway")
    elif relation == "opposite_directions":
        if ego["highway_id"] != other["highway_id"]:
            raise ValueError("Opposite-direction case needs one highway")
        ex, ey = _xy(ego["forward_xy"], "ego forward")
        ox, oy = _xy(other["forward_xy"], "other forward")
        magnitude = math.hypot(ex, ey) * math.hypot(ox, oy)
        if magnitude == 0:
            raise ValueError("Nonzero approach headings required")
        dot = (ex * ox + ey * oy) / magnitude
        if dot > -.8 or not scene.get("other_left_turn_intended"):
            raise ValueError("Opposite headings and sourced left-turn intention required")
    else:
        raise ValueError("Unknown approach relation")
    sign = scene["stop_sign"]
    if sign.get("governed_lane_id") != ego["lane_id"] or not sign.get("native_id"):
        raise ValueError("Stop sign must govern the ego entrance")
    for role, entry in approaches.items():
        route = [_xy(p, role + " route") for p in entry["route_xy_m"]]
        if len(route) < 3 or polygon.intersects(Point(route[0])) or polygon.intersects(Point(route[-1])):
            raise ValueError(role + " route needs outside approach and exit")
        if not LineString(route).intersects(polygon) or not any(
            polygon.contains(Point(p)) for p in route[1:-1]
        ):
            raise ValueError(role + " route misses crossing interior")
        if any(math.dist(a, b) < 1 for a, b in zip(route, route[1:])):
            raise ValueError(role + " route has duplicate points")
    stop = _xy(scene["ego_stop_line_xy_m"], "stop line")
    route = [_xy(p, "ego route") for p in ego["route_xy_m"]]
    if polygon.intersects(Point(stop)) or LineString(route[:2]).distance(Point(stop)) > 3:
        raise ValueError("Stop line must lie on ego approach before crossing")
    return scene


def stop_yield_control(distance_to_stop_m, speed_mps, stopped_once, conflict_clear,
                       target_speed_mps=5.0):
    """Return throttle, brake, release state. A real stop is mandatory before release."""
    for value in (distance_to_stop_m, speed_mps, target_speed_mps):
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("Finite stop-control telemetry required")
    if distance_to_stop_m < -0.5 and not stopped_once:
        raise ValueError("Ego passed stop line without a recorded stop")
    if not stopped_once:
        # Conservative engineering deceleration, not a legal stopping-distance rule.
        braking_distance = speed_mps * speed_mps / (2 * 3.0) + 1.0
        if distance_to_stop_m <= braking_distance:
            stopped_once = speed_mps <= .1 and abs(distance_to_stop_m) <= 1.0
            return 0.0, 1.0, stopped_once
        return min(.35, max(.0, (target_speed_mps - speed_mps) * .15)), 0.0, False
    if not conflict_clear:
        return 0.0, 1.0, True
    return min(.45, max(.0, (target_speed_mps - speed_mps) * .18)), 0.0, True
