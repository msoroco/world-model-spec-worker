"""Find a Native stop-sign actor whose trigger contains the approach point.

This tests physical sign governance. Official status and properly erected face
still need Native map and original-camera review.
"""

import math
from contextlib import contextmanager

from shapely.geometry import Point, Polygon


def _pose(value, label):
    if (not isinstance(value, list) or len(value) != 4 or
            any(type(n) not in (int, float) or not math.isfinite(n) for n in value)):
        raise ValueError("Finite x,y,z,yaw pose required: " + label)
    return value


def validate_site(site):
    """Validate reviewed construction inputs without treating them as Native proof."""
    if not isinstance(site, dict):
        raise ValueError("Reviewed site packet required")
    for key in ("native_map_name", "crossing_source", "median_opening_source",
                "different_highways_source", "device_inventory_source",
                "sign_erection_source", "camera_plan_source"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError("Missing site source: " + key)
    if type(site.get("junction_id")) is not int:
        raise ValueError("Native junction identity required")
    highways = site.get("highway_ids")
    if (not isinstance(highways, dict) or set(highways) != {"ego", "other"} or
            not all(isinstance(v, str) and v for v in highways.values()) or
            highways["ego"] == highways["other"]):
        raise ValueError("Distinct sourced highway identities required")
    for role in ("ego", "other"):
        for phase in ("approach", "entry"):
            _pose(site.get(role + "_" + phase), role + " " + phase)
    coords = site.get("crossing_polygon_xy_m")
    if not isinstance(coords, list) or len(coords) < 3:
        raise ValueError("Sourced crossing polygon required")
    for pair in coords:
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(type(n) not in (int, float) or not math.isfinite(n) for n in pair)):
            raise ValueError("Finite crossing polygon vertex required")
    polygon = Polygon(coords)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Valid crossing polygon required")
    for role in ("ego", "other"):
        approach = site[role + "_approach"]
        entry = site[role + "_entry"]
        if polygon.intersects(Point(approach[:2])) or not polygon.contains(Point(entry[:2])):
            raise ValueError("Approach outside and entry inside crossing required: " + role)
        dx, dy = entry[0] - approach[0], entry[1] - approach[1]
        if dx * math.cos(math.radians(approach[3])) + dy * math.sin(math.radians(approach[3])) <= 0:
            raise ValueError("Approach points away from crossing: " + role)
    return polygon


def _waypoint(world_map, transform):
    waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
    if waypoint is None:
        raise ValueError("Native pose does not lie on a road")
    return waypoint


@contextmanager
def construct_candidate(world, site, transforms, blueprint):
    """Check both Native approaches and own both spawned vehicle lifetimes.

    Site source strings identify review inputs. This code cannot certify that a
    sign is official, properly erected or visible in original camera pixels.
    """
    validate_site(site)
    world_map = world.get_map()
    if world_map.name != site["native_map_name"]:
        raise ValueError("Native map differs from reviewed site")
    waypoints = {key: _waypoint(world_map, transforms[key]) for key in
                 ("ego_approach", "ego_entry", "other_approach", "other_entry")}
    if waypoints["ego_approach"].road_id == waypoints["other_approach"].road_id:
        raise ValueError("Different Native approach roads required")
    for role in ("ego", "other"):
        entry = waypoints[role + "_entry"]
        junction = entry.get_junction() if entry.is_junction else None
        if junction is None or junction.id != site["junction_id"]:
            raise ValueError("Entry outside selected Native junction: " + role)
    sign_waypoint = (waypoints["ego_approach"] if "ego_sign_check" not in transforms
                     else _waypoint(world_map, transforms["ego_sign_check"]))
    if sign_waypoint.road_id != waypoints["ego_approach"].road_id:
        raise ValueError("Stop sign check is not on ego approach road")
    sign = find_governing_stop_sign(world, sign_waypoint)
    if sign.trigger_volume.contains(waypoints["other_approach"].transform.location,
                                    sign.get_transform()):
        raise ValueError("Selected sign also governs other approach")
    actors = []
    try:
        for role in ("ego", "other"):
            actor = world.try_spawn_actor(blueprint, transforms[role + "_approach"])
            if actor is None:
                raise ValueError("Native vehicle spawn failed: " + role)
            actors.append(actor)
        yield {"ego": actors[0], "other": actors[1], "stop_sign": sign,
               "junction_id": site["junction_id"],
               "approach_road_ids": {role: waypoints[role + "_approach"].road_id
                                     for role in ("ego", "other")},
               "highway_ids": site["highway_ids"]}
    finally:
        for actor in reversed(actors):
            actor.destroy()


def find_governing_stop_sign(world, approach_waypoint):
    point = approach_waypoint.transform.location
    matches = []
    for sign in world.get_actors().filter("traffic.stop*"):
        if sign.trigger_volume.contains(point, sign.get_transform()):
            matches.append(sign)
    if len(matches) != 1:
        raise ValueError(f"Expected one governing stop sign, found {len(matches)}")
    return matches[0]
