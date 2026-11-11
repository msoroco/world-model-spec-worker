"""Measured-feedback attempt to let the right-hand participant clear."""
import math

from shapely.geometry import MultiPoint, Polygon


def body_in_crossing(actor, crossing_polygon_xy_m):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = [(float(v.x), float(v.y)) for v in vertices]
    if len(points) < 4 or any(not math.isfinite(value) for point in points for value in point):
        raise ValueError("Complete finite Native body required")
    body = MultiPoint(points).convex_hull
    crossing = Polygon(crossing_polygon_xy_m)
    if body.area <= 0 or not crossing.is_valid or crossing.area <= 0:
        raise ValueError("Valid body and crossing required")
    return body.intersects(crossing)


def right_hand_hold(other_inside, other_entered_once):
    if type(other_inside) is not bool or type(other_entered_once) is not bool:
        raise ValueError("Measured Boolean other-body state required")
    seen = other_entered_once or other_inside
    return not seen or other_inside, seen


def near_time_entry_hold(other_inside, other_entered_once):
    """Release only after the right-hand body enters; timing stays measured.

    This is an attempted approach-order controller, not a legal yield decision.
    A later physical review must check interaction safety and actual entry delta.
    """
    if type(other_inside) is not bool or type(other_entered_once) is not bool:
        raise ValueError("Measured Boolean other-body state required")
    seen = other_entered_once or other_inside
    return not seen, seen


def apply_speed_control(carla, actor, target_speed_mps, hold, steer=0.0):
    if type(target_speed_mps) not in (int, float) or not math.isfinite(target_speed_mps) or target_speed_mps <= 0:
        raise ValueError("Positive finite requested speed required")
    velocity = actor.get_velocity()
    speed = math.sqrt(float(velocity.x)**2 + float(velocity.y)**2 + float(velocity.z)**2)
    if not math.isfinite(speed):
        raise ValueError("Finite Native velocity feedback required")
    if type(steer) not in (int, float) or not math.isfinite(steer) or not -1 <= steer <= 1:
        raise ValueError("Finite normalized steering required")
    control = carla.VehicleControl()
    control.steer = steer
    control.throttle = 0.0 if hold else max(0.0, min(0.65, 0.18 + 0.16 * (target_speed_mps - speed)))
    control.brake = 1.0 if hold else min(0.4, max(0.0, 0.3 * (speed - target_speed_mps)))
    actor.apply_control(control)
    return {"measured_speed_mps": speed, "hold": bool(hold),
            "throttle": control.throttle, "brake": control.brake,
            "steer": control.steer}
