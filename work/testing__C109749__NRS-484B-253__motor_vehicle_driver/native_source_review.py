"""Bind a proposed junction packet to an actual CARLA map survey.

The caller supplies a live CARLA map object and its location factory. No
diagnostic packet can be promoted by editing a provenance flag alone.
"""

import hashlib

from native_intersection import validate


def review(packet, *, carla_map, location_factory):
    validate(packet)
    if packet.get("diagnostic_fixture") or packet.get("reviewed_original_map") is not True:
        raise ValueError("reviewed original map packet required")
    road = carla_map.to_opendrive()
    if not isinstance(road, str) or not road:
        raise ValueError("live Native OpenDRIVE source missing")
    actual_hash = hashlib.sha256(road.encode("utf-8")).hexdigest()
    if actual_hash != packet["map_sha256"]:
        raise ValueError("Native OpenDRIVE bytes differ from reviewed packet")
    checked = []
    for route_name in ("ego_route", "opposing_route", "later_opposing_route"):
        route = packet.get(route_name)
        if route is None:
            continue
        for index, point in enumerate(route):
            location = location_factory(float(point["x_m"]), float(point["y_m"]))
            waypoint = carla_map.get_waypoint(location, project_to_road=False)
            if waypoint is None:
                raise ValueError("survey waypoint absent from live Native road")
            actual = (waypoint.road_id, waypoint.lane_id,
                      waypoint.get_junction().id if waypoint.is_junction else None)
            expected = (point["road_id"], point["lane_id"], point["junction_id"])
            if actual != expected:
                raise ValueError("survey waypoint road/lane/junction mismatch")
            if index == 1 and actual[2] != packet["junction_id"]:
                raise ValueError("survey midpoint is outside chosen junction")
            checked.append((route_name, index))
    if len(checked) < 6:
        raise ValueError("both original route surveys required")
    return {"native_map_sha256": actual_hash, "junction_id": packet["junction_id"],
            "checked_waypoints": len(checked), "source_id": packet["source_ref"],
            "physical_motion": "unverified", "pixel_visibility": "unverified"}
