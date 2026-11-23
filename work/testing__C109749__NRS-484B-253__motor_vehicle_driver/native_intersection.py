"""Validate a reviewed Native intersection packet before left-turn construction.

The packet must be extracted from the selected CARLA/OpenDRIVE map; this module
does not create an intersection by drawing an annotation or inventing a tag.
"""

from math import hypot
from left_turn_measurements import _inside


def _vector(a, b):
    return (b[0] - a[0], b[1] - a[1])


def _unit(v):
    size = hypot(*v)
    if size < 1e-6:
        raise ValueError("route segment has zero length")
    return (v[0] / size, v[1] / size)


def validate(packet):
    required = ("map_sha256", "source_ref", "junction_id", "intersection_polygon",
                "ego_route", "opposing_route", "ego_blueprint_id", "opponent_blueprint_id")
    if any(key not in packet for key in required):
        raise ValueError("original Native map packet incomplete")
    if len(packet["map_sha256"]) != 64 or not packet["source_ref"] or packet["junction_id"] is None:
        raise ValueError("source-hashed original junction required")
    polygon = packet["intersection_polygon"]
    if len(polygon) < 4:
        raise ValueError("intersection polygon requires physical boundary vertices")
    routes = []
    for key in ("ego_route", "opposing_route"):
        route = packet[key]
        if len(route) < 3:
            raise ValueError("connected approach, intersection and exit waypoints required")
        if any(not waypoint.get("source_ref") or waypoint.get("junction_id") != packet["junction_id"]
               and index == 1 for index, waypoint in enumerate(route)):
            raise ValueError("original junction waypoint provenance required")
        if any("x_m" not in point or "y_m" not in point or "road_id" not in point or "lane_id" not in point
               for point in route):
            raise ValueError("original route coordinates and road/lane IDs required")
        coordinates = [(float(p["x_m"]), float(p["y_m"])) for p in route]
        if _inside(coordinates[0], polygon) or not _inside(coordinates[1], polygon) or _inside(coordinates[-1], polygon):
            raise ValueError("route must enter and leave original intersection")
        routes.append(coordinates)
    ego, opposing = routes
    ego_in, ego_out = _unit(_vector(ego[0], ego[1])), _unit(_vector(ego[1], ego[-1]))
    opp_in = _unit(_vector(opposing[0], opposing[1]))
    cross = ego_in[0] * ego_out[1] - ego_in[1] * ego_out[0]
    if cross < 0.35:
        raise ValueError("ego route does not turn left through original junction")
    if ego_in[0] * opp_in[0] + ego_in[1] * opp_in[1] > -0.7:
        raise ValueError("opposing route is not opposite-direction")
    if packet["ego_blueprint_id"] == packet["opponent_blueprint_id"] == "":
        raise ValueError("ordinary vehicle blueprints required")
    return {"map_sha256": packet["map_sha256"], "junction_id": packet["junction_id"],
            "connected_left_turn": True, "opposite_direction": True,
            "physical_realization": "requires Native execution and original frame review"}
