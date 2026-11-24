"""Spawn the exact signed-entrance traffic pair on the selected Native map."""

from contextlib import contextmanager

from yield_site import validate_native_site
from yield_stage import Stage

VEHICLE = "vehicle.tesla.model3"
EGO_START_XY = (-60.0, 1.8)


def _waypoint(world, location, road_id, lane_id, junction):
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if (waypoint is None or waypoint.road_id != road_id or waypoint.lane_id != lane_id
            or bool(waypoint.is_junction) != junction):
        raise ValueError("Exact actor spawn is off its Native connected lane")
    return waypoint


def _spawn(world, point, road_id, lane_id, junction, location_factory):
    location = location_factory(x=point[0], y=point[1], z=.25)
    waypoint = _waypoint(world, location, road_id, lane_id, junction)
    blueprint = world.get_blueprint_library().find(VEHICLE)
    if blueprint is None:
        raise ValueError("Missing Native motor vehicle blueprint")
    actor = world.try_spawn_actor(blueprint, waypoint.transform)
    if actor is None:
        raise ValueError("Native motor vehicle spawn failed")
    try:
        _waypoint(world, actor.get_location(), road_id, lane_id, junction)
        if actor.type_id != VEHICLE:
            raise ValueError("Native actor blueprint differs")
    except BaseException:
        actor.destroy()
        raise
    return actor


@contextmanager
def stage_case(world, stage: Stage, *, location_factory=None, officer_factory=None):
    """Own only spawned actors; require real officer-source construction hook."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    site = validate_native_site(world, other_stop=stage.other_stop_sign,
                                location_factory=location_factory)
    owned = []
    try:
        ego = _spawn(world, EGO_START_XY, 158208, -1, False, location_factory)
        owned.append(ego)
        other_road = 158212 if stage.kind == "yield_other_approaching" else 158213
        other = _spawn(world, stage.other_start_xy_m, other_road, -1,
                       other_road == 158213, location_factory)
        owned.append(other)
        if ego.id == other.id:
            raise ValueError("Native actor identities reused")
        officer = None
        if stage.officer_control_source_required:
            if officer_factory is None:
                raise ValueError("Officer exception requires sourced Native officer construction")
            officer = officer_factory(world, location_factory)
            if officer is None or officer.id in (ego.id, other.id):
                raise ValueError("Officer source lacks distinct Native actor")
            owned.append(officer)
        yield {"ego": ego, "other": other, "officer": officer, "site": site,
               "stage": stage, "other_spawn_point_xy_m": stage.other_start_xy_m}
    finally:
        for actor in reversed(owned):
            actor.destroy()
