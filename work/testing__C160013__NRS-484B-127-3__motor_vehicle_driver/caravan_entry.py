"""Plan a bounded entrant route from original caravan body geometry.

This is a pre-capture target plan. Native movement and danger are measured later.
"""
import math

from shapely.geometry import MultiPoint, Polygon


def _body(vertices):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Complete original body required")
    points = []
    for vertex in vertices:
        if (not isinstance(vertex, (list, tuple)) or len(vertex) != 2 or
                any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) for value in vertex)):
            raise ValueError("Finite original body vertices required")
        points.append(tuple(vertex))
    polygon = MultiPoint(points).convex_hull
    if polygon.area <= 0:
        raise ValueError("Degenerate original body")
    return polygon


def _extent(polygon, forward):
    values = [x * forward[0] + y * forward[1] for x, y in polygon.exterior.coords]
    return min(values), max(values)


def plan_entry(context, members, entrant_vertices, *, gap_index, outcome):
    if outcome not in ("occupy", "stop_before"):
        raise ValueError("Unknown selected caravan gap outcome")
    if not isinstance(members, list) or len(members) < 3:
        raise ValueError("At least three original caravan bodies required")
    forward = context.get("road_forward_xy")
    if not isinstance(forward, list) or len(forward) != 2:
        raise ValueError("Sourced highway direction required")
    length = math.hypot(*forward)
    if not math.isfinite(length) or length <= 0:
        raise ValueError("Invalid highway direction")
    forward = (forward[0] / length, forward[1] / length)
    normal = (-forward[1], forward[0])
    road = Polygon(context.get("roadway_polygon_xy_m", []))
    if not road.is_valid or road.area <= 0:
        raise ValueError("Sourced highway polygon required")
    identified = []
    for member in members:
        if type(member.get("actor_id")) is not int:
            raise ValueError("Original caravan actor identity required")
        body = _body(member.get("body_vertices_xy_m"))
        if not road.covers(body):
            raise ValueError("Caravan body outside sourced highway")
        identified.append((member["actor_id"], body))
    if len({item[0] for item in identified}) != len(identified):
        raise ValueError("Duplicate original caravan actor identity")
    identified.sort(key=lambda item: item[1].centroid.x * forward[0] +
                    item[1].centroid.y * forward[1])
    if type(gap_index) is not int or not 0 <= gap_index < len(identified) - 1:
        raise ValueError("Selected gap index outside original caravan")
    (rear_id, rear), (front_id, front) = identified[gap_index:gap_index + 2]
    rear_edge = _extent(rear, forward)[1]
    front_edge = _extent(front, forward)[0]
    opening = front_edge - rear_edge
    entrant = _body(entrant_vertices)
    if not road.covers(entrant):
        raise ValueError("Entrant body outside sourced highway")
    entrant_length = _extent(entrant, forward)[1] - _extent(entrant, forward)[0]
    target_s = (rear_edge + front_edge) / 2
    caravan_lateral = (rear.centroid.x * normal[0] + rear.centroid.y * normal[1] +
                       front.centroid.x * normal[0] + front.centroid.y * normal[1]) / 2
    entrant_lateral = entrant.centroid.x * normal[0] + entrant.centroid.y * normal[1]
    if abs(entrant_lateral - caravan_lateral) < 1.5:
        raise ValueError("Entrant must start in a distinct lateral approach")
    approach = [target_s * forward[0] + entrant_lateral * normal[0],
                target_s * forward[1] + entrant_lateral * normal[1]]
    target = [target_s * forward[0] + caravan_lateral * normal[0],
              target_s * forward[1] + caravan_lateral * normal[1]]
    if not road.covers(MultiPoint([approach, target]).convex_hull):
        raise ValueError("Planned merge leaves sourced highway")
    if outcome == "occupy" and opening <= entrant_length:
        raise ValueError("Complete entrant body cannot fit selected physical opening")
    return {"format": "worker-caravan-entry-plan", "outcome": outcome,
            "rear_actor_id": rear_id, "front_actor_id": front_id,
            "opening_m": max(0.0, opening), "entrant_body_length_m": entrant_length,
            "waypoints_xy_m": [approach, target] if outcome == "occupy" else [approach],
            "actual_occupancy_confirmed": False,
            "without_danger_judgment": "unresolved"}
