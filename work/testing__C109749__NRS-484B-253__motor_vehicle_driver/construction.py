"""Select a real connected junction and spawn an opposing left-turn pair.

This module does not import CARLA. The Native runner passes CARLA map/world
objects after the operator supplies its dedicated server.
"""

import math


def _yaw(waypoint):
    return float(waypoint.transform.rotation.yaw)


def _delta(a, b):
    return (b - a + 180) % 360 - 180


def _location(waypoint):
    point = waypoint.transform.location
    return (float(point.x), float(point.y))


def _distance(a, b):
    return math.dist(_location(a), _location(b))


def _next(waypoint, step_m):
    return list(waypoint.next(step_m))


def _previous(waypoint, step_m):
    return list(waypoint.previous(step_m))


def inbound_entries(carla_map, *, step_m=4.0, max_steps=30,
                    minimum_approach_m=35.0):
    """Find exterior waypoints whose forward route enters a Native junction."""
    candidates = []
    seen = set()
    for starting in carla_map.generate_waypoints(step_m):
        if starting.is_junction or not str(getattr(starting, "lane_type", "")).lower().endswith("driving"):
            continue
        frontier = [(starting, 0)]
        while frontier:
            current, steps = frontier.pop()
            if steps >= max_steps:
                continue
            for following in _next(current, step_m):
                if following.is_junction:
                    junction = following.get_junction()
                    approach_length = _distance(starting, current)
                    key = (junction.id, starting.road_id, starting.lane_id,
                           round(starting.s / step_m))
                    if approach_length >= minimum_approach_m and key not in seen:
                        seen.add(key)
                        candidates.append({"outside": starting, "entry": following,
                                           "junction_id": junction.id,
                                           "approach_length_m": approach_length})
                elif abs(_delta(_yaw(starting), _yaw(following))) <= 30:
                    frontier.append((following, steps + 1))
    return candidates


def left_exit(entry, *, step_m=4.0, max_steps=18):
    """Find a connected exit roughly 90 degrees left of the inbound heading."""
    initial = _yaw(entry["outside"])
    frontier = [(entry["entry"], [entry["entry"]], 0)]
    seen = set()
    while frontier:
        waypoint, path, steps = frontier.pop(0)
        if steps > max_steps:
            continue
        key = (waypoint.road_id, waypoint.lane_id, round(waypoint.s / step_m))
        if key in seen:
            continue
        seen.add(key)
        if not waypoint.is_junction:
            change = _delta(initial, _yaw(waypoint))
            if -135 <= change <= -45:
                return path
            continue
        for candidate in _next(waypoint, step_m):
            if candidate.is_junction and candidate.get_junction().id != entry["junction_id"]:
                continue
            frontier.append((candidate, path + [candidate], steps + 1))
    return None


def select_intersection(carla_map):
    """Return a same-junction opposing pair and a connected left exit."""
    entries = inbound_entries(carla_map)
    for ego in entries:
        route = left_exit(ego)
        if route is None:
            continue
        for other in entries:
            if other is ego or other["junction_id"] != ego["junction_id"]:
                continue
            if abs(abs(_delta(_yaw(ego["outside"]), _yaw(other["outside"]))) - 180) > 25:
                continue
            if _distance(ego["outside"], other["outside"]) < 10:
                continue
            return {"ego": ego, "oncoming": other, "left_route": route,
                    "junction_id": ego["junction_id"]}
    raise ValueError("No connected opposing approaches with a left exit in Native map")


def spawn_pair(world, selected, *, ego_blueprint="vehicle.tesla.model3",
               oncoming_blueprint="vehicle.audi.tt"):
    """Spawn both actors at selected Native waypoints; caller owns cleanup."""
    library = world.get_blueprint_library()
    actors = []
    try:
        for role, blueprint_id, entry in (
            ("ego_left_turn", ego_blueprint, selected["ego"]),
            ("opposing_vehicle", oncoming_blueprint, selected["oncoming"]),
        ):
            blueprint = library.find(blueprint_id)
            blueprint.set_attribute("role_name", role)
            actor = world.try_spawn_actor(blueprint, entry["outside"].transform)
            if actor is None:
                raise ValueError("Native spawn failed for " + role)
            actors.append(actor)
        return tuple(actors)
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def spawn_reciprocal_vehicle(world, selected, *, behind_m=25.0,
                             blueprint_id='vehicle.audi.tt'):
    """Spawn a later opposing approach on the same Native lane.

    The first opposing actor can clear the initial yield conflict. A distinct
    later actor is then needed to observe the reciprocal yield after the turn
    starts. This function never silently places it on another lane.
    """
    if type(behind_m) not in (int,float) or not math.isfinite(behind_m) or behind_m < 15:
        raise ValueError('Positive later-opposing separation required')
    first = selected['oncoming']['outside']
    previous = _previous(first,behind_m)
    matching = [waypoint for waypoint in previous
                if waypoint.road_id == first.road_id and waypoint.lane_id == first.lane_id
                and abs(_delta(_yaw(waypoint),_yaw(first))) <= 15
                and _distance(waypoint,first) >= behind_m-2]
    if not matching:
        raise ValueError('No same-lane later opposing spawn waypoint')
    waypoint = min(matching,key=lambda item:abs(_distance(item,first)-behind_m))
    blueprint = world.get_blueprint_library().find(blueprint_id)
    blueprint.set_attribute('role_name','later_opposing_vehicle')
    actor = world.try_spawn_actor(blueprint,waypoint.transform)
    if actor is None:
        raise ValueError('Native later opposing spawn failed')
    return actor
