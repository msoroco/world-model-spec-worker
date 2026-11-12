"""Pre-tick Native motion commands for the staged yield-sign cases.

These target speeds create the intended comparison. They do not determine
whether a through vehicle is an immediate hazard or whether the ego yielded.
"""

import math

from yield_controller import speed_control
from yield_capture_sources import INTERSECTION_ENTRY_X

THROUGH_CLEAR_Y_M = 12.0
THROUGH_TARGET_MPS = 7.0
EGO_END_X_M = 55.0
THROUGH_END_Y_M = 50.0


def _speed(actor):
    v = actor.get_velocity()
    value = math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z)
    if not math.isfinite(value):
        raise ValueError('Missing original actor velocity')
    return value


def apply_motion(world, staging, *, control_factory=None):
    """Read current Native state and apply controls before the next world tick."""
    if control_factory is None:
        import carla
        control_factory = carla.VehicleControl
    ego = staging['ego']
    through = staging['through']
    stage = staging['stage']
    ego_point = ego.get_location()
    waypoint = world.get_map().get_waypoint(ego_point, project_to_road=False)
    if waypoint is None or waypoint.road_id not in (158190, 158192, 158193):
        raise ValueError('Ego left the authored one-way approach/crossing route')
    within = waypoint.road_id in (158192, 158193)
    distance = max(0.0, INTERSECTION_ENTRY_X - ego_point.x)
    through_clear = through is None or through.get_location().y >= THROUGH_CLEAR_Y_M
    ego_target = stage.target(distance, within_intersection=within,
                              through_vehicle_clear=through_clear)
    if ego_point.x >= EGO_END_X_M:
        ego_target = 0.0
    ego_command = speed_control(ego_target, _speed(ego))
    ego.apply_control(control_factory(**ego_command))
    through_command = None
    if through is not None:
        through_target = (0.0 if through.get_location().y >= THROUGH_END_Y_M
                          else THROUGH_TARGET_MPS)
        through_command = speed_control(through_target, _speed(through))
        through.apply_control(control_factory(**through_command))
    return {'ego_target_mps': ego_target,
            'through_target_mps': None if through is None else through_target,
            'through_clear_by_position': through_clear,
            'ego_within_or_beyond_junction': within,
            'distance_to_intersection_m': distance,
            'ego_command': ego_command, 'through_command': through_command}
