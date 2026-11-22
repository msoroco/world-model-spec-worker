"""Portable route and precedence controller core; CARLA binding remains pending."""
from __future__ import annotations

import hashlib

from crossing_audit import _inside


def validate_routes(scene):
    """Check that two authored routes traverse one physically identified crossing."""
    crossing = scene["crossing"]
    bounds = crossing["bounds_xy_m"]
    if not crossing.get("map_source_sha256") or not crossing.get("crossing_id"):
        raise ValueError("source-hashed map and crossing identity required")
    if scene["ego_highway"] == scene["other_highway"]:
        raise ValueError("distinct highway identities required")
    directions = []
    for party in ("ego", "other"):
        route = scene[f"{party}_route_xy_m"]
        if len(route) < 3 or _inside(route[0], bounds) or _inside(route[-1], bounds):
            raise ValueError(f"{party} route must start and end outside crossing")
        if not any(_inside(p, bounds) for p in route[1:-1]):
            raise ValueError(f"{party} route misses crossing")
        directions.append((route[-1][0] - route[0][0], route[-1][1] - route[0][1]))
    dot = sum(a*b for a, b in zip(*directions))
    norms = (sum(x*x for x in directions[0]) * sum(x*x for x in directions[1])) ** 0.5
    if norms == 0 or abs(dot / norms) > 0.5:
        raise ValueError("routes do not form a crossing approach")
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
    for party in ("ego", "other"):
        route = scene[f"{party}_route_xy_m"]
        waypoints = []
        for x, y in route:
            waypoint = world_map.get_waypoint(location_factory(x, y), project_to_road=False)
            if waypoint is None:
                raise ValueError(f"{party} route point is not on a drivable lane")
            waypoints.append(waypoint)
        declared_road = scene[f"{party}_approach_road_id"]
        if waypoints[0].road_id != declared_road:
            raise ValueError(f"{party} approach road ID differs from source plan")
        if not any(w.is_junction for w in waypoints[1:-1]):
            raise ValueError(f"{party} route has no mapped junction waypoint")
        bound[party] = waypoints
    if scene["ego_approach_road_id"] == scene["other_approach_road_id"]:
        raise ValueError("approach road IDs are not distinct")
    return bound
