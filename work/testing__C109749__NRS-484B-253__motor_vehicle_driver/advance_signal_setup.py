"""Native-lazy upstream ego placement for signal-distance probes.

The returned waypoint is on the same inbound lane as the selected junction
approach. A caller must still capture the full traveled path and actual signal
readback; waypoint distance alone is no proof of statutory signal distance.
"""

import math


def upstream_waypoint(outside, *, additional_m, tolerance_m=2.0):
    if (type(additional_m) not in (int, float) or not math.isfinite(additional_m)
            or additional_m <= 0):
        raise ValueError('Positive finite upstream travel required')
    if type(tolerance_m) not in (int, float) or tolerance_m < 0:
        raise ValueError('Nonnegative waypoint tolerance required')
    start = outside.transform.location
    candidates = []
    for waypoint in outside.previous(additional_m):
        point = waypoint.transform.location
        separation = math.hypot(point.x - start.x, point.y - start.y)
        heading_delta = (waypoint.transform.rotation.yaw - outside.transform.rotation.yaw + 180) % 360 - 180
        if (waypoint.road_id == outside.road_id and waypoint.lane_id == outside.lane_id
                and not waypoint.is_junction and abs(heading_delta) <= 15
                and separation >= additional_m - tolerance_m):
            candidates.append((abs(separation - additional_m), waypoint))
    if not candidates:
        raise ValueError('Same-lane upstream signal-distance waypoint unavailable')
    return min(candidates, key=lambda item: item[0])[1]


def probe_waypoints(outside, *, distances_m=(25.0, 30.48, 36.0), approach_to_turn_m):
    """Return below/at/above 30.48 m spawn targets with actual lane checks."""
    if (type(approach_to_turn_m) not in (int, float) or
            not math.isfinite(approach_to_turn_m) or approach_to_turn_m <= 0):
        raise ValueError('Positive finite existing approach length required')
    result = {}
    for distance in distances_m:
        if distance <= approach_to_turn_m:
            raise ValueError('Probe cannot start before existing approach waypoint')
        result[distance] = upstream_waypoint(outside, additional_m=distance-approach_to_turn_m)
    return result
