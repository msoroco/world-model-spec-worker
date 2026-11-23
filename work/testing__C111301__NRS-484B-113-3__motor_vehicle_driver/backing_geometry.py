"""Source-gated Native geometry for an intersection backing interaction.

This module never asserts that a named cell has a usable reverse path. The
operator must export an original CARLA/OpenDRIVE packet and validate it first.
"""
from math import hypot


def _point(value):
    if not isinstance(value, dict) or not all(k in value for k in ("x_m", "y_m", "source_ref")):
        raise ValueError("original coordinate and source reference required")
    if not value["source_ref"]:
        raise ValueError("empty coordinate source")
    return float(value["x_m"]), float(value["y_m"])


def _distance_to_segment(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 <= 0:
        raise ValueError("degenerate route segment")
    fraction = max(0.0, min(1.0, ((point[0]-start[0])*dx+(point[1]-start[1])*dy)/length2))
    return hypot(point[0]-start[0]-fraction*dx, point[1]-start[1]-fraction*dy)


def _segment_gap(a, b, c, d):
    def cross(u, v, p):
        return (v[0]-u[0])*(p[1]-u[1])-(v[1]-u[1])*(p[0]-u[0])
    if cross(a,b,c)*cross(a,b,d) <= 0 and cross(c,d,a)*cross(c,d,b) <= 0:
        return 0.0
    return min(_distance_to_segment(p, u, v) for p,u,v in
               ((a,c,d),(b,c,d),(c,a,b),(d,a,b)))


def validate(packet):
    """Return source identities and conflict geometry, not physical acceptance."""
    required = ("map_sha256", "map_name", "junction_id", "vehicle_blueprint_id",
                "pedestrian_blueprint_id", "vehicle_reverse_route", "pedestrian_route",
                "vehicle_half_width_m", "pedestrian_radius_m", "control_source")
    if any(k not in packet for k in required):
        raise ValueError("incomplete original Native map and actor packet")
    if len(packet["map_sha256"]) != 64 or not packet["map_name"] or packet["junction_id"] is None:
        raise ValueError("original source-hashed map junction required")
    if not packet["control_source"] or not packet["vehicle_blueprint_id"].startswith("vehicle."):
        raise ValueError("original vehicle and control source required")
    if not packet["pedestrian_blueprint_id"].startswith("walker.pedestrian."):
        raise ValueError("original pedestrian blueprint required")
    vehicle = packet["vehicle_reverse_route"]
    pedestrian = packet["pedestrian_route"]
    if len(vehicle) < 2 or len(pedestrian) < 2:
        raise ValueError("connected reverse and pedestrian routes required")
    if any(p.get("junction_id") != packet["junction_id"] for p in vehicle):
        raise ValueError("vehicle reverse route not bound to original junction")
    v = [_point(p) for p in vehicle]
    w = [_point(p) for p in pedestrian]
    if any(hypot(v[i+1][0]-v[i][0], v[i+1][1]-v[i][1]) < .1 for i in range(len(v)-1)):
        raise ValueError("vehicle reverse route contains degenerate segment")
    if any(hypot(w[i+1][0]-w[i][0], w[i+1][1]-w[i][1]) < .1 for i in range(len(w)-1)):
        raise ValueError("pedestrian route contains degenerate segment")
    width = float(packet["vehicle_half_width_m"])
    radius = float(packet["pedestrian_radius_m"])
    if width <= 0 or radius <= 0:
        raise ValueError("actor extents must be positive")
    closest = min(_segment_gap(v[i],v[i+1],w[j],w[j+1])
                  for i in range(len(v)-1) for j in range(len(w)-1))
    if closest > width + radius:
        raise ValueError("pedestrian route misses reverse body corridor")
    return {"map_sha256": packet["map_sha256"], "junction_id": packet["junction_id"],
            "vehicle_blueprint_id": packet["vehicle_blueprint_id"],
            "pedestrian_blueprint_id": packet["pedestrian_blueprint_id"],
            "route_gap_m": closest, "route_conflict": True,
            "physical_realization": "pending original Native execution"}
