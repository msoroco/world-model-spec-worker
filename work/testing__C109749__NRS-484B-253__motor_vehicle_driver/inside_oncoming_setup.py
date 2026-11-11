"""Select and spawn an opposing vehicle already inside the chosen junction.

This is construction for the NRS 484B.253 inside-intersection branch. The Native
runner must still record and verify the actor's complete body in the junction.
"""
import math
from shapely.geometry import MultiPoint, Polygon

from capture_sources import actor_sample


def _yaw(waypoint):
    return float(waypoint.transform.rotation.yaw)


def _heading_change(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


def _distance(first, second):
    a, b = first.transform.location, second.transform.location
    return math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y))


def inside_waypoint(selected, *, travel_m=6.0):
    """Find a forward waypoint in the selected opposing lane and junction."""
    if type(travel_m) not in (int, float) or not math.isfinite(travel_m) or travel_m < 4.0:
        raise ValueError('Positive inside-junction travel distance required')
    entry = selected['oncoming']['entry']
    junction_id = selected['junction_id']
    if not entry.is_junction or entry.get_junction().id != junction_id:
        raise ValueError('Opposing entry is not in the selected Native junction')
    candidates = []
    for candidate in entry.next(travel_m):
        if (not candidate.is_junction or candidate.get_junction().id != junction_id or
                candidate.road_id != entry.road_id or candidate.lane_id != entry.lane_id or
                abs(_heading_change(_yaw(entry), _yaw(candidate))) > 25.0 or
                _distance(entry, candidate) < travel_m - 2.0):
            continue
        candidates.append(candidate)
    if not candidates:
        raise ValueError('No same-lane inside-junction opposing spawn waypoint')
    return min(candidates, key=lambda waypoint: abs(_distance(entry, waypoint) - travel_m))


def spawn_inside_opposing(world, selected, *, travel_m=6.0,
                          blueprint_id='vehicle.audi.tt'):
    """Spawn only after the same-junction waypoint check; caller owns cleanup."""
    waypoint = inside_waypoint(selected, travel_m=travel_m)
    blueprint = world.get_blueprint_library().find(blueprint_id)
    blueprint.set_attribute('role_name', 'opposing_vehicle_inside_junction')
    actor = world.try_spawn_actor(blueprint, waypoint.transform)
    if actor is None:
        raise ValueError('Native inside-junction opposing spawn failed')
    return actor


def spawn_inside_pair(world, selected, *, travel_m=6.0,
                      ego_blueprint_id='vehicle.tesla.model3',
                      opposing_blueprint_id='vehicle.audi.tt'):
    """Spawn the subject outside and the opposing actor inside, atomically."""
    inside = inside_waypoint(selected, travel_m=travel_m)
    actors = []
    try:
        for role, blueprint_id, transform in (
                ('ego_left_turn', ego_blueprint_id, selected['ego']['outside'].transform),
                ('opposing_vehicle_inside_junction', opposing_blueprint_id, inside.transform)):
            blueprint = world.get_blueprint_library().find(blueprint_id)
            blueprint.set_attribute('role_name', role)
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Native spawn failed for ' + role)
            actors.append(actor)
        return tuple(actors)
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def verify_inside_body(actor, context):
    """Require the complete spawned body within the sourced junction envelope."""
    polygon = Polygon(context['intersection_polygon_xy_m'])
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError('Invalid Native junction envelope')
    sample = actor_sample(actor)
    body = MultiPoint(sample['body_vertices_xy_m']).convex_hull
    if body.is_empty or not polygon.covers(body):
        raise ValueError('Initial opposing complete body is outside Native junction envelope')
    return sample


def opposing_target_speed(*, ego_body_seen_in_junction, authored_approach_speed_mps):
    """Hold the inside actor until the subject's sourced body reaches the junction."""
    if type(ego_body_seen_in_junction) is not bool:
        raise ValueError('Measured subject junction presence required')
    if (type(authored_approach_speed_mps) not in (int, float) or
            not math.isfinite(authored_approach_speed_mps) or authored_approach_speed_mps <= 0):
        raise ValueError('Positive finite authored opposing approach speed required')
    return authored_approach_speed_mps if ego_body_seen_in_junction else 0.0
