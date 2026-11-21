"""Find a Native yield-sign actor whose trigger contains the approach point.

This tests physical sign governance. Official status and properly erected face
still need Native map and original-camera review.
"""

import math


def find_governing_yield_sign(world, approach_waypoint):
    point = approach_waypoint.transform.location
    matches = []
    for sign in world.get_actors().filter("traffic.yield*"):
        if sign.trigger_volume.contains(point, sign.get_transform()):
            matches.append(sign)
    if len(matches) != 1:
        raise ValueError(f"Expected one governing yield sign, found {len(matches)}")
    return matches[0]


def step_ego(distance_to_crossing_m, speed_mps, other_body_inside,
             target_mps=5.0):
    """Plan one 20 Hz approach control step from original body observations.

    The hold is a physical conflict interlock. It does not decide whether the
    sign is official or whether NRS 484B.250(1) applies at this crossing.
    """
    values = (distance_to_crossing_m, speed_mps, target_mps)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("Finite approach distance and speed required")
    if distance_to_crossing_m < 0 or speed_mps < 0 or target_mps <= 0:
        raise ValueError("Nonnegative approach state and positive target required")
    if type(other_body_inside) is not bool:
        raise ValueError("Measured other-body occupancy required")
    distance = float(distance_to_crossing_m)
    speed = float(speed_mps)
    if other_body_inside:
        # Begin braking before the crossing, with a full hold near the line.
        braking_distance = max(3.0, speed * speed / 3.0)
        if distance <= braking_distance:
            return 0.0, min(1.0, max(0.35, speed / max(distance, 0.5))), "hold_for_other_body"
        return min(0.3, max(0.0, (target_mps - speed) * 0.1)), 0.0, "approach_conflict"
    throttle = min(0.5, max(0.0, (target_mps - speed) * 0.18))
    brake = min(0.5, max(0.0, (speed - target_mps) * 0.2))
    return throttle, brake, "clear_body_proceed"
