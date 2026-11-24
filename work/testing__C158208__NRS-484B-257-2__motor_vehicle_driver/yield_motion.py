"""Pre-tick vehicle commands for the staged signed-entrance traffic pair."""

import math

from yield_capture import _vertices


def _speed(actor):
    velocity = actor.get_velocity()
    values = (velocity.x, velocity.y, velocity.z)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("Missing finite Native actor velocity")
    return math.sqrt(sum(v * v for v in values))


def _control(target, observed):
    delta = (target - observed) * .25
    return {"throttle": min(1.0, max(0.0, delta)),
            "brake": min(1.0, max(0.0, -delta)), "steer": 0.0}


def apply_motion(world, staging, tick, *, control_factory=None):
    """Use current Native bodies; actual response is measured after the tick."""
    if control_factory is None:
        import carla
        control_factory = carla.VehicleControl
    ego, other, stage = staging["ego"], staging["other"], staging["stage"]
    origin, forward = staging["reference_origin_xy_m"], staging["ego_forward_xy"]
    ego_point = ego.get_location()
    other_point = other.get_location()
    ego_waypoint = world.get_map().get_waypoint(ego_point, project_to_road=False)
    other_waypoint = world.get_map().get_waypoint(other_point, project_to_road=False)
    if (ego_waypoint is None or ego_waypoint.road_id not in (158208, 158210, 158211)
            or other_waypoint is None or other_waypoint.road_id not in (158212, 158213, 158214)):
        raise ValueError("Native actor left the connected signed-intersection routes")
    before = all(sum((point[i] - origin[i]) * forward[i] for i in (0, 1)) < 0
                 for point in _vertices(ego)[0])
    other_clear = other_point.y <= -12.0
    ego_target = 0.0 if ego_point.x >= 55.0 else stage.target_ego_speed(
        before_reference=before, other_body_clear=other_clear)
    other_target = 0.0 if other_point.y <= -55.0 else stage.target_other_speed(tick)
    ego_command, other_command = _control(ego_target, _speed(ego)), _control(other_target, _speed(other))
    ego.apply_control(control_factory(**ego_command))
    other.apply_control(control_factory(**other_command))
    return {"ego_target_mps": ego_target, "other_target_mps": other_target,
            "ego_before_reference": before, "other_clear_by_position": other_clear,
            "ego_command": ego_command, "other_command": other_command}
