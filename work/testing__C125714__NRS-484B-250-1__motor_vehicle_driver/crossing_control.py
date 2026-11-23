"""Portable route and precedence controller core; CARLA binding remains pending."""
from __future__ import annotations

import hashlib
import math

from crossing_audit import _inside


def validate_routes(scene):
    """Check that two authored routes traverse one physically identified crossing."""
    crossing = scene["crossing"]
    bounds = crossing["bounds_xy_m"]
    if not crossing.get("map_source_sha256") or not crossing.get("crossing_id"):
        raise ValueError("source-hashed map and crossing identity required")
    relation = scene.get("approach_relation", "crossing")
    if relation not in ("crossing", "opposite"):
        raise ValueError("approach relation not established")
    if relation == "crossing" and scene["ego_highway"] == scene["other_highway"]:
        raise ValueError("distinct highway identities required")
    if relation == "opposite" and scene["ego_highway"] != scene["other_highway"]:
        raise ValueError("opposite approaches require one highway identity")
    directions = []
    for party in ("ego", "other"):
        route = scene[f"{party}_route_xy_m"]
        if len(route) < 3 or _inside(route[0], bounds) or _inside(route[-1], bounds):
            raise ValueError(f"{party} route must start and end outside crossing")
        if not any(_inside(p, bounds) for p in route[1:-1]):
            raise ValueError(f"{party} route misses crossing")
        directions.append((route[1][0] - route[0][0], route[1][1] - route[0][1]))
    dot = sum(a*b for a, b in zip(*directions))
    norms = (sum(x*x for x in directions[0]) * sum(x*x for x in directions[1])) ** 0.5
    if norms == 0:
        raise ValueError("route direction is undefined")
    cosine = dot / norms
    if relation == "crossing" and abs(cosine) > 0.5:
        raise ValueError("routes do not form a crossing approach")
    if relation == "opposite" and cosine > -0.8:
        raise ValueError("routes do not form an opposite approach")
    if relation == "opposite":
        route = scene["other_route_xy_m"]
        departure = (route[-1][0]-route[-2][0], route[-1][1]-route[-2][1])
        length = (sum(x*x for x in directions[1]) * sum(x*x for x in departure)) ** 0.5
        if length == 0:
            raise ValueError("opposite departure direction is undefined")
        signed_turn = (directions[1][0]*departure[1] -
                       directions[1][1]*departure[0]) / length
        observed_left_path = signed_turn > 0.8
        if observed_left_path != scene.get("left_turn_realized", False):
            raise ValueError("left-turn route differs from declared realization")
    return {"crossing_id": crossing["crossing_id"], "map_source_sha256": crossing["map_source_sha256"]}


def ego_request(ego_before_crossing, other_entered, other_cleared, freshness_ok,
                require_other_first=True):
    """Fail-closed engineering request; observed behavior is measured separately."""
    if not freshness_ok:
        return "brake"
    if ego_before_crossing and require_other_first:
        if not other_entered or not other_cleared:
            return "brake"
    return "proceed"


def bind_map(world_map, scene, location_factory):
    """Check authored routes against the live OpenDRIVE map before any spawn.

    The factory creates CARLA Locations in production and trivial points in CPU
    tests. No simulator module is imported at module load.
    """
    validate_routes(scene)
    actual_hash = hashlib.sha256(world_map.to_opendrive().encode()).hexdigest()
    if actual_hash != scene["crossing"]["map_source_sha256"]:
        raise ValueError("live OpenDRIVE map hash differs from inspected source")
    bound = {}
    bounds = scene["crossing"]["bounds_xy_m"]
    for party in ("ego", "other"):
        route = scene[f"{party}_route_xy_m"]
        waypoints = []
        for x, y in route:
            waypoint = world_map.get_waypoint(location_factory(x, y), project_to_road=False)
            if waypoint is None:
                raise ValueError(f"{party} route point is not on a drivable lane")
            location = waypoint.transform.location
            if math.hypot(location.x-x, location.y-y) > 2:
                raise ValueError(f"{party} route point is too far from its drivable lane")
            waypoints.append(waypoint)
        mapped = [[waypoint.transform.location.x, waypoint.transform.location.y]
                  for waypoint in waypoints]
        if (_inside(mapped[0], bounds) or _inside(mapped[-1], bounds) or
                not any(_inside(point, bounds) for point in mapped[1:-1])):
            raise ValueError(f"{party} mapped route does not traverse the declared crossing")
        declared_road = scene[f"{party}_approach_road_id"]
        if waypoints[0].road_id != declared_road:
            raise ValueError(f"{party} approach road ID differs from source plan")
        if not any(w.is_junction for w in waypoints[1:-1]):
            raise ValueError(f"{party} route has no mapped junction waypoint")
        for first, second in zip(waypoints, waypoints[1:]):
            if not _forward_connected(first, second):
                raise ValueError(f"{party} route lacks forward Native waypoint connectivity")
        bound[party] = waypoints
    if scene["ego_approach_road_id"] == scene["other_approach_road_id"]:
        raise ValueError("approach road IDs are not distinct")
    return bound


def _forward_connected(first, second, limit=1200):
    """Follow Native waypoint successors, including legal junction branches."""
    target = second.transform.location
    pending = [first]
    seen = set()
    index = 0
    while index < len(pending) and index < limit:
        waypoint = pending[index]
        index += 1
        location = waypoint.transform.location
        key = (waypoint.road_id, getattr(waypoint, "lane_id", None),
               round(location.x, 1), round(location.y, 1))
        if key in seen:
            continue
        seen.add(key)
        if (index > 1 and waypoint.road_id == second.road_id
                and getattr(waypoint, "lane_id", None) == getattr(second, "lane_id", None)
                and math.hypot(location.x-target.x, location.y-target.y) <= 2):
            return True
        pending.extend(waypoint.next(2.0))
    return False
