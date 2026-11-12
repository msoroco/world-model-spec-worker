"""Native actor staging for the selected C158190 yield-sign comparison.

The world must be a dedicated operator-owned CARLA world loaded from the
authored site. This module has no CARLA import or server contact at import time.
"""
from contextlib import contextmanager

from yield_site import opendrive_to_carla, validate_native_site
from yield_controller import Stage, PREFIX

EGO_BLUEPRINT = 'vehicle.tesla.model3'
THROUGH_BLUEPRINT = 'vehicle.tesla.model3'
EGO_POINT = opendrive_to_carla(-60.0, -1.8)
THROUGH_APPROACH = opendrive_to_carla(1.8, -45.0)
THROUGH_ENTERED = opendrive_to_carla(1.8, -4.0)


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
    """Spawn exact-case actors, then destroy only actors this function owns."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    stage = Stage(case_id)
    site = validate_native_site(world, location_factory=location_factory)
    suffix = case_id.removeprefix(PREFIX)
    through_point = (THROUGH_ENTERED if suffix == 'yield_nearest_view_through_entered'
                     else THROUGH_APPROACH)
    owned = []
    try:
        ego_location = location_factory(x=EGO_POINT[0], y=EGO_POINT[1], z=.25)
        ego_waypoint = _waypoint(world, ego_location, 158190, -1)
        ego = _spawn(world, EGO_BLUEPRINT, ego_waypoint, 158190, -1)
        owned.append(ego)
        through = None
        if suffix != 'yield_nearest_view_clear':
            through_location = location_factory(x=through_point[0], y=through_point[1], z=.25)
            through_road = 158195 if suffix == 'yield_nearest_view_through_entered' else 158194
            through_waypoint = _waypoint(world, through_location, through_road, -1)
            through = _spawn(world, THROUGH_BLUEPRINT, through_waypoint, through_road, -1)
            owned.append(through)
            if ego.id == through.id:
                raise ValueError('Native actor identity reused for two roles')
        yield {'ego': ego, 'through': through, 'site': site, 'stage': stage,
               'through_spawn_point_xy_m': None if through is None else through_point}
    finally:
        for actor in reversed(owned):
            actor.destroy()
