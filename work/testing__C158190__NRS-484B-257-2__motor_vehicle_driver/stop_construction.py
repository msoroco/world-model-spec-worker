"""Stage the stop-sign junction cases in an operator-owned Native world.

This module has no CARLA import or server connection during CPU checks. The
signal-control exception needs a separate authored control variant.
"""

from contextlib import contextmanager
import math

from stop_site import opendrive_to_carla, validate_native_site


PREFIX = 'testing__C158190__NRS-484B-257-2__motor_vehicle_driver__'
EGO_BLUEPRINT = 'vehicle.tesla.model3'
OTHER_BLUEPRINT = 'vehicle.tesla.model3'
EGO_POINT = opendrive_to_carla(-60.0, -1.8)
OTHER_APPROACH = opendrive_to_carla(1.8, -45.0)
OTHER_INSIDE = opendrive_to_carla(1.8, -4.0)
SUPPORTED = {
    PREFIX + 'stop_other_inside',
    PREFIX + 'stop_other_approaching',
    PREFIX + 'stop_no_other',
    PREFIX + 'stop_no_halt',
}


class StopStage:
    """Engineering speed targets; actual stop and yielding require source review."""

    def __init__(self, case_id, *, hold_frames=12):
        self.plan = plan_case(case_id)
        if type(hold_frames) is not int or hold_frames < 2:
            raise ValueError('Invalid requested stop hold')
        self.hold_frames = hold_frames
        self.stopped_frames = 0
        self.released = False

    def target(self, distance_to_reference_m, observed_speed_mps, *,
               before_reference, within_intersection, other_clear):
        if any(not isinstance(v, (int, float)) or isinstance(v, bool)
               or not math.isfinite(v) or v < 0 for v in
               (distance_to_reference_m, observed_speed_mps)):
            raise ValueError('Missing finite Native speed or stop-reference distance')
        if any(type(v) is not bool for v in
               (before_reference, within_intersection, other_clear)):
            raise ValueError('Missing Native road/crossing state')
        if self.plan['rolling_response_requested']:
            return 4.0 if distance_to_reference_m <= 18 else 8.0
        if within_intersection:
            return 5.0
        if self.released:
            return 5.0
        if before_reference and distance_to_reference_m <= 3.0:
            if observed_speed_mps <= .05:
                self.stopped_frames += 1
            else:
                self.stopped_frames = 0
            if self.stopped_frames >= self.hold_frames and other_clear:
                self.released = True
                return 5.0
            return 0.0
        if not before_reference:
            raise ValueError('Ego crossed stop reference without staged halt')
        return 3.0 if distance_to_reference_m <= 18 else 8.0


def plan_case(case_id):
    if case_id not in SUPPORTED:
        raise ValueError('Case needs a different control construction: ' + case_id)
    suffix = case_id.removeprefix(PREFIX)
    other_point = (None if suffix == 'stop_no_other' else
                   OTHER_INSIDE if suffix == 'stop_other_inside' else OTHER_APPROACH)
    return {'case_id': case_id, 'ego_point_xy_m': EGO_POINT,
            'other_point_xy_m': other_point,
            'other_start_road_id': None if other_point is None else
            158195 if suffix == 'stop_other_inside' else 158194,
            'rolling_response_requested': suffix == 'stop_no_halt'}


def _waypoint(world, location, road_id, lane_id):
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road_id, lane_id):
        raise ValueError('Selected spawn point is not on the authored lane')
    return waypoint


def _spawn(world, blueprint_id, waypoint, road_id, lane_id):
    blueprint = world.get_blueprint_library().find(blueprint_id)
    if blueprint is None:
        raise ValueError('Missing Native motor-vehicle blueprint: ' + blueprint_id)
    actor = world.try_spawn_actor(blueprint, waypoint.transform)
    if actor is None:
        raise ValueError('Native actor could not spawn at selected point')
    try:
        actual = _waypoint(world, actor.get_location(), road_id, lane_id)
        if actor.type_id != blueprint_id or actual.is_junction != waypoint.is_junction:
            raise ValueError('Native actor identity or junction location differs')
    except BaseException:
        actor.destroy()
        raise
    return actor


@contextmanager
def stage_case(world, case_id, *, location_factory=None):
    """Read back the map and stage exactly the selected participants."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    plan = plan_case(case_id)
    site = validate_native_site(world, location_factory=location_factory)
    owned = []
    try:
        x, y = plan['ego_point_xy_m']
        ego_location = location_factory(x=x, y=y, z=.25)
        ego = _spawn(world, EGO_BLUEPRINT,
                     _waypoint(world, ego_location, 158190, -1), 158190, -1)
        owned.append(ego)
        other = None
        if plan['other_point_xy_m'] is not None:
            x, y = plan['other_point_xy_m']
            road_id = plan['other_start_road_id']
            other_location = location_factory(x=x, y=y, z=.25)
            other = _spawn(world, OTHER_BLUEPRINT,
                           _waypoint(world, other_location, road_id, -1), road_id, -1)
            owned.append(other)
            if other.id == ego.id:
                raise ValueError('Native actor identity reused for both roles')
        yield {'ego': ego, 'other': other, 'site': site, 'plan': plan}
    finally:
        for actor in reversed(owned):
            actor.destroy()
