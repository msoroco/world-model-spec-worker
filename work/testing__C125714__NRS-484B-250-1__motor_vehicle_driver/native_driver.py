"""Lazy CARLA-facing construction and next-tick control for C125714."""
from __future__ import annotations

import math

from crossing_audit import _body_overlaps
from crossing_control import bind_map, ego_request


def _location(carla, x, y):
    return carla.Location(x=x, y=y, z=0)


def spawn_vehicles(world, scene, carla):
    """Bind inspected map and spawn the two owned conventional vehicles."""
    mapping = world.get_map()
    waypoints = bind_map(mapping, scene, lambda x, y: _location(carla, x, y))
    blueprints = world.get_blueprint_library().filter("vehicle.*")
    if not blueprints:
        raise ValueError("No conventional Native vehicle blueprint")
    actors = {}
    try:
        for party in ("ego", "other"):
            blueprint = blueprints[0]
            blueprint.set_attribute("role_name", "c125714_250_1_" + party)
            pose = waypoints[party][0].transform
            actor = world.spawn_actor(blueprint, pose)
            if actor is None:
                raise ValueError("Native spawn failed: " + party)
            actors[party] = actor
        if actors["ego"].id == actors["other"].id:
            raise ValueError("Native actor IDs were reused")
    except BaseException:
        for actor in reversed(list(actors.values())):
            actor.destroy()
        raise
    return actors


def body_polygon(actor):
    """Project all eight original bounding-box vertices to a four-corner hull."""
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("Original Native vehicle body lacks eight vertices")
    points = [(float(v.x), float(v.y)) for v in vertices]
    if not all(math.isfinite(v) for point in points for v in point):
        raise ValueError("Original Native body vertex is non-finite")
    # The vehicle bounding box is a rotated rectangle in the ground plane.
    unique = sorted(set(points))
    if len(unique) != 4:
        raise ValueError("Original Native body projection lacks four corners")
    center = (sum(x for x, _ in unique) / 4, sum(y for _, y in unique) / 4)
    return [list(point) for point in sorted(unique,
            key=lambda p: math.atan2(p[1]-center[1], p[0]-center[0]))]


def control_step(scene, state, *, frame, ego_body, other_body):
    """Compute the next ego request from the just-observed original frame."""
    if type(frame) is not int or frame <= state.get("last_frame", -1):
        raise ValueError("Missing or stale original control frame")
    if state.get("last_frame") is not None and frame != state["last_frame"] + 1:
        raise ValueError("Gap in original control frames")
    bounds = scene["crossing"]["bounds_xy_m"]
    ego_within = _body_overlaps(ego_body, bounds)
    other_within = _body_overlaps(other_body, bounds)
    other_entered = state.get("other_entered", False) or other_within
    route = scene["other_route_xy_m"]
    delta = [route[-1][i]-route[0][i] for i in (0,1)]
    axis = 0 if abs(delta[0]) > abs(delta[1]) else 1
    if delta[axis] == 0:
        raise ValueError("Other route has no crossing direction")
    other_beyond_exit = (min(v[axis] for v in other_body) > bounds[axis+2]
                         if delta[axis] > 0 else
                         max(v[axis] for v in other_body) < bounds[axis])
    other_cleared = state.get("other_cleared", False) or (
        state.get("other_entered", False) and not other_within and other_beyond_exit)
    ego_entered = state.get("ego_entered", False) or ego_within
    request = ego_request(not ego_entered, other_entered, other_cleared,
                          freshness_ok=True,
                          require_other_first=scene["other_entered_first"])
    return {"last_frame": frame, "other_entered": other_entered,
            "other_cleared": other_cleared, "ego_entered": ego_entered,
            "request": request, "source": "original same-frame body polygon overlap"}


def apply_ego(actor, carla, decision):
    """Send the recorded request to the next CARLA tick."""
    if decision["request"] not in ("brake", "proceed"):
        raise ValueError("Unknown next-tick control request")
    hold = decision["request"] == "brake"
    actor.apply_control(carla.VehicleControl(throttle=0.0 if hold else .25,
                                              brake=1.0 if hold else 0.0,
                                              steer=0.0))
