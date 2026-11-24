"""CPU-testable Native controller helpers for planned physical sweeps.

Target setpoints select engineering attempts. Recorded acceleration and route
position, not these requests, determine later physical coverage.
"""
import math

ACCEL_TARGETS_MPS2 = (0.1, 0.15, 0.2)
ROUTE_OFFSETS_M = (25.0, 100.0, 175.0)


def require_target(value, allowed, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if float(value) not in allowed:
        raise ValueError(name + ' is outside the frozen engineering grid')
    return float(value)


def longitudinal_acceleration(acceleration, yaw_degrees):
    """Project original vehicle acceleration onto its current forward heading."""
    if any(not math.isfinite(float(v)) for v in (acceleration.x, acceleration.y, yaw_degrees)):
        raise ValueError('Original acceleration or heading is not finite')
    theta = math.radians(yaw_degrees)
    return acceleration.x * math.cos(theta) + acceleration.y * math.sin(theta)


def throttle_for_acceleration(target_mps2, measured_mps2, prior_throttle):
    target = require_target(target_mps2, ACCEL_TARGETS_MPS2, 'Acceleration target')
    if not math.isfinite(measured_mps2) or not math.isfinite(prior_throttle):
        raise ValueError('Controller feedback must be finite')
    if not 0 <= prior_throttle <= 1:
        raise ValueError('Prior throttle outside normalized controller range')
    # Small bounded feedback step; real vehicle response remains unverified.
    return min(1.0, max(0.0, prior_throttle + 0.3 * (target - measured_mps2)))


def route_waypoint(world_map, spawn_transform, offset_m):
    """Choose one unbranched forward route from the current Native spawn."""
    offset = require_target(offset_m, ROUTE_OFFSETS_M, 'Route offset')
    start = world_map.get_waypoint(spawn_transform.location, project_to_road=True)
    if start is None:
        raise ValueError('Original spawn has no mapped lane')
    options = start.next(offset)
    if len(options) != 1:
        raise ValueError('Route offset has missing or ambiguous forward waypoint')
    selected = options[0]
    if selected.road_id != start.road_id or selected.lane_id != start.lane_id:
        raise ValueError('Route offset changed road or lane identity')
    return selected
